#-------------------------Track information class-------------------------

class Track:
    def __init__(self, data, username, password, server_url):
        self.id = data.get('id')
        self.title = data.get('title', 'Unknown')
        self.artist = data.get('artist', 'Unknown')
        self.album = data.get('album', 'Unknown')
        self.duration = data.get('duration', 0)
        self.path = data.get('path', '')
        self.username = username
        self.password = password
        self.server_url = server_url
    
    def get_stream_url(self):
        """Generate stream URL with token-based authentication"""
        # Generate salt and token
        salt = secrets.token_hex(3)
        token = hashlib.md5((self.password + salt).encode()).hexdigest()
        
        # Build params dict (urlencode handles special characters)
        params = {
            'u': self.username,
            't': token,
            's': salt,
            'v': '1.8.0',
            'c': 'Aqua',
            'id': self.id,
        }
        
        stream_url = f"{self.server_url}/rest/stream?{urlencode(params)}"
        return stream_url
    
    def __str__(self):
        return f"{self.title} - {self.artist}"