from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Date, Text
from sqlalchemy.orm import relationship
from app.database.db_connection import Base

class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)  # Titel sollten prägnant sein
    description = Column(Text, nullable=True)    # Unbegrenzte Länge für Beschreibungen
    created_at = Column(Date, nullable=False)
    challange_end = Column(Date, nullable=False)

    # Cascade delete sorgt dafür, dass alle zugehörigen Sections gelöscht werden, wenn die Challenge gelöscht wird
    sections = relationship(
        "Section",
        back_populates="challenge",
        cascade="all, delete-orphan",  # Löscht alle zugehörigen Sections, wenn die Challenge gelöscht wird
        passive_deletes=True           # Aktiviert das Löschen in der Datenbank, ohne zusätzliche Abfragen
    )

class Section(Base):
    __tablename__ = "challenge_sections"

    id = Column(Integer, primary_key=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False)  # Verweis auf die Challenge
    title = Column(Text, nullable=False)  # Sektions-Titel sollten ebenfalls prägnant sein

    # Cascade delete sorgt dafür, dass alle zugehörigen Items gelöscht werden, wenn die Section gelöscht wird
    items = relationship(
        "Item",
        back_populates="section",
        cascade="all, delete-orphan",  # Löscht alle zugehörigen Items, wenn die Section gelöscht wird
        passive_deletes=True           # Aktiviert das Löschen in der Datenbank, ohne zusätzliche Abfragen
    )
    challenge = relationship("Challenge", back_populates="sections")

class Item(Base):
    __tablename__ = "challenge_items"

    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("challenge_sections.id", ondelete="CASCADE"), nullable=False)  # Verweis auf die Section
    text = Column(Text, nullable=False)          # Text statt String für längere Aufgabenbeschreibungen
    completed = Column(Boolean, nullable=False, default=False)

    # Cascade delete sorgt dafür, dass alle zugehörigen SubChallenges gelöscht werden, wenn das Item gelöscht wird
    subchallenges = relationship(
        "SubChallenge",
        back_populates="item",
        cascade="all, delete-orphan",  # Löscht alle zugehörigen SubChallenges, wenn das Item gelöscht wird
        passive_deletes=True           # Aktiviert das Löschen in der Datenbank, ohne zusätzliche Abfragen
    )

    section = relationship("Section", back_populates="items")

class SubChallenge(Base):
    __tablename__ = "subchallenges"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)          # Text statt String für längere Unterziel-Beschreibungen
    completed = Column(Boolean, default=False)
    item_id = Column(Integer, ForeignKey("challenge_items.id", ondelete="CASCADE"), nullable=False)  # Verweis auf das zugehörige Item

    item = relationship("Item", back_populates="subchallenges")