from fastapi import Request

def get_client_ip_and_url(request: Request):
    # Holen der IP-Adresse und URL
    forwarded_for = request.headers.get("X-Forwarded-For")
    client_ip = forwarded_for.split(",")[0] if forwarded_for else request.client.host  # Fallback auf request.client.host
    full_url = str(request.url)
    
    return client_ip, full_url

class Client:
    def __init__(self, request: Request):
        # Beim Erstellen des Objekts wird die IP und URL durch den Request ermittelt
        self.client_ip, self.full_url = self.visited(request)
        
    def visited(self, request: Request):
        # Holen der IP-Adresse und URL
        return get_client_ip_and_url(request)
