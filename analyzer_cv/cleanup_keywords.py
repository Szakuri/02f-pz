from app import create_app, db
from models import Position, Keyword

app = create_app()

with app.app_context():
    global_position_ids = [pos.id for pos in Position.query.filter_by(is_default=True).all()]

    Keyword.query.filter(~Keyword.position_id.in_(global_position_ids)).delete(synchronize_session=False)

    db.session.commit()

    print("Nieaktualne słowa kluczowe zostały usunięte.")
