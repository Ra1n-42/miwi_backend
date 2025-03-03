from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP, func, ForeignKey
from app.database.db_connection import Base
from sqlalchemy.orm import relationship



class User(Base):
    '''role are like kernel level privileg user=3, admin/root = 0'''
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    twitch_id = Column(String(320), unique=True, nullable=False)
    email = Column(String(320), unique=True, nullable=False)
    display_name = Column(String(320), nullable=False)
    role = Column(Integer, default=3, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)

    # Beziehung zur UserIpLog-Tabelle
    ip_logs = relationship('UserIpLog', back_populates='user')

# Tabelle zum Speichern von IP-Adressen
class UserIpLog(Base):
    __tablename__ = 'user_ip_logs'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Verweis auf den Benutzer
    ip_address = Column(String(45), nullable=False)  # IP-Adresse des Benutzers (IPv4 oder IPv6)
    timestamp = Column(TIMESTAMP, server_default=func.now(), nullable=False)  # Zeitpunkt des Loggings

    # Beziehung zum User
    user = relationship('User', back_populates='ip_logs')