from sqlalchemy.orm import Session
from app.models.clip import Clip
from app.models.user import User
from datetime import datetime


def save_clip_if_not_exists(clip, broadcaster_id: str, db: Session) -> None:
    """
    Prüft, ob der Clip bereits in der Datenbank existiert. Wenn nicht, wird er gespeichert.

    Args:
        clip (dict): Die Clip-Daten von Twitch.
        broadcaster_id (str): Die ID des Broadcasters.
        db (Session): Die Datenbank-Sitzung.

    Returns:
        None
    """
    clip_id = clip["id"]
    creator_id = clip["creator_id"]
    creator_name = clip["creator_name"]

    # Überprüfe, ob der Benutzer (creator_id) bereits existiert, andernfalls erstelle ihn
    creator = db.query(User).filter(User.twitch_id == creator_id).first()
    if not creator:
        # Einen minimalen Benutzer anlegen
        new_user = User(
            twitch_id=creator_id,
            display_name=creator_name
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        creator = new_user  # Hole den frisch erstellten Benutzer

    # Überprüfe, ob der Clip bereits existiert
    existing_clip = db.query(Clip).filter(Clip.clip_id == clip_id).first()

    if not existing_clip:
        # Entferne das 'Z' aus dem ISO 8601 Format und konvertiere es in datetime
        created_at_str = clip["created_at"].rstrip('Z')  # Entferne 'Z'
        created_at = datetime.fromisoformat(created_at_str)  # Konvertiere in datetime-Objekt

        # Wenn der Clip nicht existiert, erstelle einen neuen
        new_clip = Clip(
            clip_id=clip_id,
            broadcaster_id=broadcaster_id,
            creator_id=creator.id,  # Verwende die ID des Benutzers
            game_id=clip["game_id"],
            view_count=clip["view_count"],
            likes=clip.get("likes", 0),
            created_at=created_at,
            thumbnail_url=clip.get("thumbnail_url", ""),
        )
        db.add(new_clip)
    else:
        # Wenn der Clip bereits existiert, aktualisiere die Anzahl der Aufrufe (view_count)
        existing_clip.view_count = clip["view_count"]
    db.commit()
    
    # print(f"Clip ID: {clip_id}, Thumbnail URL: {clip.get('thumbnail_url')}")

