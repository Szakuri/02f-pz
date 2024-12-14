from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    session,
    send_file
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from pytesseract import image_to_string
from pdf2image import convert_from_path
import os
import unicodedata
import re

db = SQLAlchemy()
migrate = Migrate()


def remove_diacritics(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

def extract_email_from_cv_text(text):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None


def extract_name_from_cv_text(text, max_lines=60):

    normalized_text = remove_diacritics(text)
    lines = [line.strip() for line in normalized_text.strip().split("\n") if line.strip()]

    
    ignore_keywords = {
        "LANGUAGES", "SKILLS", "EDUCATION", "REFERENCES", "CONTACT", "PROFILE",
        "O MNIE", "ABOUT ME", "KONTAKT", "ADRES", "CERTYFIKATY", "CERTIFICATES",
        "JĘZYKI", "JEZYKI", "EDUKACJA", "DOŚWIADCZENIE", "EXPERIENCE",
        "UMIEJĘTNOŚCI", "UMIEJETNOSCI", "UNIVERSITY", "COLLEGE", "INSTITUTE", "SZKOLA", "UNIWERSYTET", "LICEUM", "TECHNIKUM"
    }

    for i, line in enumerate(lines[:max_lines]):
        if any(keyword in line for keyword in ignore_keywords):
            continue

        cleaned_line = re.sub(r"\d+|[^A-Z\s]", "", line).strip()

        match = re.match(r"^([A-Z]{2,})\s+([A-Z]{2,})$", cleaned_line)
        if match:
            return f"{match.group(1)} {match.group(2)}"

        if i + 1 < len(lines):
            cleaned_next_line = re.sub(r"\d+|[^A-Z\s]", "", lines[i + 1]).strip()
            if line.isupper() and cleaned_next_line.isupper():
                return f"{line} {lines[i + 1]}"
            
    return "Nierozpoznane"


def extract_phone_from_cv_text(text):
    phone_pattern = r'(?:\+?\d{1,3}[ -]?)?(?:\(?\d{1,4}\)?[ -]?)?\d{3,4}[ -]?\d{3,4}[ -]?\d{3,4}'
    match = re.search(phone_pattern, text)
    return match.group(0) if match else None



def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), "uploads"
    )
    app.secret_key = os.urandom(24)
    app.secret_key = os.getenv("SECRET_KEY", "domyslny_klucz")

    db.init_app(app)
    migrate.init_app(app, db)
        
    with app.app_context():
        from models import Position, Keyword, Candidate, User
        db.create_all() 
        create_default_positions()

    @app.route("/")
    def home():
        if "user_id" not in session:
            flash("Musisz się zalogować!")
            return redirect(url_for("login"))
        user = User.query.get(session["user_id"])
        return render_template("home.html", username=user.username)

    @app.route("/upload")
    def upload():
        if "user_id" not in session:
            flash("Musisz się zalogować!")
            return redirect(url_for("login"))

        user_id = session["user_id"]

        if request.method == "POST":
            selected_position_id = request.form.get("position_id")
            session["last_position_id"] = selected_position_id

        global_positions = Position.query.filter_by(is_default=True).all()
        user_positions = Position.query.filter_by(user_id=user_id).all()
        last_position_id = session.get("last_position_id", global_positions[0].id if global_positions else None)

        return render_template(
            "upload.html",
            global_positions=global_positions,
            user_positions=user_positions,
            last_position_id=last_position_id 
        )

    @app.route("/positions", methods=["POST"])
    def add_position():
        data = request.json
        position = Position(title=data["title"])
        db.session.add(position)
        db.session.commit()

        for word in data["keywords"]:
            keyword = Keyword(word=word, position_id=position.id)
            db.session.add(keyword)

        db.session.commit()
        return jsonify({"message": "Stanowisko zostało pomyślnie dodane!"}), 201

    @app.route("/analyze_cv", methods=["POST"])
    def analyze_cv():
        try:
            user_input_name = request.form["name"]
            position_id = int(request.form["position_id"])
            file = request.files["file"]

            session["last_position_id"] = position_id

            filename = f"{user_input_name}_{file.filename}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            keywords = Keyword.query.filter_by(position_id=position_id).all()

            try:
                pages = convert_from_path(file_path)
                extracted_text = " ".join(image_to_string(page) for page in pages)
            except Exception as e:
                flash(f"Błąd podczas wyodrębniania tekstu z PDF: {str(e)}")
                return redirect(url_for("upload"))

            first_words = extract_name_from_cv_text(extracted_text)
            email_cv = extract_email_from_cv_text(extracted_text)
            phone_number = extract_phone_from_cv_text(extracted_text)

            normalized_text = remove_diacritics(extracted_text).lower()

            results = {}
            total_score = 0
            for keyword in keywords:
                keyword_normalized = remove_diacritics(keyword.word).lower()
                count = normalized_text.count(keyword_normalized)
                points = count * keyword.weight  # Uwzględnienie wagi
                results[keyword.word] = {"count": count, "weight": keyword.weight, "points": points}
                total_score += points

 
            candidate = Candidate(
                name=user_input_name,  
                first_words=first_words,  
                cv_text=extracted_text,
                email_cv=email_cv,
                phone_number=phone_number,
                position_id=position_id,
                points=total_score,
                user_id=session.get("user_id"),
                path=file_path
            )
            db.session.add(candidate)
            db.session.commit()

            return render_template("results.html", name=user_input_name, results=results, total_score=total_score)

        except Exception as e:
            flash(f"Wystąpił błąd: {str(e)}")
            return redirect(url_for("upload"))


    @app.route("/add_position", methods=["GET", "POST"])
    def add_position_form():
        if "user_id" not in session:
            flash("Musisz się zalogować!")
            return redirect(url_for("login"))

        if request.method == "POST":
            title = request.form["title"]
            keywords = request.form["keywords"].split(",")

            position = Position(title=title, user_id=session["user_id"])
            db.session.add(position)
            db.session.commit()

            for keyword in keywords:
                kw = Keyword(word=keyword.strip(), position_id=position.id)
                db.session.add(kw)

            db.session.commit()

            flash("Stanowisko zostało dodane pomyślnie!")
            return redirect(url_for("home"))

        return render_template("add_position.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form["username"]
            email = request.form["email"]
            password = request.form["password"]

            if User.query.filter_by(username=username).first():
                flash("Nazwa użytkownika jest już zajęta!")
                return redirect(url_for("register"))

            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()

            flash("Rejestracja zakończona pomyślnie! Teraz możesz się zalogować.")
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]

            user = User.query.filter_by(username=username).first()

            if user and user.check_password(password):
                session["user_id"] = user.id
                flash("Logowanie zakończone sukcesem!")
                return redirect(url_for("home"))
            else:
                flash("Niepoprawna nazwa użytkownika lub hasło.")
                return redirect(url_for("login"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.pop("user_id", None)
        flash("Wylogowano pomyślnie!")
        return redirect(url_for("login"))

    @app.route("/view_positions")
    def view_positions():
        if "user_id" not in session:
            flash("Musisz się zalogować!")
            return redirect(url_for("login"))

        user_id = session["user_id"]
        positions = Position.query.filter_by(user_id=user_id).all()
        return render_template("view_positions.html", positions=positions)
    

    @app.route("/ranking", methods=["GET", "POST"])
    def ranking():
        try:
            positions = Position.query.all()
            position_id = request.args.get("position_id", type=int) or positions[0].id
            limit = request.args.get("limit", default=20, type=int)
            limit = max(1, min(limit, 50))

            position = Position.query.get_or_404(position_id)
            candidates = (
                Candidate.query.filter_by(position_id=position_id)
                .filter((Candidate.user_id == session.get("user_id")) | (Candidate.user_id.is_(None)))  
                .filter(Candidate.points.isnot(None))
                .order_by(Candidate.points.desc())
                .limit(limit)
                .all()
                )

            candidates_with_index = list(enumerate(candidates, start=1))

            return render_template(
                "ranking.html",
                positions=positions,
                position=position,
                candidates_with_index=candidates_with_index,
                limit=limit,
            )
        except Exception as e:
            flash(f"Wystąpił błąd: {str(e)}")
            return redirect(url_for("home"))
        
        
    @app.route("/edit_position/<int:position_id>", methods=["GET", "POST"])
    def edit_position(position_id):
        position = Position.query.get_or_404(position_id)

        if request.method == "POST":
            title = request.form.get("title")
            position.title = title

            keyword_ids = request.form.getlist("keyword_ids")
            keyword_words = request.form.getlist("keyword_words")
            weights = request.form.getlist("weights")
            deleted_keywords = request.form.getlist("deleted_keywords")

            for keyword_id in deleted_keywords:
                keyword = Keyword.query.get(int(keyword_id))
                if keyword:
                    db.session.delete(keyword)

            for keyword_id, word, weight in zip(keyword_ids, keyword_words, weights):
                keyword = Keyword.query.get(int(keyword_id))
                if keyword:
                    keyword.word = word
                    keyword.weight = int(weight)

            new_keywords = request.form.getlist("new_keywords[]")
            new_weights = request.form.getlist("new_weights[]")
            for word, weight in zip(new_keywords, new_weights):
                new_keyword = Keyword(word=word, weight=int(weight), position_id=position_id)
                db.session.add(new_keyword)

            db.session.commit()
            flash("Stanowisko zostało zaktualizowane!")
            return redirect(url_for("view_positions"))

        keywords = Keyword.query.filter_by(position_id=position.id).all()
        return render_template("edit_position.html", position=position, keywords=keywords)


    @app.route("/delete_position/<int:position_id>", methods=["POST"])
    def delete_position(position_id):
        position = Position.query.get_or_404(position_id)
        
        if position.is_default:
            flash("Nie można usunąć globalnych stanowisk!")
            return redirect(url_for("view_positions"))
        
        db.session.delete(position)
        db.session.commit()
        flash("Stanowisko zostało pomyślnie usunięte!")
        return redirect(url_for("view_positions"))
    

    @app.route("/download_cv/<int:candidate_id>")
    def download_cv(candidate_id):
        candidate = Candidate.query.get_or_404(candidate_id)
        if not candidate.path:
            flash("Ten kandydat nie ma przesłanego CV.")
            return redirect(url_for("ranking"))
        return send_file(candidate.path, as_attachment=True)

    @app.route("/preview_cv/<int:candidate_id>")
    def preview_cv(candidate_id):
        candidate = Candidate.query.get_or_404(candidate_id)
        if not candidate.path:
            flash("Ten kandydat nie ma przesłanego CV.")
            return redirect(url_for("ranking"))
        return send_file(candidate.path)
    
    @app.route("/delete_candidate/<int:candidate_id>", methods=["POST"])
    def delete_candidate(candidate_id):
        candidate = Candidate.query.get_or_404(candidate_id)

        if candidate.user_id != session.get("user_id"):
            flash("Nie możesz usunąć tego kandydata.")
            return redirect(url_for("ranking"))

        db.session.delete(candidate)
        db.session.commit()

        flash("Kandydat został pomyślnie usunięty.")
        return redirect(url_for("ranking"))



    return app

def create_default_positions():
    from models import Position, Keyword

    Position.query.filter_by(is_default=True).delete()
    db.session.commit()

    # Struktura z wagami dla słów kluczowych
    default_positions = [
        {
        "title": "Programista",
        "keywords": [
            {"word": "programowanie", "weight": 5}, {"word": "Python", "weight": 5},
            {"word": "Java", "weight": 5}, {"word": "JavaScript", "weight": 5},
            {"word": "C#", "weight": 4}, {"word": "SQL", "weight": 3},
            {"word": "bazy danych", "weight": 2}, {"word": "API", "weight": 3},
            {"word": "framework", "weight": 3}, {"word": "debugowanie", "weight": 3},
            {"word": "kodowanie", "weight": 2}, {"word": "systemy operacyjne", "weight": 2},
            {"word": "integracja", "weight": 1}, {"word": "automatyzacja", "weight": 2},
            {"word": "scrum", "weight": 3}, {"word": "agile", "weight": 2},
            {"word": "testing", "weight": 2}, {"word": "backend", "weight": 4},
            {"word": "frontend", "weight": 4}, {"word": "narzędzia CI/CD", "weight": 4},
            {"word": "Git", "weight": 4}, {"word": "Docker", "weight": 3},
            {"word": "Linux", "weight": 3}, {"word": "Windows", "weight": 3},
            {"word": "architektura systemów", "weight": 3}, {"word": "analityka", "weight": 2},
            {"word": "optymalizacja", "weight": 3}, {"word": "REST", "weight": 4},
            {"word": "SOAP", "weight": 3}, {"word": "mikroserwisy", "weight": 4},
            {"word": "bezpieczeństwo IT", "weight": 5}, {"word": "refaktoryzacja", "weight": 2},
            {"word": "chmura", "weight": 4}, {"word": "Azure", "weight": 4},
            {"word": "AWS", "weight": 4}, {"word": "GCP", "weight": 4}, {"word": "DevOps", "weight": 4}, 
            {"word": "B1", "weight": 1}, {"word": "B2", "weight": 2},
            {"word": "C1", "weight": 3}, {"word": "C2", "weight": 4}, {"word": "English", "weight": 1}, 
            {"word": "Angielski", "weight": 1}, {"word": "FastAPI", "weight": 3}, {"word": "Flask", "weight": 4}, {"word": "Django", "weight": 5}, {"word": "TypeScript", "weight": 4}, {"word": "React", "weight": 5}, {"word": "Node.js", "weight": 4}, {"word": "Jenkins", "weight": 4}, {"word": "GitHub Actions", "weight": 3}, {"word": "Kubernetes", "weight": 3},{"word": "Ansible", "weight": 2},{"word": "Terraform", "weight": 2},{"word": "AWS Lambda", "weight": 2}, {"word": "AWS S3", "weight": 2}, {"word": "Azure DevOps", "weight": 2}, {"word": "Redis", "weight": 3},{"word": "PostgreSQL", "weight": 2},{"word": "MongoDB", "weight": 2}, {"word": "pytest", "weight": 2}
        ]
    },
    {
    "title": "Analityk Danych",
    "keywords": [
        {"word": "dane", "weight": 5}, {"word": "Excel", "weight": 3},
        {"word": "SQL", "weight": 5}, {"word": "analizy", "weight": 4},
        {"word": "wizualizacja danych", "weight": 4}, {"word": "Tableau", "weight": 3},
        {"word": "Power BI", "weight": 4}, {"word": "statystyka", "weight": 5},
        {"word": "Python", "weight": 5}, {"word": "R", "weight": 4},
        {"word": "modele predykcyjne", "weight": 5}, {"word": "algorytmy", "weight": 5},
        {"word": "analiza danych", "weight": 5}, {"word": "przetwarzanie danych", "weight": 4},
        {"word": "ETL", "weight": 4}, {"word": "dashboard", "weight": 3},
        {"word": "raporty", "weight": 4}, {"word": "Big Data", "weight": 5},
        {"word": "Hadoop", "weight": 5}, {"word": "Spark", "weight": 5},
        {"word": "analityka biznesowa", "weight": 4}, {"word": "insighty", "weight": 3},
        {"word": "dane sprzedażowe", "weight": 3}, {"word": "prognozowanie", "weight": 5},
        {"word": "optymalizacja", "weight": 2}, {"word": "bazy danych", "weight": 4},
        {"word": "machine learning", "weight": 5}, {"word": "analiza rynku", "weight": 3},
        {"word": "czyszczenie danych", "weight": 2}, {"word": "Google Analytics", "weight": 2},
        {"word": "KPIs", "weight": 3}, {"word": "modelowanie danych", "weight": 5},
        {"word": "B1", "weight": 1}, {"word": "B2", "weight": 2},
        {"word": "C1", "weight": 3}, {"word": "C2", "weight": 4}, {"word": "English", "weight": 1},
        {"word": "Angielski", "weight": 1}, {"word": "matplotlib", "weight": 4}, {"word": "seaborn", "weight": 4},
        {"word": "pandas", "weight": 5}, {"word": "numpy", "weight": 5}, {"word": "scikit-learn", "weight": 5},
        {"word": "Jupyter Notebook", "weight": 3}, {"word": "Apache Spark", "weight": 5},
        {"word": "Apache Hadoop", "weight": 4}, {"word": "ETL pipelines", "weight": 4},
        {"word": "TensorFlow", "weight": 5}, {"word": "Keras", "weight": 4},
        {"word": "PyTorch", "weight": 5}, {"word": "modele regresyjne", "weight": 5},
        {"word": "klasyfikacja danych", "weight": 4}, {"word": "modelowanie predykcyjne", "weight": 5},
        {"word": "SQLAlchemy", "weight": 4}, {"word": "DBeaver", "weight": 3}, {"word": "Snowflake", "weight": 4},
        {"word": "Apache Airflow", "weight": 5}, {"word": "CRM", "weight": 4},
        {"word": "pipeline danych", "weight": 4}, {"word": "churn prediction", "weight": 4},
        {"word": "klasyfikacja klientów", "weight": 5}, {"word": "integracja danych", "weight": 4},
        {"word": "algorytmy AI", "weight": 5}, {"word": "rozmowy z klientami", "weight": 3},
        {"word": "analiza ruchu internetowego", "weight": 4}, {"word": "modele statystyczne", "weight": 5},
        {"word": "segmentacja użytkowników", "weight": 4}, {"word": "narzędzia analityczne", "weight": 3},
        {"word": "raportowanie", "weight": 4}, {"word": "środowiska Big Data", "weight": 5},
        {"word": "Linux", "weight": 4}, {"word": "IBM SPSS Modeler", "weight": 3},
        {"word": "Scrum", "weight": 3}, {"word": "Agile", "weight": 3}, {"word": "Jira", "weight": 3},
        {"word": "Confluence", "weight": 3}, {"word": "statystyka e-commerce", "weight": 5},
        {"word": "umiejętność analitycznego myślenia", "weight": 4}, {"word": "komunikatywność", "weight": 2},
        {"word": "praca zespołowa", "weight": 3}
    ]
    },
    {
    "title": "Kierownik Projektu",
    "keywords": [
        {"word": "zarządzanie projektami", "weight": 5}, {"word": "harmonogramy", "weight": 3}, {"word": "budżet", "weight": 5}, {"word": "agile", "weight": 5}, {"word": "scrum", "weight": 5}, {"word": "waterfall", "weight": 2}, {"word": "zarządzanie ryzykiem", "weight": 5}, {"word": "priorytetyzacja", "weight": 3}, {"word": "planowanie", "weight": 4}, {"word": "komunikacja", "weight": 5}, {"word": "zarządzanie zespołem", "weight": 5}, {"word": "stakeholderzy", "weight": 4}, {"word": "analiza wymagań", "weight": 4}, {"word": "cele projektu", "weight": 5}, {"word": "raportowanie", "weight": 3},
        {"word": "monitoring", "weight": 3}, {"word": "zarządzanie czasem", "weight": 3}, {"word": "zarządzanie zmianą", "weight": 5}, {"word": "leadership", "weight": 5}, {"word": "efektywność", "weight": 4}, {"word": "metodologia", "weight": 4}, {"word": "stand-up", "weight": 2}, {"word": "roadmap", "weight": 2}, {"word": "narzędzia PM", "weight": 4}, {"word": "Jira", "weight": 5}, {"word": "Asana", "weight": 4}, {"word": "MS Project", "weight": 4}, {"word": "change management", "weight": 5}, {"word": "project governance", "weight": 4}, {"word": "stakeholder engagement", "weight": 5}, {"word": "risk assessment", "weight": 5}, {"word": "budget control", "weight": 5},
        {"word": "time management", "weight": 4}, {"word": "negotiation skills", "weight": 4}, {"word": "project lifecycle", "weight": 4}, {"word": "team collaboration", "weight": 4}, {"word": "resource allocation", "weight": 3}, {"word": "communication plan", "weight": 4}, {"word": "process optimization", "weight": 4}, {"word": "conflict resolution", "weight": 3}, {"word": "KPI tracking", "weight": 4}, {"word": "milestone management", "weight": 3}, {"word": "Lean methodology", "weight": 3}, {"word": "Six Sigma", "weight": 3}, {"word": "critical path method (CPM)", "weight": 2}, {"word": "project documentation", "weight": 4}, {"word": "SCRUM Master", "weight": 4},
        {"word": "user stories", "weight": 3}, {"word": "issue tracking", "weight": 3}, {"word": "performance metrics", "weight": 4}, {"word": "cross-functional teams", "weight": 4}, {"word": "PRINCE2", "weight": 4}, {"word": "Kanban", "weight": 3}, {"word": "Gantt charts", "weight": 2}, {"word": "OKRs (Objectives and Key Results)", "weight": 4}, {"word": "B1", "weight": 1}, {"word": "B2", "weight": 2}, {"word": "C1", "weight": 3}, {"word": "C2", "weight": 4}, {"word": "English", "weight": 1}, {"word": "Angielski", "weight": 1}
    ]
    },

    {
    "title": "Copywriter",
    "keywords": [
        {"word": "SEO", "weight": 5}, {"word": "optymalizacja tresci", "weight": 5},
        {"word": "copywriting", "weight": 5}, {"word": "marketing tresci", "weight": 4},
        {"word": "artykuly", "weight": 4}, {"word": "blogi", "weight": 4},
        {"word": "storytelling", "weight": 5}, {"word": "kreatywne pisanie", "weight": 4},
        {"word": "redagowanie", "weight": 4}, {"word": "social media", "weight": 4},
        {"word": "CTA", "weight": 3}, {"word": "reklama", "weight": 4},
        {"word": "edytowanie", "weight": 4}, {"word": "jezyk", "weight": 4},
        {"word": "tresc", "weight": 4}, {"word": "analiza konkurencji", "weight": 4},
        {"word": "Google Analytics", "weight": 4}, {"word": "Ahrefs", "weight": 4},
        {"word": "Google Search Console", "weight": 4}, {"word": "targetowanie", "weight": 3},
        {"word": "UX writing", "weight": 4}, {"word": "optymalizacja slow kluczowych", "weight": 5},
        {"word": "analiza odbiorcow", "weight": 3}, {"word": "lekkie pioro", "weight": 4},
        {"word": "korekta tekstow", "weight": 4}, {"word": "MS Office", "weight": 3},
        {"word": "JIRA", "weight": 3}, {"word": "Confluence", "weight": 3},
        {"word": "HTML", "weight": 3}, {"word": "research", "weight": 4},
        {"word": "ortografia", "weight": 3}, {"word": "interpunkcja", "weight": 3},
        {"word": "kreatywnosc", "weight": 3}, {"word": "terminowosc", "weight": 3},
        {"word": "organizacja pracy", "weight": 3}, {"word": "perswazja", "weight": 3},
        {"word": "uwaznosc na detale", "weight": 3}, {"word": "psychologia", "weight": 2},
        {"word": "socjologia", "weight": 2}, {"word": "empatia", "weight": 2},
        {"word": "tresci reklamowe", "weight": 4}, {"word": "call to action", "weight": 3},
        {"word": "kampanie reklamowe", "weight": 4}, {"word": "opisy produktow", "weight": 4},
        {"word": "hasla reklamowe", "weight": 3}, {"word": "newslettery", "weight": 3},
        {"word": "e-booki", "weight": 3}, {"word": "projektowanie bannerow", "weight": 3},
        {"word": "jezyk angielski", "weight": 3}, {"word": "jezyk polski", "weight": 3}
    ]
    },
    {
    "title": "Specjalista ds. marketingu",
    "keywords": [
        {"word": "marketing cyfrowy", "weight": 5}, {"word": "SEO", "weight": 5},
        {"word": "SEM", "weight": 5}, {"word": "Google Ads", "weight": 4},
        {"word": "Facebook Ads", "weight": 4}, {"word": "social media", "weight": 4},
        {"word": "kampanie reklamowe", "weight": 4}, {"word": "content marketing", "weight": 4},
        {"word": "Google Analytics", "weight": 5}, {"word": "email marketing", "weight": 4},
        {"word": "automatyzacja marketingu", "weight": 4}, {"word": "analiza rynku", "weight": 4},
        {"word": "remarketing", "weight": 4}, {"word": "lead generation", "weight": 5},
        {"word": "strategia SEO", "weight": 5}, {"word": "zarzadzanie budzetem", "weight": 4},
        {"word": "A/B testing", "weight": 5}, {"word": "UX", "weight": 3},
        {"word": "tworzenie tresci", "weight": 4}, {"word": "copywriting", "weight": 4},
        {"word": "Salesforce", "weight": 4}, {"word": "Salesmanago", "weight": 4},
        {"word": "kampanie PPC", "weight": 5}, {"word": "branding", "weight": 4},
        {"word": "projektowanie landing pages", "weight": 4}, {"word": "HTML", "weight": 3},
        {"word": "CMS", "weight": 4}, {"word": "Corel Draw", "weight": 3},
        {"word": "Adobe Photoshop", "weight": 3}, {"word": "Google Tag Manager", "weight": 4},
        {"word": "analiza odbiorcow", "weight": 4}, {"word": "media planowanie", "weight": 4},
        {"word": "strategia marketingowa", "weight": 5}, {"word": "optymalizacja", "weight": 5},
        {"word": "perswazja", "weight": 3}, {"word": "kreatywnosc", "weight": 3},
        {"word": "zarzadzanie zespolem", "weight": 3}, {"word": "Wordpress", "weight": 4},
        {"word": "B2", "weight": 2}, {"word": "C1", "weight": 3},
        {"word": "angielski", "weight": 1}, {"word": "english", "weight": 1}
    ],
    },
    {
    "title": "Administrator Sieci",
    "keywords": [
        {"word": "sieci komputerowe", "weight": 5}, {"word": "protokoły", "weight": 5},
        {"word": "TCP/IP", "weight": 5}, {"word": "DNS", "weight": 4},
        {"word": "DHCP", "weight": 4}, {"word": "routing", "weight": 4},
        {"word": "VPN", "weight": 5}, {"word": "bezpieczenstwo", "weight": 5},
        {"word": "firewalle", "weight": 5}, {"word": "zarzadzanie siecia", "weight": 5},
        {"word": "konfiguracja", "weight": 4}, {"word": "LAN", "weight": 4},
        {"word": "WAN", "weight": 4}, {"word": "zarzadzanie serwerami", "weight": 5},
        {"word": "backup", "weight": 4}, {"word": "monitoring sieci", "weight": 4},
        {"word": "roziazywanie problemow", "weight": 4}, {"word": "load balancing", "weight": 4},
        {"word": "NAT", "weight": 3}, {"word": "VLAN", "weight": 3},
        {"word": "QoS", "weight": 3}, {"word": "SNMP", "weight": 3},
        {"word": "Wi-Fi", "weight": 4}, {"word": "urzadzenia sieciowe", "weight": 4},
        {"word": "Cisco", "weight": 5}, {"word": "Juniper", "weight": 4},
        {"word": "Mikrotik", "weight": 4}, {"word": "przelaczniki", "weight": 4},
        {"word": "routery", "weight": 4}, {"word": "topologia sieci", "weight": 4},
        {"word": "systemy redundantne", "weight": 5}, {"word": "HA", "weight": 5},
        {"word": "IPSec", "weight": 4}, {"word": "Ethernet", "weight": 4},
        {"word": "802.11", "weight": 3}, {"word": "MPLS", "weight": 3},
        {"word": "IP", "weight": 4}, {"word": "IPv6", "weight": 4},
        {"word": "zarzadzanie dostepem", "weight": 5}, {"word": "kontrola przeplywu", "weight": 4},
        {"word": "proxy", "weight": 3}, {"word": "IDS/IPS", "weight": 4},
        {"word": "SIEM", "weight": 4}, {"word": "zarzadzanie urzadzeniami", "weight": 4},
        {"word": "PowerShell", "weight": 4}, {"word": "Bash", "weight": 4},
        {"word": "automatyzacja", "weight": 5}, {"word": "monitorowanie ruchu", "weight": 4},
        {"word": "Ansible", "weight": 4}, {"word": "Kubernetes", "weight": 4},
        {"word": "AWS", "weight": 4}, {"word": "Azure", "weight": 4},
        {"word": "GCP", "weight": 4}, {"word": "Active Directory", "weight": 4},
        {"word": "SolarWinds", "weight": 4}, {"word": "Nagios", "weight": 4},
        {"word": "Wireshark", "weight": 4}, {"word": "VoIP", "weight": 3},
        {"word": "SSL/TLS", "weight": 3}, {"word": "certyfikaty", "weight": 3},
        {"word": "praca zespolowa", "weight": 2}, {"word": "Python", "weight": 4},
        {"word": "zarzadzanie infrastruktura", "weight": 5}, {"word": "macierzystosc", "weight": 3},
        {"word": "zarzadzanie tozsamoscia", "weight": 4}, {"word": "kontrola dostepu", "weight": 5},
        {"word": "Cybersecurity", "weight": 5}, {"word": "Linux", "weight": 4},
        {"word": "Windows Server", "weight": 4}, {"word": "Hyper-V", "weight": 3},
        {"word": "VMware", "weight": 4}, {"word": "Docker", "weight": 4},
        {"word": "przepustowosc", "weight": 3}, {"word": "DevOps", "weight": 4},
        {"word": "chmura hybrydowa", "weight": 4}, {"word": "zdalny dostep", "weight": 4},
        {"word": "English", "weight": 1}, {"word": "angielski", "weight": 2}
    ]
},
    {
    "title": "Specjalista HR",
    "keywords": [
        {"word": "rekrutacja", "weight": 5}, {"word": "onboarding", "weight": 5},
        {"word": "rozwijanie pracownikow", "weight": 4}, {"word": "rozmowy kwalifikacyjne", "weight": 4},
        {"word": "ocena pracownikow", "weight": 4}, {"word": "szkolenia", "weight": 4},
        {"word": "employer branding", "weight": 5}, {"word": "zarzadzanie talentami", "weight": 5},
        {"word": "benefity", "weight": 4}, {"word": "kultura organizacyjna", "weight": 4},
        {"word": "HRIS", "weight": 4}, {"word": "umowy", "weight": 3},
        {"word": "planowanie zatrudnienia", "weight": 5}, {"word": "rotacja pracownikow", "weight": 4},
        {"word": "analiza kompetencji", "weight": 4}, {"word": "zaangazowanie pracownikow", "weight": 4},
        {"word": "raporty HR", "weight": 4}, {"word": "KPI", "weight": 4},
        {"word": "prawo pracy", "weight": 4}, {"word": "wynagrodzenia", "weight": 3},
        {"word": "programy motywacyjne", "weight": 4}, {"word": "feedback", "weight": 4},
        {"word": "rozwijanie liderow", "weight": 5}, {"word": "zarzadzanie konfliktem", "weight": 3},
        {"word": "eventy integracyjne", "weight": 3}, {"word": "systemy kadrowo-placowe", "weight": 4},
        {"word": "succession planning", "weight": 4}, {"word": "talent acquisition", "weight": 4},
        {"word": "rozwoj liderow", "weight": 5}, {"word": "komunikacja wewnetrzna", "weight": 3},
        {"word": "planowanie szkoleń", "weight": 4}, {"word": "raportowanie HR", "weight": 4},
        {"word": "retencja pracownikow", "weight": 4}, {"word": "zarzadzanie zespolami", "weight": 3},
        {"word": "analiza danych HR", "weight": 4}, {"word": "prawa zatrudnienia", "weight": 3},
        {"word": "zarzadzanie benefitami", "weight": 4}, {"word": "work-life balance", "weight": 3},
        {"word": "strategia employer brandingowa", "weight": 4}, {"word": "zarzadzanie talentami", "weight": 5},
        {"word": "B1", "weight": 1}, {"word": "B2", "weight": 2},
        {"word": "C1", "weight": 3}, {"word": "C2", "weight": 4}, {"word": "English", "weight": 1},
        {"word": "Angielski", "weight": 1}, {"word": "Word", "weight": 3}, {"word": "Excel", "weight": 3}, {"word": "HR", "weight": 2}
        ]
        },
    {
    "title": "Księgowy",
    "keywords": [
        {"word": "rachunkowosc", "weight": 5}, {"word": "ksiegi rachunkowe", "weight": 4},
        {"word": "podatki", "weight": 5}, {"word": "VAT", "weight": 4},
        {"word": "PIT", "weight": 4}, {"word": "CIT", "weight": 4},
        {"word": "bilans", "weight": 4}, {"word": "sprawozdania finansowe", "weight": 4},
        {"word": "budzetowanie", "weight": 5}, {"word": "kontrola kosztow", "weight": 4},
        {"word": "SAP", "weight": 4}, {"word": "audyt", "weight": 4},
        {"word": "Excel", "weight": 4}, {"word": "raportowanie", "weight": 4},
        {"word": "analiza kosztow", "weight": 4}, {"word": "rozliczenia", "weight": 4},
        {"word": "fakturowanie", "weight": 4}, {"word": "amortyzacja", "weight": 3},
        {"word": "prognozowanie finansowe", "weight": 4}, {"word": "zgodnosc podatkowa", "weight": 4},
        {"word": "kontrole wewnetrzne", "weight": 4}, {"word": "analiza wydatkow", "weight": 4},
        {"word": "bilansowanie", "weight": 4}, {"word": "systemy ERP", "weight": 4},
        {"word": "Cash Flow", "weight": 5}, {"word": "zobowiazania", "weight": 3},
        {"word": "naleznosci", "weight": 3}, {"word": "ksiegowosc zarzadcza", "weight": 4},
        {"word": "analiza finansowa", "weight": 5}, {"word": "zgodnosc regulacyjna", "weight": 5},
        {"word": "optymalizacja podatkowa", "weight": 4}, {"word": "VAT-UE", "weight": 4},
        {"word": "koszt jednostkowy", "weight": 3}, {"word": "QuickBooks", "weight": 4},
        {"word": "bank reconciliations", "weight": 4}, {"word": "financial reporting", "weight": 5},
        {"word": "tax compliance", "weight": 5}, {"word": "accounts payable", "weight": 4},
        {"word": "accounts receivable", "weight": 4}, {"word": "budgeting and forecasting", "weight": 5}, 
        {"word": "financial analysis", "weight": 5},
        {"word": "internal audits", "weight": 4}, {"word": "revenue recognition", "weight": 4},
        {"word": "cost accounting", "weight": 4}, {"word": "data entry", "weight": 3},
        {"word": "tax returns", "weight": 4}, {"word": "depreciation schedules", "weight": 3},
        {"word": "compliance monitoring", "weight": 4}, {"word": "auditing", "weight": 4},
        {"word": "financial planning", "weight": 4}, {"word": "financial statements", "weight": 4},
        {"word": "SAP FI/CO", "weight": 4}, {"word": "Oracle Financials", "weight": 4},
        {"word": "Xero", "weight": 4}, {"word": "payroll", "weight": 3},
        {"word": "regulatory compliance", "weight": 4}, {"word": "C1", "weight": 3},
        {"word": "C2", "weight": 4}, {"word": "English", "weight": 1}, 
        {"word": "Angielski", "weight": 1}
    ]
    }, 
    {
    "title": "Kierownik Sprzedaży",
    "keywords": [
        {"word": "sprzedaz", "weight": 5}, {"word": "zarzadzanie klientami", "weight": 5},
        {"word": "KPI", "weight": 5}, {"word": "negocjacje", "weight": 5},
        {"word": "CRM", "weight": 5}, {"word": "budowanie relacji", "weight": 5},
        {"word": "lead generation", "weight": 5}, {"word": "strategia sprzedazy", "weight": 5},
        {"word": "targety", "weight": 4}, {"word": "raportowanie", "weight": 4},
        {"word": "prezentacje", "weight": 4}, {"word": "prognozy sprzedazy", "weight": 4},
        {"word": "analizy", "weight": 4}, {"word": "pipeline sprzedazy", "weight": 5},
        {"word": "pozyskiwanie klientow", "weight": 5}, {"word": "zarzadzanie zespolem", "weight": 5},
        {"word": "follow-up", "weight": 4}, {"word": "utrzymanie klienta", "weight": 5},
        {"word": "marketing sprzedazowy", "weight": 4}, {"word": "wspolpraca z partnerami", "weight": 4},
        {"word": "networking", "weight": 4}, {"word": "analiza rynku", "weight": 4},
        {"word": "sprzedaz B2B", "weight": 5}, {"word": "sprzedaz B2C", "weight": 5},
        {"word": "budzetowanie", "weight": 4}, {"word": "rozwoj zespolu sprzedazowego", "weight": 5},
        {"word": "motywacja zespolu", "weight": 4}, {"word": "cross-selling", "weight": 4},
        {"word": "upselling", "weight": 4}, {"word": "analiza konkurencji", "weight": 4},
        {"word": "customer success", "weight": 4}, {"word": "sales forecasting", "weight": 4},
        {"word": "churn prevention", "weight": 4}, {"word": "AI-driven sales tools", "weight": 4},
        {"word": "hybrid sales model", "weight": 4}, {"word": "social selling", "weight": 4},
        {"word": "value-based pricing", "weight": 4}, {"word": "customer satisfaction", "weight": 4},
        {"word": "incentive programs", "weight": 4}, {"word": "market share", "weight": 4},
        {"word": "czas zarzadzania", "weight": 3}, {"word": "praca zespolowa", "weight": 3},
        {"word": "B1", "weight": 1}, {"word": "B2", "weight": 2},
        {"word": "C1", "weight": 3}, {"word": "C2", "weight": 4}, {"word": "English", "weight": 1},
        {"word": "Angielski", "weight": 1}
    ]
},
    {
    "title": "DevOps Engineer",
    "keywords": [
        {"word": "CI/CD", "weight": 5}, {"word": "Docker", "weight": 5},
        {"word": "Kubernetes", "weight": 5}, {"word": "Jenkins", "weight": 4},
        {"word": "automation", "weight": 5}, {"word": "monitoring", "weight": 3},
        {"word": "infrastructure", "weight": 5}, {"word": "AWS", "weight": 5},
        {"word": "Azure", "weight": 5}, {"word": "GCP", "weight": 5},
        {"word": "cloud", "weight": 4}, {"word": "scripts", "weight": 5},
        {"word": "Ansible", "weight": 5}, {"word": "Terraform", "weight": 5},
        {"word": "OpenShift", "weight": 4}, {"word": "DevSecOps", "weight": 4},
        {"word": "log management", "weight": 4}, {"word": "containers", "weight": 5},
        {"word": "version control", "weight": 4}, {"word": "code promotion", "weight": 4},
        {"word": "load balancing", "weight": 4}, {"word": "TDD", "weight": 5},
        {"word": "GitOps", "weight": 5}, {"word": "deployment management", "weight": 5},
        {"word": "pipelines", "weight": 4}, {"word": "observability", "weight": 4},
        {"word": "Linux", "weight": 5}, {"word": "Python", "weight": 5},
        {"word": "Bash", "weight": 5}, {"word": "Prometheus", "weight": 4},
        {"word": "Grafana", "weight": 4}, {"word": "system security", "weight": 4},
        {"word": "ELK", "weight": 4}, {"word": "microservices", "weight": 5},
        {"word": "CloudFormation", "weight": 4}, {"word": "CodePipeline", "weight": 4},
        {"word": "cost optimization", "weight": 4}, {"word": "Agile", "weight": 3},
        {"word": "team collaboration", "weight": 3}, {"word": "problem solving", "weight": 3},
        {"word": "time management", "weight": 3}, {"word": "English", "weight": 1},
        {"word": "angielski", "weight": 1}, {"word": "B1", "weight": 1},
        {"word": "B2", "weight": 2}, {"word": "C1", "weight": 3},
        {"word": "C2", "weight": 4}, {"word": "NGINX", "weight": 4},
        {"word": "Apache", "weight": 4}, {"word": "HTTP/HTTPS", "weight": 4},
        {"word": "reverse proxy", "weight": 4}, {"word": "CI/CD pipelines", "weight": 4},
        {"word": "cloud automation", "weight": 4}, {"word": "orchestration", "weight": 4},
        {"word": "scalability", "weight": 4}, {"word": "fault tolerance", "weight": 2},
        {"word": "cloud-native", "weight": 5}, {"word": "distributed systems", "weight": 3},
        {"word": "infrastructure as code", "weight": 5}, {"word": "IaC", "weight": 5},
        {"word": "serverless", "weight": 4}, {"word": "Lambda", "weight": 4},
        {"word": "S3", "weight": 4}, {"word": "EC2", "weight": 4},
        {"word": "CloudTrail", "weight": 4}, {"word": "IAM", "weight": 4},
        {"word": "debugging", "weight": 4}, {"word": "incident response", "weight": 4},
        {"word": "service mesh", "weight": 4}, {"word": "Istio", "weight": 3},
        {"word": "distributed tracing", "weight": 4}, {"word": "Jaeger", "weight": 3},
        {"word": "service discovery", "weight": 4}, {"word": "Helm", "weight": 3},
        {"word": "artifacts", "weight": 2}, {"word": "k8s", "weight": 5},
        {"word": "deployment automation", "weight": 2}, {"word": "logging", "weight": 4},
        {"word": "Zabbix", "weight": 2}, {"word": "new relic", "weight": 2},
        {"word": "postmortems", "weight": 3}, {"word": "blameless culture", "weight": 1},
        {"word": "APIs", "weight": 4}, {"word": "SLA", "weight": 4},
        {"word": "SLI", "weight": 4}, {"word": "SLO", "weight": 4}
    ]
},
    {
    "title": "Nauczyciel",
    "keywords": [
        {"word": "nauczanie", "weight": 5}, {"word": "pedagogika", "weight": 5},
        {"word": "lekcje", "weight": 4}, {"word": "programy", "weight": 4},
        {"word": "testy", "weight": 4}, {"word": "egzaminy", "weight": 4},
        {"word": "dydaktyka", "weight": 5}, {"word": "e-learning", "weight": 5},
        {"word": "zarzadzanie", "weight": 4}, {"word": "metody", "weight": 4},
        {"word": "edukacja", "weight": 5}, {"word": "oceny", "weight": 4},
        {"word": "technologia", "weight": 4}, {"word": "materialy", "weight": 4},
        {"word": "interakcja", "weight": 4}, {"word": "planowanie", "weight": 4},
        {"word": "mentoring", "weight": 4}, {"word": "kreatywnosc", "weight": 3},
        {"word": "adaptacja", "weight": 4}, {"word": "gry", "weight": 3},
        {"word": "pomoc", "weight": 3}, {"word": "komunikacja", "weight": 3},
        {"word": "zarzadzanie czasem", "weight": 3}, {"word": "Excel", "weight": 3},
        {"word": "Word", "weight": 3}, {"word": "PowerPoint", "weight": 3},
        {"word": "teaching", "weight": 5}, {"word": "lesson plans", "weight": 4},
        {"word": "grading", "weight": 4}, {"word": "classroom", "weight": 4},
        {"word": "learning", "weight": 5}, {"word": "materials", "weight": 4},
        {"word": "students", "weight": 5}, {"word": "assessments", "weight": 4},
        {"word": "innovation", "weight": 4}, {"word": "technology", "weight": 4},
        {"word": "feedback", "weight": 4}, {"word": "collaboration", "weight": 3},
        {"word": "time management", "weight": 3}, {"word": "planning", "weight": 4},
        {"word": "mentorship", "weight": 4}, {"word": "online tools", "weight": 4},
        {"word": "English", "weight": 3}, {"word": "angielski", "weight": 3},
        {"word": "B1", "weight": 1}, {"word": "B2", "weight": 2},
        {"word": "C1", "weight": 3}, {"word": "C2", "weight": 4}
        ]
    },

    {
    "title": "Specjalista Wsparcia IT",
    "keywords": [
        {"word": "wsparcie", "weight": 5}, {"word": "helpdesk", "weight": 5},
        {"word": "systemy operacyjne", "weight": 5}, {"word": "rozwiązywanie problemów", "weight": 5},
        {"word": "hardware", "weight": 5}, {"word": "software", "weight": 4},
        {"word": "serwis", "weight": 4}, {"word": "konfiguracja", "weight": 5},
        {"word": "zarządzanie urządzeniami", "weight": 4}, {"word": "dokumentacja", "weight": 4},
        {"word": "usuwanie awarii", "weight": 5}, {"word": "aktualizacje systemowe", "weight": 4},
        {"word": "instalacja oprogramowania", "weight": 5}, {"word": "ITIL", "weight": 5},
        {"word": "zarządzanie użytkownikami", "weight": 4}, {"word": "telekomunikacja", "weight": 4},
        {"word": "VPN", "weight": 4}, {"word": "sieci komputerowe", "weight": 5},
        {"word": "zabezpieczenia", "weight": 4}, {"word": "diagnostyka", "weight": 5},
        {"word": "Active Directory", "weight": 5}, {"word": "zarządzanie hasłami", "weight": 4},
        {"word": "patch management", "weight": 4}, {"word": "backup", "weight": 4},
        {"word": "zarządzanie dostępem", "weight": 4}, {"word": "Microsoft Office", "weight": 4},
        {"word": "sieci LAN/WAN", "weight": 5}, {"word": "zarządzanie incydentami", "weight": 4},
        {"word": "PowerShell", "weight": 4}, {"word": "Bash", "weight": 4},
        {"word": "zdalne wsparcie", "weight": 5}, {"word": "zdalny dostęp", "weight": 4},
        {"word": "komunikatywnosc", "weight": 3}, {"word": "czas reakcji", "weight": 4},
        {"word": "zarządzanie zadaniami", "weight": 3}, {"word": "czas realizacji", "weight": 4},
        {"word": "cyberbezpieczenstwo", "weight": 5}, {"word": "obsługa klienta", "weight": 3},
        {"word": "protokoly sieciowe", "weight": 4}, {"word": "TCP/IP", "weight": 4},
        {"word": "firewall", "weight": 4}, {"word": "monitoring systemów", "weight": 4},
        {"word": "wirtualizacja", "weight": 4}, {"word": "VMware", "weight": 4},
        {"word": "Hyper-V", "weight": 4}, {"word": "zgłoszenia serwisowe", "weight": 5},
        {"word": "angielski", "weight": 1}, {"word": "English", "weight": 1},
        {"word": "B1", "weight": 1}, {"word": "B2", "weight": 2},
        {"word": "C1", "weight": 3}, {"word": "C2", "weight": 4}
        ]
    },

    ]

    for pos in default_positions:
        if not Position.query.filter_by(title=pos["title"], is_default=True).first():
            position = Position(title=pos["title"], is_default=True)
            db.session.add(position)
            db.session.commit()

            for keyword in pos["keywords"]:
                if not Keyword.query.filter_by(word=keyword["word"], position_id=position.id).first():
                    kw = Keyword(
                        word=keyword["word"],
                        weight=keyword["weight"],
                        position_id=position.id,
                    )
                    db.session.add(kw)

    db.session.commit()

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True) 