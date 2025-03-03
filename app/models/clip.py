# /app/models/clip.py
# from app.models.rating import Rating
from sqlalchemy.orm import relationship, Session
from sqlalchemy import Column, String, Integer, TIMESTAMP, func, Index, ForeignKey, Boolean
from app.database.db_connection import Base  # Base-Klasse für alle Modelle
from app.models.user import UserClipLike


PARENT_URL = "dev.miwi.tv"  # Feste URL für Embeds

class Clip(Base):
    __tablename__ = 'clips'

    id = Column(Integer, primary_key=True, index=True)
    clip_id = Column(String(100), unique=True, nullable=False)  # Speichern der Clip-ID
    broadcaster_id = Column(String(100), nullable=False)  # ID des Broadcasters
    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    game_id = Column(String(100), nullable=False)  # Game ID
    view_count = Column(Integer, default=0)  # Anzahl der Views
    created_at = Column(TIMESTAMP, nullable=False)  # Zeitpunkt der Erstellung
    likes = Column(Integer, default=0)  # Anzahl der Likes
    thumbnail_url = Column(String(255), nullable=True)  # URL des Thumbnails

    creator = relationship('User', back_populates='clips')

    # Hier die Beziehung zu UserClipLike hinzufügen
    user_likes = relationship('UserClipLike', back_populates='clip', cascade='all, delete-orphan')
    
    __table_args__ = (
        Index('ix_game_id', 'game_id'),
    )
    
    def get_embed_url(self):
        """Generiert die Embed URL"""
        if not self.clip_id:
            raise ValueError("Clip ID is missing.")
        return f"https://clips.twitch.tv/embed?clip={self.clip_id}&parent={PARENT_URL}"
    
    def calculate_likes(self, db: Session):
        """Berechnet die Anzahl der Likes für diesen Clip."""
        return db.query(func.count(UserClipLike.id)).filter(UserClipLike.clip_id == self.id).scalar()


class BlockedClips(Base):
    __tablename__ = 'blocked_clips'

    id = Column(Integer, primary_key=True, index=True)
    clip_id = Column(Integer, ForeignKey('clips.id'), nullable=False)  # Verweis auf den Clip
    status = Column(Boolean, default=True, nullable=False)  # True = blockiert, False = freigegeben
    edited_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Wer hat es geändert?
    # created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)


    # Beziehungen
    clip = relationship('Clip', backref='blocked_status')
    editor = relationship('User', backref='edited_blocks')