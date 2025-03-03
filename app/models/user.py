# /app/models/user.py

from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP, func, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database.db_connection import Base  # Base-Klasse, die für alle Modelle verwendet wird

# User Modell
class User(Base):
    '''role are like kernel level privileg user=3, admin/root = 0'''
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    twitch_id = Column(String(320), unique=True, nullable=False)
    email = Column(String(320), unique=True, nullable=True)
    display_name = Column(String(320), nullable=False)
    role = Column(Integer, default=3, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)



    clips = relationship('Clip', back_populates='creator', cascade='all, delete-orphan')

    # Rückbeziehung zu UserClipLike hinzufügen
    clip_likes = relationship('UserClipLike', back_populates='user', cascade='all, delete-orphan')
    
# UserClipLike Modell (Speicherung von Likes, IP-Adressen und dem Clip)
class UserClipLike(Base):
    __tablename__ = 'user_clip_likes'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Verweis auf die User-ID
    clip_id = Column(Integer, ForeignKey('clips.id'), nullable=False)  # Verweis auf die Clip-ID
    ip_address = Column(String(45), nullable=False)  # IP-Adresse des Benutzers
    liked_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)  # Zeitpunkt des Likes

    # Beziehungen
    user = relationship('User', back_populates='clip_likes')  # User <-> Likes Beziehung
    clip = relationship('Clip', back_populates='user_likes')  # Clip <-> Likes Beziehung

    # Unique Constraint: Jeder Benutzer kann einen Clip nur einmal mit derselben IP liken
    __table_args__ = (
        Index('ix_user_clip_ip', 'user_id', 'clip_id', 'ip_address', unique=True),
    )

