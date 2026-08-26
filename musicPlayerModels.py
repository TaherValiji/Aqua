import secrets
import hashlib
from urllib.parse import urlencode
from typing import Optional, List

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



#-------------------------Queue class for managing playlist-------------------------

class MusicQueue:
    def __init__(self):
        self.queue: List[Track] = []
        self.current: Optional[Track] = None
        self.is_playing = False
        self.loop_mode = 0  # 0 = no loop, 1 = queue loop, 2 = song loop
        self.original_queue: List[Track] = []
    
    def add(self, track: Track):
        self.queue.append(track)
    
    def next(self) -> Optional[Track]:
        if self.queue:
            return self.queue.pop(0)
        return None

    def set_loop_mode(self, mode: int):
        if mode == 1 and self.queue:
            self.original_queue = self.queue.copy()
        self.loop_mode = mode


    def clear(self):
        self.queue.clear()
        self.original_queue.clear()
        self.current = None
        self.is_playing = False
        self.loop_mode = 0

    
    def __len__(self):
        return len(self.queue)
