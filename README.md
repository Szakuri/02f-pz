# Projekt_Zespolowy_02F
Projekt tworzony w zespole pięcioosobowym, w celu zaliczenia przedmiotu na studiach.

# Automatyczna Analiza CV i Rekomendacja Kandydatów

## Opis projektu
Aplikacja umożliwia automatyczną analizę CV kandydatów i rekomendację najlepszych na podstawie wymagań określonych stanowisk. Jej głównym celem jest zautomatyzowanie procesu rekrutacji poprzez wykorzystanie technik przetwarzania języka naturalnego (NLP).

**Aplikacja została wdrożona na platformie Heroku.** W obecnej wersji system nie wykorzystuje REST API – frontend i backend są zintegrowane w ramach frameworka Flask.

Projekt został opracowany w ramach zespołowego zadania na studiach przez pięcioosobowy zespół.

---

## Funkcjonalności
- **Przesyłanie CV**: Użytkownicy mogą przesyłać pliki PDF z CV do analizy.
- **Analiza CV**:
  - Wyodrębnianie kluczowych informacji, takich jak:
    - Imię i nazwisko,
    - Adres e-mail,
    - Numer telefonu,
- **Dopasowanie do stanowisk**: Na podstawie słów kluczowych przypisanych do stanowiska system generuje punktację dla CV.
- **Zarządzanie stanowiskami**:
  - Dodawanie nowych stanowisk i przypisywanie do nich słów kluczowych z wagami.
  - Edytowanie i usuwanie stanowisk.
- **Ranking kandydatów**: Automatyczne generowanie listy kandydatów uszeregowanych według dopasowania do wybranego stanowiska.
- **Podgląd i pobieranie CV**: Możliwość przeglądania i pobierania przesłanych plików CV.
- **Rejestracja i logowanie użytkowników**: Obsługa kont użytkowników z zabezpieczeniem hasłem.

---

## Technologie i języki

### **Języki programowania**
- **Python**: Główny język backendu, wykorzystany do przetwarzania danych, analizy NLP oraz integracji z bazą danych.
- **HTML**: Do budowy szablonów stron.
- **CSS**: Stylizacja interfejsu użytkownika.
- **JavaScript**: Obsługa dynamicznych elementów na stronach.

### **Frameworki i biblioteki**
- **Flask**: Framework webowy do obsługi backendu i komunikacji frontend-backend.
- **Flask-SQLAlchemy**: ORM do zarządzania bazą danych.
- **Flask-Migrate**: Obsługa migracji schematu bazy danych.
- **spaCy**: Biblioteka NLP do analizy języka naturalnego.
- **pytesseract**: Narzędzie OCR do ekstrakcji tekstu z plików PDF.
- **pdf2image**: Konwersja plików PDF na obrazy w celu ułatwienia analizy OCR.
- **Bootstrap** (opcjonalnie): Możliwość użycia do poprawy responsywności interfejsu użytkownika.

### **Baza danych**
- **SQLite**: Lokalna baza danych używana do przechowywania danych w aplikacji.
- **PostgreSQL**: Zalecana baza danych dla środowiska produkcyjnego (możliwość łatwego wdrożenia na Heroku).

### **Infrastruktura i narzędzia**
- **Heroku**: Platforma chmurowa do wdrażania aplikacji.
- **GitHub**: Kontrola wersji i współpraca zespołowa.
- **Docker**: Możliwość konteneryzacji aplikacji.
- **Tesseract OCR**: Narzędzie zewnętrzne do przetwarzania tekstu z obrazów.
- **Pipenv** lub **virtualenv**: Zarządzanie środowiskiem wirtualnym Python.

---

## Architektura aplikacji
Aplikacja działa jako aplikacja monolityczna, łącząc funkcje frontendowe i backendowe za pomocą frameworka Flask.

### Moduły:
- **Backend**:
  - Obsługa logiki aplikacji (analiza NLP, dopasowanie kandydatów).
  - Zarządzanie bazą danych i przetwarzaniem plików PDF.
- **Frontend**:
  - Renderowanie stron za pomocą szablonów HTML.
  - Obsługa formularzy przesyłania plików i zarządzania stanowiskami.

---
