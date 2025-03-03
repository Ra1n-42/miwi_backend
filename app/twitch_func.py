import os
import httpx
import requests
from fastapi import HTTPException
from app.twitch_data import Twitch

class Streamer:
    ID = os.getenv("TWITCH_STREAMER_ID")
    SECRET = os.getenv("TWITCH_STREAMER_SECRET")

def get_user_info(access_token: str):
    user_info_url = "https://api.twitch.tv/helix/users"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": Twitch.CLIENT_ID,
    }
    
    response = requests.get(user_info_url, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch user info")
    
    user_info = response.json()
    return {
        "id": user_info["data"][0]["id"],
        "login": user_info["data"][0]["login"],
        
        "display_name": user_info["data"][0]["display_name"],
        "avatar_url": user_info["data"][0]["profile_image_url"],
        "description": user_info["data"][0]["description"],

        
        "email": user_info["data"][0]["email"] if "email" in user_info["data"][0] else None,
        "created_at": user_info["data"][0]["created_at"],
    }

# async def fetch_stream_status(user_login: str, token: str):
    # url = "https://api.twitch.tv/helix/streams"
    # headers = {
    #     "Client-ID": Streamer.ID,
    #     "Authorization": f"Bearer {token}",
    # }
    # params = {"user_login": user_login}

    # async with httpx.AsyncClient() as client:
    #     response = await client.get(url, headers=headers, params=params)
    #     data = response.json()

    # return data["data"][0] if response.status_code == 200 and data["data"] else None

async def fetch_stream_status(user_login: str, token: str):
    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Client-ID": Streamer.ID,
        "Authorization": f"Bearer {token}",
    }
    params = {"user_login": user_login}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:  # Set explicit timeout
            response = await client.get(url, headers=headers, params=params)
            data = response.json()
            
            return data["data"][0] if response.status_code == 200 and data["data"] else None
            
    except httpx.ConnectTimeout:
        print(f"Connection timeout when fetching stream status for {user_login}")
        return None
    except httpx.ReadTimeout:
        print(f"Read timeout when fetching stream status for {user_login}")
        return None
    except Exception as e:
        print(f"Error fetching stream status for {user_login}: {str(e)}")
        return None    

# No Login required (dev creds)

# async def get_oauth_token():
#     url = "https://id.twitch.tv/oauth2/token"
#     params = {
#         "client_id": Streamer.ID,  
#         "client_secret": Streamer.SECRET,
#         "grant_type": "client_credentials"
#     }

#     async with httpx.AsyncClient() as client:
#         response = await client.post(url, params=params)
#         data = response.json()

#     return data['access_token']  # -> access_token
async def get_oauth_token():
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": Streamer.ID,
        "client_secret": Streamer.SECRET,
        "grant_type": "client_credentials"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, params=params)
            data = response.json()
            
            if response.status_code == 200:
                return data['access_token']
            else:
                print(f"Failed to get OAuth token: {data}")
                # Return previous token if available, or None
                return None
                
    except Exception as e:
        print(f"Error fetching OAuth token: {str(e)}")
        return None


def get_clips_from_twitch(broadcaster_id, access_token, limit=10):
    """
    Ruft Clips eines Broadcasters ab und unterstützt die Paginierung.
    """
    url = "https://api.twitch.tv/helix/clips"
    headers = {
        "Client-ID": Twitch.CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "broadcaster_id": broadcaster_id,
        "first": limit
    }
    clips = []
    
    while True:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            clips.extend(data["data"])  # Füge die abgerufenen Clips zur Liste hinzu

            # Prüfe, ob es noch eine nächste Seite gibt
            if "pagination" in data and "cursor" in data["pagination"]:
                params["after"] = data["pagination"]["cursor"]  # Setze den Cursor für die nächste Seite
            else:
                break  # Keine weiteren Seiten, beende die Schleife
        else:
            print(f"Fehler beim Abrufen der Clips: {response.status_code}")
            print(response.json())
            break

    return clips

def get_broadcaster_id(username, access_token):
    """
    Ruft die Broadcaster-ID eines Benutzernamens ab.
    """
    url = "https://api.twitch.tv/helix/users"
    headers = {
        "Client-ID": Twitch.CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    params = {"login": username}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        if data["data"]:
            return data["data"][0]["id"]
        else:
            print("Benutzer nicht gefunden.")
            return None
    else:
        print(f"Fehler beim Abrufen der Broadcaster-ID: {response.status_code}")
        print(response.json())
        return None
    
def generate_access_token():
    """
    Generiert ein Access Token mit Hilfe von CLIENT_ID und CLIENT_SECRET.
    """
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": Twitch.CLIENT_ID,
        "client_secret": Twitch.CLIENT_SECRET,
        "grant_type": "client_credentials"
    }

    response = requests.post(url, params=params)

    if response.status_code == 200:
        data = response.json()
        return data["access_token"]
    else:
        print(f"Fehler beim Abrufen des Access Tokens: {response.status_code}")
        print(response.json())
        return None
    
def get_access_token(code: str) -> str:
    """
    Holt das Access Token von Twitch mit dem Authorization Code.
    """
    token_url = "https://id.twitch.tv/oauth2/token"
    data = {
        "client_id": Twitch.CLIENT_ID,
        "client_secret": Twitch.CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": Twitch.REDIRECT_URI,
    }

    response = requests.post(token_url, data=data)

    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch access token")
    
    tokens = response.json()
    return tokens["access_token"], tokens["expires_in"]