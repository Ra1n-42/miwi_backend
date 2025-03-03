from functools import wraps
from fastapi import Depends
from fastapi import HTTPException
from .auth import check_request_token


# Authentifizierungs-Decorator
def authenticate_route(func):
    @wraps(func)
    async def wrapper(*args, token_data: dict = Depends(check_request_token), **kwargs):
        # Hier kannst du zusätzliche Berechtigungslogik einfügen
        # Zum Beispiel: Überprüfen, ob der Benutzer bestimmte Rollen oder Berechtigungen hat
        # Du kannst auch auf `token_data` zugreifen, das die Benutzerinformationen enthält
        
        # Beispiel: Nur Benutzer mit einer bestimmten Rolle können fortfahren
        if token_data.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Rufe die ursprüngliche Funktion auf, wenn alles OK ist
        return await func(*args, **kwargs)
    return wrapper


