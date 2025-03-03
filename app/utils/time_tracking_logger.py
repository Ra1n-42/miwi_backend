import logging
from datetime import datetime
from fastapi import Request
from functools import wraps
from .display_client_data import Client

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_request_duration(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Find the request object
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
                
        if not request and 'request' in kwargs:
            request = kwargs['request']
            
        if not request:
            # If no request object found, just call the function
            return await func(*args, **kwargs)
            
        start_time = datetime.now()
        client = Client(request)
        full_url = str(request.url)

        # Log the start of the request
        logger.info(f"Anfrage für {full_url} empfangen von IP: {client.client_ip} um {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # Call the original function with the original arguments
            response = await func(*args, **kwargs)
        finally:
            # Calculate the duration and log it
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"Sync abgeschlossen um {end_time.strftime('%Y-%m-%d %H:%M:%S')}. Dauer: {duration:.2f} Sekunden.")
        
        return response

    return wrapper

