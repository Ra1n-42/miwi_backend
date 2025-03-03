from app.models.user import User
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from app.token import decode_jwt, TokenExpiredError, InvalidTokenError
from sqlalchemy.orm import Session
from app.database.db_connection import get_db 
from typing import Annotated, List
from app.user_func import get_db_user
from pydantic import BaseModel
from datetime import datetime

from app.utils.time_tracking_logger import log_request_duration, logger

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}},
)

db_dependency = Annotated[Session, Depends(get_db)]

def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_jwt(str(token))
        return payload  # Gibt die Benutzerinformationen zurück
    except TokenExpiredError:
        raise HTTPException(status_code=401, detail="Token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/me")
@log_request_duration
async def get_user_data(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    user_db_id = current_user.get("user_id")
    if not user_db_id: return {"message": "Not authenticated"}
    logger.info(f"user {current_user["display_name"]} requested his own data") 
    db_user = get_db_user(db, user_db_id)
    # return userinfo dict 

    return {
        "user_id": user_db_id,
        "display_name": current_user.get("display_name"),
        "avatar_url": current_user.get("avatar_url"),
        "role": db_user.role,
    }

@router.post("/logout")
@log_request_duration
async def logout(
    request: Request,
    response: Response):
    # Löschen des Cookies
    response.delete_cookie("access_token")
    
    return {"message": "Successfully logged out"}


def check_access_by_role(current_user_role: int, allowed_roles: list):
    if current_user_role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail={"message": "Das kannst du zurzeit nicht machen, dafür benötigst du die richtigen Rechte."}
        )

class UserUpdate(BaseModel):
    id: int
    role: int
    is_active: bool

@router.put("/update")
@log_request_duration
async def update_user(
    request: Request,
    user_update: UserUpdate, 
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Prüfen, ob der aktuelle Benutzer admin oder eine ähnliche Rolle hat
    db_user = get_db_user(db, user_db_id=current_user.get("user_id"))
    check_access_by_role(db_user.role, [0])

    # Zielbenutzer aus der Datenbank abrufen
    user = db.query(User).filter(User.id == user_update.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    logger.info(f"{current_user["display_name"]} änderte {user.display_name} die rolle {user.role} zu {user_update.role}")
    # Aktualisierung durchführen
    user.role = user_update.role
    user.is_active = user_update.is_active

    db.commit()
    db.refresh(user)
    # Rückgabe, die das Frontend benötigt
    return {"message": f"{user.display_name} erfolgreich bearbeitet!", "user": user}

class UserOut(BaseModel):
    id: int
    twitch_id: int
    email: str
    display_name: str
    role: int
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),  # Konvertiert datetime in ISO 8601 String
        }

# Route für alle Benutzer
@router.get("/all", response_model=List[UserOut])
@log_request_duration
async def get_all_user(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    db_user = get_db_user(db, user_db_id = current_user.get("user_id"))
    # Rollenprüfung

    check_access_by_role(db_user.role, [0, 1]) 

    # Abruf aller Benutzer aus der Datenbank
    users = db.query(User).filter(User.email.isnot(None)).all()

    # Rückgabe aller Benutzer
    return users