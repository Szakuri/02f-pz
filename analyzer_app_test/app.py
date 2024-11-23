from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import pytesseract
from pdf2image import convert_from_path
import os
import re
from collections import Counter

# Inicjalizacja aplikacji Flask i konfiguracja bazy danych
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"  # Baza danych SQLite
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


# Modele bazy danych
class Position(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    keywords = db.relationship("Keyword", backref="position", lazy=True)


class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(50), nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey("position.id"), nullable=False)


class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cv_text = db.Column(db.Text, nullable=False)
    position_id = db.Column(db.Integer, db.ForeignKey("position.id"), nullable=False)


# Endpoint domyślny dla sprawdzenia działania serwera
@app.route("/")
def home():
    return "Flask server is running."


# Endpoint do dodawania stanowiska i słów kluczowych
@app.route("/positions", methods=["POST"])
def add_positions():
    data = request.json
    if isinstance(data, list):  # Sprawdza, czy dane są tablicą
        for item in data:
            position = Position(title=item["title"])
            db.session.add(position)
            db.session.commit()

            for word in item["keywords"]:
                keyword = Keyword(word=word, position_id=position.id)
                db.session.add(keyword)

        db.session.commit()
        return jsonify({"message": "Positions and keywords added successfully"}), 201
    else:
        # W przypadku pojedynczego obiektu JSON
        position = Position(title=data["title"])
        db.session.add(position)
        db.session.commit()

        for word in data["keywords"]:
            keyword = Keyword(word=word, position_id=position.id)
            db.session.add(keyword)

        db.session.commit()
        return jsonify({"message": "Position and keywords added successfully"}), 201


# Endpoint do analizy CV
@app.route("/analyze_cv", methods=["POST"])
def analyze_cv():
    data = request.json
    candidate_name = data["name"]
    file_path = data["file_path"]
    position_id = data["position_id"]

    # Ekstrakcja tekstu z PDF
    try:
        pages = convert_from_path(file_path, 300)
        cv_text = "\n".join(pytesseract.image_to_string(page) for page in pages)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Przypisanie słów kluczowych do danego stanowiska
    keywords = [
        kw.word for kw in Keyword.query.filter_by(position_id=position_id).all()
    ]

    # Dodaj print do sprawdzenia słów kluczowych
    print("Keywords for position_id", position_id, ":", keywords)

    # Analiza słów kluczowych
    normalized_text = re.sub(r"[^a-zA-Z0-9\s]", "", cv_text.lower())
    words = normalized_text.split()
    word_counts = Counter(words)
    keyword_counts = {
        keyword: word_counts.get(keyword.lower(), 0) for keyword in keywords
    }
    total_score = sum(keyword_counts.values())

    # Zapis wyników analizy w bazie danych
    candidate = Candidate(name=candidate_name, cv_text=cv_text, position_id=position_id)
    db.session.add(candidate)
    db.session.commit()

    return (
        jsonify(
            {
                "candidate_name": candidate_name,
                "keyword_counts": keyword_counts,
                "total_score": total_score,
            }
        ),
        200,
    )


# Inicjalizacja bazy danych
with app.app_context():
    db.create_all()

# Uruchomienie serwera
if __name__ == "__main__":
    app.run(debug=True)
