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
import os

# Inicjalizacja bazy danych
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

    # Importowanie modeli
    with app.app_context():
        from models import Position, Keyword, Candidate, User

        db.create_all()  # Tworzy tabele, jeśli jeszcze nie istnieją

    # Zdefiniowanie endpointów
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
        positions = Position.query.filter_by(user_id=user_id).all()
        return render_template("upload.html", positions=positions)

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

            # Odczytanie tekstu z pliku PDF za pomocą OCR
            try:
                pages = convert_from_path(file_path)
                extracted_text = " ".join(image_to_string(page) for page in pages)
            except Exception as e:
                return (
                    jsonify(
                        {"error": f"Błąd podczas wyodrębniania tekstu z PDF: {str(e)}"}
                    ),
                    500,
                )

            # Normalizacja tekstu
            normalized_text = extracted_text.lower()

            # Analiza słów kluczowych
            results = {
                keyword.lower(): normalized_text.count(keyword.lower())
                for keyword in keywords
            }

            # Zapis kandydata i wyników do bazy danych
            candidate = Candidate(
                name=name, cv_text=extracted_text, position_id=position_id
            )
            db.session.add(candidate)
            db.session.commit()

            return (
                jsonify(
                    {"message": "Analiza zakończona pomyślnie", "results": results}
                ),
                200,
            )

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

    return app


# Uruchamianie aplikacji
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
