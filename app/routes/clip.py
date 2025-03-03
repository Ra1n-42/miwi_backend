from pydantic import BaseModel
from app.routes.user import check_access_by_role, get_current_user
from fastapi import (
    APIRouter,
    Body, 
    Depends, 
    HTTPException, 
    Request,
    Query
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from app.database.db_connection import get_db
from app.twitch_func import (
    generate_access_token, 
    get_broadcaster_id, 
    get_clips_from_twitch
)
from app.clip_func import (
    save_clip_if_not_exists
)
from app.models import (
    User, UserClipLike, Clip, BlockedClips
)
from app.user_func import get_db_user

from app.utils.time_tracking_logger import log_request_duration, logger
from app.utils.display_client_data import Client

router = APIRouter(
    prefix="/clip",
    tags=["clip"],
    responses={404: {"description": "Not found"}},
)


@router.post("/sync_clips")
@log_request_duration
async def sync_clips(request: Request, db: Session = Depends(get_db)):
      
    client = Client(request)
    
    logger.info(f"Anfrage für '/sync_clips' empfangen von IP: {client.client_ip} - {client.full_url}")

    broadcaster_username = "miwitv"

    access_token = generate_access_token()

    broadcaster_id = get_broadcaster_id(broadcaster_username, access_token)
    if not broadcaster_id:
        logger.error(f"Broadcaster {broadcaster_username} nicht gefunden.")
        raise HTTPException(status_code=400, detail="Broadcaster not found")

    clips = get_clips_from_twitch(broadcaster_id, access_token)
    if not clips:
        logger.warning(f"Keine Clips für Broadcaster {broadcaster_username} gefunden.")
        raise HTTPException(status_code=404, detail="No clips found")
    
    logger.info("Clips Synchronisation initiiert.")
    # Alle Clip-IDs von Twitch extrahieren
    twitch_clip_ids = {clip['id'] for clip in clips}
    # Alle Clips aus der Datenbank abrufen
    db_clips = db.query(Clip).filter(Clip.broadcaster_id == broadcaster_id).all()

    # Prüfen, ob Clips aus der DB noch auf Twitch existieren
    for db_clip in db_clips:
        if db_clip.clip_id not in twitch_clip_ids:
            # Lösche alle Likes für diesen Clip
            db.query(UserClipLike).filter(UserClipLike.clip_id == db_clip.id).delete()

            # Lösche den Clip aus der Datenbank
            db.delete(db_clip)
            logger.info(f"Clip {db_clip.clip_id} aus der Datenbank gelöscht.")

    for clip in clips:
        save_clip_if_not_exists(clip, broadcaster_id, db=db)

    return {"message": "Clips synchronisiert"}

class ClipResponse(BaseModel):
    creator_name: str
    id: str
    view_count: int
    created_at: str
    likes: int
    blocked: bool
    thumbnail_url: str | None

    class Config:
        from_attributes = True # Erlaubt die Konvertierung von SQLAlchemy Modellen

@router.get("/my_liked_clips")
@log_request_duration
async def get_my_liked_clips(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Gibt alle Clips vom aktuellen Benutzer zurück.

    Args:
        db (Session): Datenbank-Session.
        current_user (dict): Der aktuell angemeldete Benutzer.

    Returns:
        list[ClipResponse]: Eine Liste von Clips, die von dem Benutzer geliked wurden.
    """

    # Benutzerid aus dem JWT-Token und den Benutzer aus der Datenbank abrufen
    user_db_id = current_user.get("user_id")
    user = db.query(User).filter(User.id == user_db_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    logger.info(f"Benutzer {user.display_name +" : "+ user.twitch_id} ruft seine clips auf.")

    # Erstellt eine Joint zwischen UserClipLike und Clip, um die Clips zu erhalten, die der Benutzer geliked hat
    liked_clips = (
        db.query(Clip)
        .join(UserClipLike)
        .filter(UserClipLike.user_id == user.id)
        .order_by(UserClipLike.liked_at.desc())
        .all()
    )

    result = []
    for clip in liked_clips:
        result.append({
            "id": clip.clip_id,
            "creator_name": clip.creator.display_name,
            "view_count": clip.view_count,
            "created_at": clip.created_at.isoformat(),
            "likes": clip.calculate_likes(db),
            "thumbnail_url": clip.thumbnail_url,
        })
    logger.info(f"Benutzer {user.display_name +" : "+ user.twitch_id} hat {len(result)} Clips aufgerufen.")

    return result

@router.get("/all")
@log_request_duration
async def get_all_clips(
    request: Request,
    db: Session = Depends(get_db),
    show_blocked: bool = Query(False, description="Zeige blockierte Clips")
    ):
    query = db.query(Clip).options(joinedload(Clip.creator))
    # Wenn show_blocked=False, dann blockierte Clips ausfiltern
    if not show_blocked:
        blocked_clip_ids = select(BlockedClips.clip_id).where(BlockedClips.status == True)
        query = query.filter(~Clip.id.in_(blocked_clip_ids))  # Clips ausschließen
    
    clips = query.all()

    if not clips:
        raise HTTPException(status_code=404, detail="No clips found")
    
    result = []
    for clip in clips:
        likes_count = clip.calculate_likes(db)
        block_status = None
        if show_blocked:
            block_status_query = db.query(BlockedClips).filter(BlockedClips.clip_id == clip.id).first()
            block_status = block_status_query.status if block_status_query else False  # False wenn nicht blockiert
        
        result.append({
            "id": clip.clip_id,
            "creator_name": clip.creator.display_name,
            "view_count": clip.view_count,
            "created_at": clip.created_at.isoformat(),
            "likes": likes_count,
            "blocked": block_status,
            "thumbnail_url": clip.thumbnail_url,
        })
    logger.info(f"Es wurden {len(result)} Clips abgerufen.")
    return result

@router.post("/like/{clip_id}")
@log_request_duration
async def like_clip(
    clip_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # Authentifizierter Benutzer
):
    """
    Like a clip. Prevents a user from liking the same clip with the same IP multiple times.

    Args:
        clip_id (str): The ID of the clip to like.
        request (Request): The HTTP request object for retrieving the IP address.
        db (Session): Database session dependency.
        current_user (User): Authenticated user retrieved from JWT or session.

    Returns:
        dict: Success message if the clip is liked successfully.
    """
    user_ip = Client(request).client_ip
    user_name = current_user["display_name"]
    user_id = current_user["user_id"]

    # Clip prüfen
    clip = db.query(Clip).filter(Clip.clip_id == clip_id).first()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Verhindern, dass ein Nutzer seinen eigenen Clip liked
    if clip.creator_id == user_id:
        raise HTTPException(status_code=403, detail={"message": "Du kannst deinen eigenen Clip nicht liken."})

    # 1. User darf denselben Clip nicht doppelt liken (unabhängig von der IP)
    existing_like_by_user = db.query(UserClipLike).filter_by(
        user_id=user_id,
        clip_id=clip.id
    ).first()

    if existing_like_by_user:
        raise HTTPException(status_code=400, detail={"message": "Du hast diesen Clip bereits geliked."})

    # 2. Verhindere mehrere Accounts von derselben IP den gleichen Clip zu liken
    existing_like_by_ip = db.query(UserClipLike).filter_by(
        clip_id=clip.id,
        ip_address=user_ip
    ).first()

    if existing_like_by_ip:
        logger.warning(f"User {user_name} versucht denselben Clip von derselben IP zu liken.")
        raise HTTPException(status_code=400, detail={"message": "Von dieser IP wurde dieser Clip bereits geliked."})

    # Like speichern
    new_like = UserClipLike(
        user_id=user_id,
        clip_id=clip.id,
        ip_address=user_ip,
    )
    try:
        db.add(new_like)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Etwas ist schiefgelaufen routes.clip -> 160")

    # Optional: Anzahl der Likes im Clip aktualisieren
    clip.likes += 1
    db.commit()
    
    logger.info(f"Clip {clip_id} von {user_name, user_id, user_ip} geliked.")
    updated_likes = clip.calculate_likes(db)
    return {"message": "Clip liked successfully", "likes": updated_likes}

@router.post("/block/{clip_id}")
@log_request_duration
async def block_or_unblock_clip(
    clip_id: str,
    status: bool = Body(..., embed=True, description="True = blockieren, False = entsperren"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Blockiert oder entsperrt einen Clip.

    Args:
        clip_id (str): Die Clip-ID.
        status (bool): True = blockieren, False = entsperren.
        db (Session): Datenbank-Session.
        current_user (User): Der aktuell angemeldete Benutzer.

    Returns:
        dict: Bestätigung der Änderung.
    """

    # Clip prüfen
    clip = db.query(Clip).filter(Clip.clip_id == clip_id).first()
    if not clip:
        logger.warning(f"{current_user["display_name"]} hat versucht Clip: {clip_id} zu blockieren, der nicht existiert.")
        raise HTTPException(status_code=404, detail={"message": "Clip nicht gefunden."})

    roles = [0, 1, 2]
    db_user = get_db_user(db, user_db_id=current_user.get("user_id"))
    check_access_by_role(db_user.role, roles)

    # Überprüfen, ob der Clip schon blockiert wurde
    blocked_entry = db.query(BlockedClips).filter(BlockedClips.clip_id == clip.id).first()

    if blocked_entry:
        # Status aktualisieren
        blocked_entry.status = status
        blocked_entry.edited_user_id = db_user.id
    else:
        # Neuen Block-Eintrag erstellen
        new_block = BlockedClips(
            clip_id=clip.id,
            status=status,
            edited_user_id=db_user.id
        )
        db.add(new_block)

    db.commit()

    action = "blockiert" if status else "freigegeben"
    logger.info(f"Clip {clip_id} wurde von {current_user["display_name"]} erfolgreich {action}.")
    return {"message": f"Clip wurde erfolgreich {action}."}