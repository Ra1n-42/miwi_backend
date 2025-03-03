import jwt
from datetime import datetime, timedelta

SECRET_KEY = ".#DasIsMeinSuperDuperGeheimerSuperSchlüssel#."
ALGORITHM = "HS256"

class TokenExpiredError(Exception):
    pass

class InvalidTokenError(Exception):
    pass

def create_jwt(data: dict):
    if "user_id" in data and not isinstance(data["user_id"], int):
        data["user_id"] = int(data["user_id"])
    token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
    return token

def decode_jwt(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print("Decoded Payload:", payload)
        # Validierung des sub-Wertes
        if "user_id" not in payload or not isinstance(payload["user_id"], int):
            raise InvalidTokenError("Subject (user_id) muss ein int sein")
        return payload
    except jwt.ExpiredSignatureError as e:
        print("JWT Decode Error: ExpiredSignatureError:", str(e))
        raise TokenExpiredError("Token abgelaufen")
    except jwt.InvalidTokenError as e:
        print("JWT Decode Error: InvalidTokenError:", str(e))
        raise InvalidTokenError("Ungültiges Token")
    except Exception as e:
        print("Unexpected Error during JWT Decode:", str(e))
        raise

