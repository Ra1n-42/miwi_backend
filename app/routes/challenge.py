from fastapi import APIRouter, Depends, HTTPException
from app.routes.user import get_current_user
from app.database.db_connection import get_db
from sqlalchemy.orm import Session, joinedload
from app.user_func import get_db_user
from app.models.challanges import Challenge, Section, Item, SubChallenge
from pydantic import BaseModel, field_validator, Field
from typing import List, Optional
from datetime import datetime
from app.routes.user import check_access_by_role
from app.utils.time_tracking_logger import log_request_duration, logger
from sqlalchemy import update

class SubItemBase(BaseModel):
    id: Optional[str] = None
    text: str = Field(..., min_length=1)
    completed: bool = Field(default=False)

class ItemBase(BaseModel):
    id: Optional[str] = None
    text: str = Field(..., min_length=1)
    completed: bool = Field(default=False)
    subchallenges: List[SubItemBase] = Field(default_factory=list)

class SectionBase(BaseModel):
    id: Optional[str] = None
    title: str = Field(..., min_length=1)
    items: List[ItemBase] = Field(default_factory=list)

class HeaderBase(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(default="")
    created_at: str
    challange_end: str

    # @field_validator('created_at', 'challange_end')
    # @classmethod
    # def validate_dates(cls, v: str) -> str:
    #     # Akzeptiere beide Formate: DD-MM-YYYY oder YYYY-MM-DD
    #     for date_format in ('%d-%m-%Y', '%Y-%m-%d'):
    #         try:
    #             parsed_date = datetime.strptime(v, date_format).date()
    #             return parsed_date.strftime('%Y-%m-%d')  # Speichere als YYYY-MM-DD für MySQL
    #         except ValueError:
    #             continue
    #     raise ValueError('Ungültiges Datumsformat. Bitte DD-MM-YYYY oder YYYY-MM-DD verwenden')
    @field_validator('created_at', 'challange_end')
    @classmethod
    def validate_dates(cls, v: str) -> str:
        for date_format in ('%d-%m-%Y', '%Y-%m-%d'):
            try:
                parsed_date = datetime.strptime(v, date_format).date()
                return parsed_date.strftime('%Y-%m-%d')  # Speichere als YYYY-MM-DD für PostgreSQL
            except ValueError:
                continue
        raise ValueError('Ungültiges Datumsformat. Bitte DD-MM-YYYY oder YYYY-MM-DD verwenden')



    @field_validator('created_at', 'challange_end')
    @classmethod
    def validate_date_range(cls, v: str, info) -> str:
        # Umwandlung der Datumseingaben zu datetime.date
        current_date = datetime.strptime(v, '%Y-%m-%d').date()
        
        if info.field_name == 'challange_end':
            created_at = info.data.get('created_at')
            if created_at:
                created_date = datetime.strptime(created_at, '%Y-%m-%d').date()
                if current_date < created_date:
                    raise ValueError('Das Enddatum muss nach dem Erstellungsdatum liegen')
        
        return v

class ChallengeCreate(BaseModel):
    header: HeaderBase
    sections: List[SectionBase] = Field(default_factory=list)

    @field_validator('sections')
    @classmethod
    def validate_sections_not_empty(cls, v: List[SectionBase]) -> List[SectionBase]:
        if not v:
            raise ValueError('Mindestens eine Sektion muss vorhanden sein')
        return v

# Response Models ohne strikte Validierung
class SubItemResponse(BaseModel):
    id: Optional[str] = None
    text: str
    completed: bool = False

class ItemResponse(BaseModel):
    id: Optional[str] = None
    text: str
    completed: bool
    subchallenges: List[SubItemResponse] = []

class SectionResponse(BaseModel):
    id: Optional[str] = None
    title: str
    items: List[ItemResponse] = []

class HeaderResponse(BaseModel):
    title: str
    description: str
    created_at: str
    challange_end: str

class ChallengeResponse(BaseModel):
    id: str
    header: HeaderResponse
    sections: List[SectionResponse] = []

router = APIRouter(
    prefix="/challenge",
    tags=["challenge"],
    responses={404: {"description": "Not found"}},
)

# ➕ Challenge erstellen
@router.post("/create")
@log_request_duration
async def create_challenge(
    challenge: ChallengeCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    db_user = get_db_user(db, user_db_id=current_user.get("user_id"))
    check_access_by_role(db_user.role, [0, 1, 2])
    try:
        logger.info(f"Versuche Challenge zu erstellen: {challenge}")
        # Challenge erstellen mit den konvertierten Daten
        # new_challenge = Challenge(
        #     title=challenge.header.title,
        #     description=challenge.header.description,
        #     created_at=datetime.strptime(challenge.header.created_at, '%Y-%m-%d').date(),
        #     challange_end=datetime.strptime(challenge.header.challange_end, '%Y-%m-%d').date()
        # )
        new_challenge = Challenge(
            title=challenge.header.title,
            description=challenge.header.description,
            created_at=datetime.strptime(challenge.header.created_at, '%Y-%m-%d').date(),
            challange_end=datetime.strptime(challenge.header.challange_end, '%Y-%m-%d').date()
        )
        db.add(new_challenge)
        db.flush()  # ID generieren

        # Sections mit Items und Subchallenges erstellen
        for section_data in challenge.sections:
            section = Section(
                challenge_id=new_challenge.id,
                title=section_data.title
            )
            db.add(section)
            db.flush()

            for item_data in section_data.items:
                item = Item(
                    section_id=section.id,
                    text=item_data.text,
                    completed=item_data.completed
                )
                db.add(item)
                db.flush()

                for sub_data in item_data.subchallenges:
                    sub = SubChallenge(
                        item_id=item.id,
                        text=sub_data.text,
                        completed=sub_data.completed if hasattr(sub_data, 'completed') else False
                    )
                    db.add(sub)
        
        db.commit()
        return {
            "message": "Challenge erfolgreich erstellt",
            "challenge_id": new_challenge.id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Fehler beim Erstellen der Challenge: {str(e)}"
        )

# 📄 Alle Challenges abrufen
@router.get("/all", response_model=List[ChallengeResponse])
async def get_all_challenges(db: Session = Depends(get_db)):
    try:
        challenges = db.query(Challenge).options(
            joinedload(Challenge.sections)
            .joinedload(Section.items)
            .joinedload(Item.subchallenges)
        ).all()
        if not challenges:
            raise HTTPException(status_code=404, detail="Keine Challenges gefunden")

        return [
            ChallengeResponse(
                id=str(challenge.id),
                header=HeaderResponse(
                    title=challenge.title,
                    description=challenge.description,
                    created_at=challenge.created_at.strftime('%Y-%m-%d'),
                    challange_end=challenge.challange_end.strftime('%Y-%m-%d')
                ),
                sections=[
                    SectionResponse(
                        id=str(section.id),
                        title=section.title,
                        items=[
                            ItemResponse(
                                id=str(item.id),
                                text=item.text,
                                completed=item.completed,
                                subchallenges=[
                                    SubItemResponse(
                                        id=str(sub.id),
                                        text=sub.text,
                                        completed=sub.completed
                                    )
                                    for sub in item.subchallenges
                                ]
                            )
                            for item in section.items
                        ]
                    )
                    for section in challenge.sections
                ]
            )
            for challenge in challenges
        ]
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Fehler beim Abrufen der Challenges: {str(e)}"
        )
class ChallengePageResponse(BaseModel):
    completed: bool

@router.put("/task/{task_id}")
async def update_task(
    task_id: int,
    taskdata: ChallengePageResponse,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    logger.info(f"/task/{task_id}: {current_user['display_name']} -> {taskdata.completed}[TRY]")
    db_user = get_db_user(db, user_db_id=current_user.get("user_id"))
    logger.info(f"/task/{task_id}: {current_user['display_name']} -> [USERFOUND]")
    check_access_by_role(db_user.role, [0, 1, 2])
    logger.info(f"/task/{task_id}: {current_user['display_name']} -> {taskdata.completed}[check_access_by_role -> PASS]")
    try:
        result = db.execute(
            update(Item)
            .where(Item.id == task_id)
            .values(completed=taskdata.completed)
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Subchallenge nicht gefunden")

        db.commit()
        logger.info(f"/task/{task_id} {current_user["display_name"]} -> {taskdata.completed}")
        return {"message": "Aufgabe erfolgreich aktualisiert"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Fehler beim Aktualisieren der Aufgbe: {str(e)}")



@router.put("/subchallenge/{subchallenge_id}")
async def update_subchallenge(
    subchallenge_id: int,
    subtaskdata: ChallengePageResponse,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Aktualisiert den 'completed'-Status einer Subchallenge.

    Args:
        subchallenge_id (int): Die ID der Subchallenge, die aktualisiert werden soll.
        completed (bool): Der neue 'completed'-Status (True oder False).
        db (Session, optional): Die Datenbank-Session. Defaults to Depends(get_db).
        current_user (dict, optional): Die Informationen des aktuellen Benutzers. Defaults to Depends(get_current_user).

    Raises:
        HTTPException: 400, wenn ein Fehler beim Aktualisieren der Subchallenge auftritt.
        HTTPException: 404, wenn die Subchallenge nicht gefunden wird.

    Returns:
        dict: Eine Nachricht, die bestätigt, dass die Subchallenge erfolgreich aktualisiert wurde.
    """
    db_user = get_db_user(db, user_db_id=current_user.get("user_id"))
    check_access_by_role(db_user.role, [0, 1, 2])

    try:
        result = db.execute(
            update(SubChallenge)
            .where(SubChallenge.id == subchallenge_id)
            .values(completed=subtaskdata.completed)
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Subchallenge nicht gefunden")

        db.commit()
        logger.info(f"/subchallenge/{subchallenge_id} {current_user["display_name"]} -> {subtaskdata.completed}")
        return {"message": "Subchallenge erfolgreich aktualisiert"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Fehler beim Aktualisieren der Subchallenge: {str(e)}")



# 🔄 Challenge aktualisieren
@router.put("/update/{challenge_id}")
async def update_challenge(
    challenge_id: int,
    challenge: ChallengeCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    db_user = get_db_user(db, user_db_id=current_user.get("user_id"))
    check_access_by_role(db_user.role, [0, 1, 2])

    # Challenge mit allen Beziehungen laden
    db_challenge = db.query(Challenge).options(
        joinedload(Challenge.sections)
        .joinedload(Section.items)
        .joinedload(Item.subchallenges)
    ).filter(Challenge.id == challenge_id).first()

    if not db_challenge:
        raise HTTPException(status_code=404, detail="Challenge nicht gefunden")

    try:
        # Header aktualisieren mit den konvertierten Daten
        db_challenge.title = challenge.header.title
        db_challenge.description = challenge.header.description
        db_challenge.created_at = datetime.strptime(challenge.header.created_at, '%Y-%m-%d').date()
        db_challenge.challange_end = datetime.strptime(challenge.header.challange_end, '%Y-%m-%d').date()

        # Bestehende Sections löschen (cascade delete wird automatisch angewendet)
        for section in db_challenge.sections:
            db.delete(section)
        
        # Neue Sections erstellen
        for section_data in challenge.sections:
            new_section = Section(
                challenge_id=db_challenge.id,
                title=section_data.title
            )
            db.add(new_section)
            db.flush()

            # Items erstellen
            for item_data in section_data.items:
                new_item = Item(
                    section_id=new_section.id,
                    text=item_data.text,
                    completed=item_data.completed
                )
                db.add(new_item)
                db.flush()

                # Subchallenges erstellen
                for sub_data in item_data.subchallenges:
                    new_sub = SubChallenge(
                        item_id=new_item.id,
                        text=sub_data.text,
                        completed=sub_data.completed if hasattr(sub_data, 'completed') else False
                    )
                    db.add(new_sub)

        db.commit()
        return {"message": "Challenge erfolgreich aktualisiert"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Fehler beim Aktualisieren der Challenge: {str(e)}"
        )


# 🗑 Challenge löschen
@router.delete("/delete/{challenge_id}")
async def delete_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    db_user = get_db_user(db, user_db_id=current_user.get("user_id"))
    check_access_by_role(db_user.role, [0, 1, 2])

    try:
        # 1. Challenge abrufen
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge nicht gefunden")

        # # 2. Alle abhängigen SubChallenges löschen
        # db.query(SubChallenge).filter(SubChallenge.item_id.in_(
        #     db.query(Item.id).filter(Item.section_id.in_(
        #         db.query(Section.id).filter(Section.challenge_id == challenge_id)
        #     ))
        # )).delete(synchronize_session=False)

        # # 3. Alle abhängigen Items löschen
        # db.query(Item).filter(Item.section_id.in_(
        #     db.query(Section.id).filter(Section.challenge_id == challenge_id)
        # )).delete(synchronize_session=False)

        # # 4. Alle abhängigen Sections löschen
        # db.query(Section).filter(Section.challenge_id == challenge_id).delete(synchronize_session=False)

        # # 5. Jetzt die Challenge löschen
        # db.delete(challenge)

        # Simplified approach with PostgreSQL
        challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge nicht gefunden")

        # Just delete the challenge - the rest will cascade automatically
        db.delete(challenge)
   
        db.commit()
        return {"message": "Challenge erfolgreich gelöscht"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Fehler beim Löschen: {str(e)}")

