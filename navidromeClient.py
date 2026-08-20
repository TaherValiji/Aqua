import secrets
import hashlib
import aiohttp
from musicPlayer import Track, MusicQueue
from typing import Optional, List

class NavidromeClient:
    def __init__(self, url: str, username: str, password: str):
        self.url = url
        self.username = username
        self.password = password
        self.session = None
    
    async def init_session(self):
        """Initialize persistent session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()
            self.session = None

        
 #-------------------------Navidrome API Authentication-------------------------
 
    async def navidromeAuthenticate(self) -> bool:
        """Authenticate with Navidrome using token-based auth"""
        try:
            await self.init_session()
            
            # Generate salt and token for auth
            salt = secrets.token_hex(3)
            token = hashlib.md5((self.password + salt).encode()).hexdigest()
            
            params = {
                'u': self.username,
                't': token,
                's': salt,
                'c': 'Aqua',
                'v': '1.16.1',
                'f': 'json'
            }
            
            async with self.session.get(
                f"{self.url}/rest/ping.view",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    api_status = data.get("subsonic-response", {}).get("status")
                    
                    if api_status == "ok":
                        print("Successfully authenticated with Navidrome")
                        return True
                    else:
                        error_msg = data.get("subsonic-response", {}).get("error", {}).get("message")
                        print(f"Failed to authenticate: {error_msg}")
                        return False
                else:
                    text = await response.text()
                    print(f"Failed to authenticate with Navidrome: {text}")
                    return False
                    
        except Exception as e:
            print(f"Error during Navidrome authentication: {e}")
            import traceback
            traceback.print_exc()
            return False

    # search for songs by name
    async def search(self, query: str) -> List[Track]:
        print(f"Searching for track by name: {query}")
        try:
            salt = secrets.token_hex(3)
            token = hashlib.md5((self.password + salt).encode()).hexdigest()
            
            params = {
                'u': self.username,
                't': token,
                's': salt,
                'c': 'Aqua',
                'v': '1.16.1',
                'f': 'json',
                'query': query,
                'songCount': 20
            }
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(
                f"{self.url}/rest/search3.view",
                params=params,
                timeout=timeout
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                
                api_status = data.get('subsonic-response', {})
                if api_status.get('status') != 'ok':
                    error_code = api_status.get('error', {}).get('code')
                    error_msg = api_status.get('error', {}).get('message', 'Unknown error')
                    print(f"Subsonic Error {error_code}: {error_msg}")
                    return []
                
                songs = api_status.get('searchResult3', {}).get('song', [])
                if isinstance(songs, dict):
                    songs = [songs]
                
                # Pass username, password, and URL to Track
                return [Track(song, self.username, self.password, self.url) for song in songs]
        except aiohttp.ClientError as e:
            print(f"Network error searching '{query}': {e}")
            return []
        return []