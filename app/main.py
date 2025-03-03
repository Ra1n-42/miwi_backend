import httpx
import asyncio
from app.routes import (challenge, user, clip)
from typing import Annotated
from app.token import create_jwt
from pydantic import BaseModel 
from sqlalchemy.orm import Session 
from app.models import User, Clip, UserClipLike, Challenge, Section, Item
from app.database.db_connection import Base, engine, get_db
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware 
from fastapi.responses import RedirectResponse
from app.twitch_func import (
    get_user_info, 
    get_oauth_token, 
    fetch_stream_status,
    get_access_token,
)
from app.user_func import (save_or_update_user)
from fastapi import FastAPI, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from app.twitch_data import Twitch
from app.utils.display_client_data import Client
from app.utils.time_tracking_logger import logger

app = FastAPI()

app.include_router(user.router)
app.include_router(clip.router)
app.include_router(challenge.router)

connected_clients = {}

origins = [
    'https://dev.miwi.tv',
    'https://miwi.tv',
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True,
    allow_methods=["*"],  # Erlaubt alle Methoden wie GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],  # Erlaubt alle Header
)

Base.metadata.create_all(bind=engine)


class UserBase(BaseModel):
    email:str

db_dependency = Annotated[Session, Depends(get_db)]


@app.websocket("/ws/{user_login}")
async def websocket_endpoint(websocket: WebSocket, user_login: str):
    await websocket.accept()
    
    # Get initial token
    token = await get_oauth_token()
    if not token:
        # Send error message and close if we can't get a token
        await websocket.send_json({"status": "error", "message": "Failed to authenticate with Twitch"})
        await websocket.close(1011)  # 1011 = Server error
        return
        
    # Store connection
    connected_clients[user_login] = websocket

    try:
        previous_status = None
        token_refresh_counter = 0
        error_count = 0
        
        while True:
            try:
                # Increment token refresh counter
                token_refresh_counter += 1
                
                # Refresh token every 30 minutes (60 loops * 30 seconds)
                if token_refresh_counter >= 60:
                    new_token = await get_oauth_token()
                    if new_token:
                        token = new_token
                    token_refresh_counter = 0
                
                # Fetch stream status
                stream_data = await fetch_stream_status(user_login, token)
                
                # Reset error counter on success
                error_count = 0
                
                # Determine status
                current_status = "online" if stream_data else "offline"
                
                # Only send if status changed
                if current_status != previous_status:
                    await websocket.send_json({
                        "status": current_status,
                        "data": stream_data,
                    })
                    previous_status = current_status
                
                # Wait before next check
                await asyncio.sleep(30)
                
            except WebSocketDisconnect:
                # Client disconnected, break the loop
                raise
                
            except Exception as e:
                error_count += 1
                logger.info(f"Error in WebSocket loop for {user_login}: {str(e)}")
                
                # After 3 consecutive errors, try refreshing the token
                if error_count >= 3:
                    logger.info(f"Refreshing token after multiple errors for {user_login}")
                    new_token = await get_oauth_token()
                    if new_token:
                        token = new_token
                    error_count = 0
                
                # Exponential backoff: wait longer between retries (max 60 seconds)
                backoff_time = min(5 * (2 ** (error_count - 1)), 60)
                await asyncio.sleep(backoff_time)
                
                # Try to send heartbeat to check if connection is still alive
                try:
                    await websocket.send_json({"status": "heartbeat"})
                except:
                    # Connection is dead, break the loop
                    raise WebSocketDisconnect()
    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {user_login}")
        if user_login in connected_clients:
            del connected_clients[user_login]
    except Exception as e:
        logger.info(f"Unexpected error in websocket for {user_login}: {str(e)}")
        if user_login in connected_clients:
            del connected_clients[user_login]
        try:
            await websocket.close(1011)
        except:
            pass

@app.get("/login")
async def login(request: Request):
    auth_url = (
        f"{Twitch.TWITCH_AUTH_URL}?"
        f"client_id={Twitch.CLIENT_ID}&"
        f"redirect_uri={Twitch.REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=user:read:email"  # Beispiel-Scopes
    )
    client_ip = Client(request).client_ip
    logger.info(f"backend[/login]:{client_ip} versucht sich einzuloggen.")
    return RedirectResponse(auth_url)

@app.post("/logout")
async def logout(response: Response):
    response = RedirectResponse(url=Twitch.REDIRECT_URL_AFTER_LOGIN)
    response.set_cookie(
        key="access_token",
        value="",
        httponly=True,
        secure=True,
        max_age=1,
        samesite="None",
        domain="dev.miwi.tv" if Twitch.DEV else "miwi.tv",
    )

    return response

@app.get("/auth/callback")
async def auth_callback(
        code: str, db: db_dependency
    ): # type: ignore
    # Access Token abrufen
    access_token, expires_in_seconds = get_access_token(code)

    logger.info(f"backend[/auth/callback]: Access Token {access_token} erhalten. Expires in {expires_in_seconds} Sekunden.")
    
    # Benutzerinformationen abrufen
    user_info = get_user_info(access_token)
    logger.info(f"backend[/auth/callback]: Benutzerinformationen erhalten: {user_info}")

    # Benutzer speichern oder aktualisieren
    user = save_or_update_user(user_info, db)

    # Ablaufzeit berechnen
    expiration_time = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
    expiration_unix = int(expiration_time.timestamp())

    # JWT-Token erstellen
    token_data = {
        "user_id": user.id, 
        "display_name": user.display_name, 
        "avatar_url": user_info["avatar_url"],
        "exp": expiration_unix,
    }
    logger.info(f"backend[/auth/callback]: JWT Token Daten: {token_data}")
    jwt_token = create_jwt(data=token_data)

    # Das JWT im HTTP-Only Cookie speichern
    response = RedirectResponse(url=Twitch.REDIRECT_URL_AFTER_LOGIN)
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        secure=True,
        max_age=expires_in_seconds,
        samesite="None", 
        domain="dev.miwi.tv" if Twitch.DEV else "miwi.tv",
    )
    logger.info(f"backend[/auth/callback]: JWT Token im Cookie gespeichert.")
    return response


@app.get("/")
async def read_root():

    return {"Hello": "MiwiTV"}


# Api Anfrage an Streamerelements 
@app.get("/giveaways")
async def get_giveaways():
    url = f"https://api.streamelements.com/kappa/v3/giveaways/{Twitch.Account_ID}"

    headers = {
        "Accept": "application/json; charset=utf-8",
        "Authorization": f"Bearer {Twitch.JWT_Token}",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
        
        if response.status_code != 200:
            return response.json()  # Erfolgreiche Antwort
    
        # JSON-Daten parsen
        data = response.json()

        # Interessante Informationen extrahieren
        sanitized_data = {
            "total": data.get("total"),
            "giveaways": [
                {
                    "title": giveaway.get("title"),
                    "description": giveaway.get("description"),
                    "preview": giveaway.get("preview"),
                    "subscriberOnly": giveaway.get("subscriberOnly"),
                    "maxTickets": giveaway.get("maxTickets"),
                    "state": giveaway.get("state"),
                    "startedAt": giveaway.get("startedAt"),
                    "endedAt": giveaway.get("endedAt"),
                    "createdAt": giveaway.get("createdAt"),
                    "winners": [
                        {
                            "username": winner.get("username"),
                            # Platzhalter für mögliche zukünftige Winner-Daten
                            "placeholder": "future_field_here"
                        }
                        for winner in giveaway.get("winners", [])
                    ]
                }
                for giveaway in data.get("giveaways", [])
            ]
        }
        print(sanitized_data)
        return sanitized_data


    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
