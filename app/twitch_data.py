import os

class Twitch:
    DEV = True

    if DEV:
        # Dev
        CLIENT_ID = os.getenv("DEV_CLIENT_ID")
        CLIENT_SECRET = os.getenv("DEV_CLIENT_SECRET")
        REDIRECT_URL_AFTER_LOGIN = os.getenv("DEV_REDIRECT_URL_AFTER_LOGIN")
    else:
        # prod
        CLIENT_ID = os.getenv("PROD_CLIENT_ID")
        CLIENT_SECRET = os.getenv("PROD_CLIENT_SECRET")
        REDIRECT_URL_AFTER_LOGIN = os.getenv("PROD_REDIRECT_URL_AFTER_LOGIN")
    
    REDIRECT_URI = REDIRECT_URL_AFTER_LOGIN + "/api/auth/callback"
    TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/authorize"

    # Streamerelements MIWI
    JWT_Token = os.getenv("JWT_Token")
    Account_ID = os.getenv("Account_ID") 
