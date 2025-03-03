from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.user import User

def save_or_update_user(user_info: dict, db: Session):
    """
    Speichert oder aktualisiert einen Benutzer, wenn er existiert.
    
    Args:
        user_info (dict): Die Benutzerdaten, die von Twitch kommen (mit Email, Display Name und Twitch ID).
        db (Session): Die Datenbank-Sitzung.

    Returns:
        user (User): Der gespeicherte oder aktualisierte Benutzer.
    """
    db_user = db.query(User).filter(User.twitch_id == user_info["id"]).first()
    if db_user:
        # Benutzerprofil aktualisieren
        db_user.email = user_info.get("email", db_user.email)
        db_user.display_name = user_info["display_name"]
        db.commit()
        db.refresh(db_user)
        return db_user
    else:
        # Neuen Benutzer erstellen
        new_user = User(
            twitch_id=user_info["id"],
            email=user_info.get("email"),
            display_name=user_info["display_name"]
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

def get_db_user(db: Session, user_db_id: int):
    """
    Holt den Benutzer aus der Datenbank anhand der user_db_id.
    """
    db_user = db.query(User).filter(User.id == user_db_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user