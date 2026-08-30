import secrets
import hashlib
import aiohttp
from musicPlayerModels import Track
from typing import List, Optional, Dict



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




    #   Search for songs by name

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



    #   Get a list of all available songs

    async def getAllSongs(self):
        salt = secrets.token_hex(3)
        token = hashlib.md5((self.password + salt).encode()).hexdigest()
        timeout = aiohttp.ClientTimeout(total=10)

        print(f"Trying to get all songs...")

        try:
            params = {
                'u': self.username,
                't': token,
                's': salt,
                'c': 'Aqua',
                'v': '1.16.1',
                'f': 'json',
                'size': 50,
            }
            async with self.session.get(
                f"{self.url}/rest/getRandomSongs.view",
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
                
                songs = api_status.get('randomSongs', {}).get('song', [])
                if isinstance(songs, dict):
                    songs = [songs]

            return [Track(song, self.username, self.password, self.url) for song in songs]

        except aiohttp.ClientError as e:
            print(f"Network error: {e}")
            return []


    # Create a new playlist and return its ID
    async def createPlaylist(self, name: str) -> Optional[str]:
        salt = secrets.token_hex(3)
        token = hashlib.md5((self.password + salt).encode()).hexdigest()

        try:
            params = {
                'u': self.username,
                't': token,
                's': salt,
                'c': 'Aqua',
                'v': '1.16.1',
                'f': 'json',
                'name': name,
            }

            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(
                f"{self.url}/createPlaylist.view",
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

                
                playlist_id = data.get('subsonic-response', {}).get('playlist', {}).get('id')
                print(f"Created playlist '{name}' with ID: {playlist_id}")
                return playlist_id
        except Exception as e:
            print(f"Error creating playlist: {e}")
        return None

    # Add songs to a playlist
    async def addSongsToPlaylist(self, playlist_id: str, song_ids: List[str]) -> bool:
        salt = secrets.token_hex(3)
        token = hashlib.md5((self.password + salt).encode()).hexdigest()
        
        try:
            params = {
            'u': self.username,
            't': token,
            's': salt,
            'c': 'Aqua',
            'v': '1.16.1',
            'f': 'json',
            'playlistId': playlist_id,
            }

            for song_id in song_ids:
                params[f'songIdToAdd'] = song_id
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(
                f"{self.url}/updatePlaylist.view",
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
                
        except Exception as e:
            print(f"Error adding songs to playlist: {e}")
        return False


    # Get playlist by name
    def getPlaylistByName(self, name: str) -> Optional[Dict]:
        try:
            response = self.session.get(f"{self.url}/getPlaylists.view")
            if response.status_code == 200:
                data = response.json()
                for playlist in data.get('subsonic-response', {}).get('playlists', {}).get('playlist', []):
                    if playlist.get('name') == name:
                        return playlist
        except Exception as e:
            print(f"Error getting playlist: {e}")
        return None
