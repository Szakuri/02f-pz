from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    session,
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from pytesseract import image_to_string
from pdf2image import convert_from_path
from PIL import Image
from docx import Document
import os


db = SQLAlchemy()


# Funkcja do tworzenia aplikacji
def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), "uploads"
    )
    app.secret_key = os.urandom(24)
    app.secret_key = os.getenv("SECRET_KEY", "domyslny_klucz")

    # Inicjalizacja bazy danych z aplikacją
    db.init_app(app)
    migrate = Migrate(app, db)

    # Importowanie modeli i tworzenie globalnych stanowisk
    with app.app_context():
        from models import Position, Keyword, Candidate, User

        db.create_all()
        create_global_positions()

    # Zdefiniowanie endpointów
    @app.route("/")
    def home():
        if "user_id" not in session:
            flash("Musisz się zalogować, aby zobaczyć tę stronę.")
            return redirect(url_for("login"))
        user = User.query.get(session["user_id"])
        return render_template("home.html", username=user.username)

    @app.route("/upload")
    def upload():
        if "user_id" not in session:
            flash("Musisz się zalogować!")
            return redirect(url_for("login"))

        user_id = session["user_id"]
        user_positions = Position.query.filter_by(user_id=user_id).all()
        global_positions = Position.query.filter_by(is_global=True).all()
        return render_template(
            "upload.html",
            user_positions=user_positions,
            global_positions=global_positions,
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

    # Endpoint: Analiza CV
    @app.route("/analyze_cv", methods=["POST"])
    def analyze_cv():
        try:
            # Pobierz dane z formularza
            name = request.form["name"]
            position_id = int(request.form["position_id"])
            file = request.files["file"]

            # Zapis pliku na serwerze
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(file_path)

            # Pobranie słów kluczowych dla stanowiska
            keywords = [
                kw.word for kw in Keyword.query.filter_by(position_id=position_id).all()
            ]

            # Odczytanie tekstu z pliku za pomocą OCR
            extracted_text = ""
            if file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                extracted_text = image_to_string(file_path)
            elif file.filename.lower().endswith('.pdf'):
                pages = convert_from_path(file_path)
                extracted_text = " ".join(image_to_string(page) for page in pages)
            elif file.filename.lower().endswith('.docx'):
                doc = Document(file_path)
                extracted_text = " ".join(paragraph.text for paragraph in doc.paragraphs)

            # Normalizacja tekstu
            normalized_text = extracted_text.lower()

            # Analiza słów kluczowych
            results = {
                keyword.lower(): normalized_text.count(keyword.lower())
                for keyword in keywords
            }

            total_score = sum(results.values())

            # Renderowanie szablonu HTML z wynikami
            return render_template("analyze_results.html", name=name, results=results, total_score=total_score)

        except Exception as e:
            return jsonify({"error": str(e)}), 500

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

            # Sprawdź, czy użytkownik istnieje
            if User.query.filter_by(username=username).first():
                flash("Nazwa użytkownika jest już zajęta!")
                return redirect(url_for("register"))

            # Utwórz użytkownika
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
                session["user_id"] = user.id  # Ustawiamy ID użytkownika w sesji
                flash("Zalogowano pomyślnie!")
                return redirect(url_for("home"))  # Przekierowanie na stronę główną
            else:
                flash("Nieprawidłowa nazwa użytkownika lub hasło.", "error")
                return redirect(url_for("login"))  # Powrót na stronę logowania

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

    @app.route("/manage_global_positions", methods=["GET", "POST"])
    def manage_global_positions():
        if request.method == "POST":
            title = request.form["title"]
            keywords = request.form["keywords"].split(",")

            existing_position = Position.query.filter_by(
                title=title, is_global=True
            ).first()
            if existing_position:
                flash("Takie stanowisko już istnieje!")
                return redirect(url_for("manage_global_positions"))

            new_position = Position(title=title, is_global=True)
            db.session.add(new_position)
            db.session.commit()

            for keyword in keywords:
                new_keyword = Keyword(word=keyword.strip(), position_id=new_position.id)
                db.session.add(new_keyword)

            db.session.commit()
            flash("Stanowisko globalne zostało dodane!")
            return redirect(url_for("manage_global_positions"))

        global_positions = Position.query.filter_by(is_global=True).all()
        return render_template(
            "manage_global_positions.html", global_positions=global_positions
        )

    return app


def create_global_positions():
    from models import Position, Keyword

    global_positions = [
        {
            "title": "Programista",
            "keywords": [
                "programowanie",
                "Python",
                "Java",
                "JavaScript",
                "C#",
                "SQL",
                "bazy danych",
                "API",
                "framework",
                "debugowanie",
                "kodowanie",
                "systemy operacyjne",
                "integracja",
                "automatyzacja",
                "scrum",
                "agile",
                "testing",
                "backend",
                "frontend",
                "narzędzia CI/CD",
                "Git",
                "Docker",
                "Linux",
                "Windows",
                "architektura systemów",
                "analityka",
                "optymalizacja",
                "REST",
                "SOAP",
                "mikroserwisy",
                "bezpieczeństwo IT",
                "refaktoryzacja",
                "chmura",
                "Azure",
                "AWS",
                "GCP",
                "DevOps",
            ],
        },
        {
            "title": "Analityk Danych",
            "keywords": [
                "dane",
                "Excel",
                "SQL",
                "analizy",
                "wizualizacja",
                "Tableau",
                "Power BI",
                "statystyka",
                "Python",
                "R",
                "modele predykcyjne",
                "algorytmy",
                "analiza danych",
                "przetwarzanie danych",
                "ETL",
                "dashboard",
                "raporty",
                "Big Data",
                "Hadoop",
                "Spark",
                "analityka biznesowa",
                "insighty",
                "dane sprzedażowe",
                "prognozowanie",
                "optymalizacja",
                "bazy danych",
                "machine learning",
                "analiza rynku",
                "czyszczenie danych",
                "Google Analytics",
                "KPIs",
                "modelowanie danych",
            ],
        },
        {
            "title": "Kierownik Projektu",
            "keywords": [
                "zarządzanie projektami",
                "harmonogramy",
                "budżet",
                "agile",
                "scrum",
                "waterfall",
                "zarządzanie ryzykiem",
                "priorytetyzacja",
                "planowanie",
                "komunikacja",
                "zarządzanie zespołem",
                "stakeholderzy",
                "analiza wymagań",
                "cele projektu",
                "raportowanie",
                "monitoring",
                "zarządzanie czasem",
                "zarządzanie zmianą",
                "leadership",
                "efektywność",
                "metodologia",
                "stand-up",
                "roadmap",
                "narzędzia PM",
                "Jira",
                "Asana",
                "MS Project",
                "zarządzanie zadaniami",
            ],
        },
        {
            "title": "Grafik",
            "keywords": [
                "projektowanie graficzne",
                "Adobe Photoshop",
                "Illustrator",
                "InDesign",
                "Canva",
                "projektowanie logo",
                "typografia",
                "paleta kolorów",
                "branding",
                "layout",
                "infografiki",
                "kreatywność",
                "ilustracje",
                "UX/UI",
                "projektowanie interfejsów",
                "responsywność",
                "druk",
                "składy",
                "grafika wektorowa",
                "animacje",
                "mockupy",
                "wizualizacje",
                "wireframes",
                "projektowanie banerów",
                "grafika 3D",
                "narzędzia graficzne",
            ],
        },
        {
            "title": "Copywriter",
            "keywords": [
                "SEO",
                "optymalizacja treści",
                "copywriting",
                "marketing treści",
                "artykuły",
                "blogi",
                "storytelling",
                "kreatywne pisanie",
                "redagowanie",
                "social media",
                "CTA",
                "reklama",
                "edytowanie",
                "język",
                "treść",
                "analiza konkurencji",
                "Google Analytics",
                "targetowanie",
                "kampanie marketingowe",
                "e-mail marketing",
                "UX writing",
                "optymalizacja słów kluczowych",
                "analiza odbiorców",
            ],
        },
        {
            "title": "Specjalista ds. Marketingu Cyfrowego",
            "keywords": [
                "marketing cyfrowy",
                "SEO",
                "SEM",
                "Google Ads",
                "Facebook Ads",
                "social media",
                "kampanie",
                "reklama",
                "targetowanie",
                "optymalizacja",
                "Google Analytics",
                "email marketing",
                "automatyzacja marketingu",
                "content marketing",
                "remarketing",
                "KPI",
                "lead generation",
                "konwersje",
                "budżet reklamowy",
                "strategia marketingowa",
            ],
        },
        {
            "title": "Administrator Sieci",
            "keywords": [
                "sieci komputerowe",
                "protokoły",
                "TCP/IP",
                "DNS",
                "DHCP",
                "routing",
                "VPN",
                "bezpieczeństwo",
                "firewalle",
                "zarządzanie siecią",
                "konfiguracja",
                "LAN",
                "WAN",
                "zarządzanie serwerami",
                "backup",
                "monitoring sieci",
                "rozwiązywanie problemów",
                "load balancing",
                "NAT",
                "VLAN",
                "QoS",
                "SNMP",
                "Wi-Fi",
                "urządzenia sieciowe",
                "Cisco",
                "Juniper",
                "Mikrotik",
                "przełączniki",
                "routery",
                "topologia sieci",
                "systemy redundantne",
                "HA (High Availability)",
                "IPSec",
                "Ethernet",
                "802.11",
                "MPLS",
                "IP",
                "IPv6",
                "zarządzanie dostępem",
                "kontrola przepływu",
                "proxy",
                "IDS/IPS",
                "SIEM",
                "zarządzanie urządzeniami",
                "PowerShell",
                "Bash",
                "automatyzacja",
                "monitorowanie ruchu",
            ],
        },
        {
            "title": "Specjalista HR",
            "keywords": [
                "rekrutacja",
                "onboarding",
                "rozwój pracowników",
                "rozmowy kwalifikacyjne",
                "ocena pracowników",
                "szkolenia",
                "employer branding",
                "zarządzanie talentami",
                "benefity",
                "kultura organizacyjna",
                "motywacja",
                "zarządzanie konfliktami",
                "HRIS",
                "umowy",
                "rozwój zawodowy",
                "rotacja pracowników",
                "strategia HR",
                "planowanie zatrudnienia",
                "headhunting",
                "rekrutacja IT",
                "analiza kompetencji",
                "zaangażowanie pracowników",
                "raporty HR",
                "wskaźniki KPI",
                "prawo pracy",
                "wynagrodzenie",
                "wyniki",
                "programy motywacyjne",
                "feedback",
                "rozwój liderów",
                "harmonogramy",
                "polityka firmy",
            ],
        },
        {
            "title": "Księgowy",
            "keywords": [
                "rachunkowość",
                "księgi rachunkowe",
                "podatki",
                "VAT",
                "PIT",
                "CIT",
                "bilans",
                "sprawozdania finansowe",
                "budżetowanie",
                "kontrola kosztów",
                "SAP",
                "audyt",
                "Excel",
                "raportowanie",
                "analiza kosztów",
                "rozliczenia",
                "fakturowanie",
                "amortyzacja",
                "prognozowanie finansowe",
                "zgodność podatkowa",
                "kontrole wewnętrzne",
                "analiza wydatków",
                "bilansowanie",
                "systemy ERP",
                "Cash Flow",
                "zobowiązania",
                "należności",
                "księgowość zarządcza",
                "analiza finansowa",
                "zgodność regulacyjna",
                "optymalizacja podatkowa",
                "VAT-UE",
                "koszt jednostkowy",
            ],
        },
        {
            "title": "Inżynier Mechanik",
            "keywords": [
                "projektowanie",
                "CAD",
                "SolidWorks",
                "inżynieria",
                "mechanika",
                "materiały",
                "modelowanie 3D",
                "rysunki techniczne",
                "analiza FEM",
                "automatyka",
                "testowanie",
                "konserwacja",
                "prototypowanie",
                "systemy mechaniczne",
                "tolerancje",
                "termodynamika",
                "dynamika",
                "projektowanie urządzeń",
                "analiza zmęczeniowa",
                "maszyny przemysłowe",
                "technologia produkcji",
                "kinematyka",
                "statyka",
                "inżynieria procesowa",
                "systemy hydrauliczne",
                "spawalnictwo",
                "mechanika płynów",
                "pompy",
                "przekładnie",
                "analiza naprężeń",
                "symulacja komputerowa",
            ],
        },
        {
            "title": "Inżynier Budownictwa",
            "keywords": [
                "projektowanie",
                "AutoCAD",
                "Revit",
                "budowa",
                "kosztorysy",
                "struktury",
                "inżynieria lądowa",
                "analiza",
                "architektura",
                "nadzór",
                "planowanie",
                "BIM",
                "projekty budowlane",
                "konstrukcje stalowe",
                "betony",
                "rysunki architektoniczne",
                "geotechnika",
                "instalacje budowlane",
                "zarządzanie budową",
                "dokumentacja techniczna",
                "wytrzymałość materiałów",
                "pomiary",
                "mosty",
                "drogi",
                "budynki wielkopowierzchniowe",
                "budynki mieszkalne",
                "inspekcje budowlane",
            ],
        },
        {
            "title": "Kierownik Sprzedaży",
            "keywords": [
                "sprzedaż",
                "zarządzanie klientami",
                "KPI",
                "negocjacje",
                "CRM",
                "budowanie relacji",
                "lead generation",
                "strategia sprzedaży",
                "targety",
                "raportowanie",
                "prezentacje",
                "prognozy sprzedaży",
                "analizy",
                "pipeline sprzedaży",
                "pozyskiwanie klientów",
                "zarządzanie zespołem",
                "follow-up",
                "utrzymanie klienta",
                "marketing sprzedażowy",
                "współpraca z partnerami",
                "networking",
            ],
        },
        {
            "title": "DevOps Engineer",
            "keywords": [
                "CI/CD",
                "Docker",
                "Kubernetes",
                "Jenkins",
                "automatyzacja",
                "monitoring",
                "infrastruktura",
                "AWS",
                "Azure",
                "chmura",
                "skrypty",
                "Ansible",
                "Terraform",
                "OpenShift",
                "bezpieczeństwo DevOps",
                "zarządzanie logami",
                "systemy kontenerowe",
                "zarządzanie wersjami",
                "promowanie kodu",
                "load balancing",
                "TDD",
                "GitOps",
                "zarządzanie wdrożeniami",
                "pipeline",
                "observability",
            ],
        },
        {
            "title": "Nauczyciel",
            "keywords": [
                "nauczanie",
                "program nauczania",
                "lekcje",
                "pedagogika",
                "materiały",
                "motywacja",
                "oceny",
                "edukacja",
                "testy",
                "egzaminy",
                "dydaktyka",
                "metody nauczania",
                "e-learning",
                "interakcja z uczniami",
                "zarządzanie klasą",
                "innowacje edukacyjne",
                "technologia edukacyjna",
            ],
        },
        {
            "title": "Specjalista Wsparcia IT",
            "keywords": [
                "wsparcie",
                "helpdesk",
                "systemy operacyjne",
                "rozwiązywanie problemów",
                "hardware",
                "software",
                "serwis",
                "konfiguracja",
                "zarządzanie urządzeniami",
                "dokumentacja",
                "usuwanie awarii",
                "aktualizacje systemowe",
                "instalacja oprogramowania",
                "ITIL",
                "narzędzia wsparcia",
                "telefoniczne wsparcie techniczne",
                "zarządzanie użytkownikami",
            ],
        },
    ]

    for position_data in global_positions:
        existing_position = Position.query.filter_by(
            title=position_data["title"], is_global=True
        ).first()
        if not existing_position:
            new_position = Position(title=position_data["title"], is_global=True)
            db.session.add(new_position)
            db.session.commit()
            for keyword in position_data["keywords"]:
                new_keyword = Keyword(word=keyword, position_id=new_position.id)
                db.session.add(new_keyword)
            db.session.commit()


# Uruchamianie aplikacji
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
