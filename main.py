import secrets
import subprocess
import hashlib
from dotenv import load_dotenv
import sys
import os
import discord
from discord.ext import commands
from discord import app_commands
import time
import requests
import aiohttp
import asyncio
from typing import Optional, List
import json
from urllib.parse import urljoin, quote, urlencode
import nacl
import yt_dlp


#-------------------------Configuration-------------------------

load_dotenv()

#   Bot general settings

bot_token = os.getenv('BOT_TOKEN')
guild_id1 = discord.Object(os.getenv('SERVER_ID1'))
guild_id2 = discord.Object(os.getenv('SERVER_ID2'))

#   Proxmox API settings

pve_url = os.getenv('PVE_URL')
pve_user_token = os.getenv('PVE_USER_TOKEN')
headers = {"Authorization": f"PVEAPIToken={pve_user_token}"}

#   Navidrome API Settings

navidrome_url = os.getenv('NAVIDROME_URL')
navidrome_username = os.getenv('NAVIDROME_USERNAME')
navidrome_password = os.getenv('NAVIDROME_PASSWORD')
music_library_path = os.getenv('MUSIC_LIBRARY_PATH')

#-------------------------Bot setup-------------------------

intents = discord.Intents.default()
intents.message_content= True
intents.voice_states = True
bot = commands.Bot(command_prefix='/', intents=intents)


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

#-------------------------Queue class for managing playlist-------------------------

class MusicQueue:
    def __init__(self):
        self.queue: List[Track] = []
        self.current: Optional[Track] = None
        self.is_playing = False
    
    def add(self, track: Track):
        self.queue.append(track)
    
    def next(self) -> Optional[Track]:
        if self.queue:
            return self.queue.pop(0)
        return None
    
    def clear(self):
        self.queue.clear()
        self.current = None
        self.is_playing = False
    
    def __len__(self):
        return len(self.queue)
 
    
 #-------------------------Navidrome API Authentication-------------------------

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


    async def search(self, query: str) -> List[Track]:
        """Search for songs in Navidrome"""
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

    
navidrome_client = NavidromeClient(navidrome_url, navidrome_username, navidrome_password)
music_queues = {}  # Store queue for each guild


#   Get or create queue for guild

def get_queue(guild_id: int) -> MusicQueue:
    if guild_id not in music_queues:
        music_queues[guild_id] = MusicQueue()
    return music_queues[guild_id]


 #  Play a track in voice channel

async def play_track(voice_client: discord.VoiceClient, track: Track, guild_id: int):
    queue = get_queue(guild_id)
    queue.current = track
    queue.is_playing = True
    
    try:
        stream_url = track.get_stream_url()

        source = discord.FFmpegPCMAudio(
            stream_url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options='-vn -filter:a "volume=0.25"'
        )
        print(f"Playing track: {track.title}")
        print(f"Stream URL: {stream_url}")
        print(f"Track ID: {track.id}")
        voice_client.play(source)
    except Exception as e:
        print(f"Error playing track: {e}")
        queue.is_playing = False


#   Auto-play next track in queue

async def music_loop(guild_id: int):
    guild = bot.get_guild(guild_id)
    if not guild:
        return
    
    voice_client = discord.utils.get(bot.voice_clients, guild=guild)
    if not voice_client:
        return
    
    queue = get_queue(guild_id)
    
    while True:
        await asyncio.sleep(1)
        
        if not voice_client.is_connected():
            queue.clear()
            break
        
        if not voice_client.is_playing() and queue.is_playing:
            next_track = queue.next()
            if next_track:
                await play_track(voice_client, next_track, guild_id)
            else:
                queue.is_playing = False


@bot.event
async def on_ready():
    print(f'Logged on as {bot.user}!')

    
    #-------------------------Authentication-------------------------

    await navidrome_client.navidromeAuthenticate()

    #-------------------------Syncing commands-------------------------

    try:
        sync_to_server1 = await bot.tree.sync(guild=guild_id1)
        print(f'Synced {len(sync_to_server1)} commands to guild {guild_id1}.')
        sync_to_server2 = await bot.tree.sync(guild=guild_id2)
        print(f'Synced {len(sync_to_server2)} commands to guild {guild_id2}.')

    except Exception as e:
        print(f"Error syncing commands: {e}")

    cmds1 = await bot.tree.fetch_commands(guild=guild_id1)
    print([c.name for c in cmds1])

    cmds2 = await bot.tree.fetch_commands(guild=guild_id2)
    print([c.name for c in cmds2])



#-------------------------Message Handling-------------------------

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.content.lower().endswith(("boo him")) or message.content.lower().endswith(("boo her")):
        await message.channel.send("boo")

    if "chat boo" in message.content.lower() and message.mentions:

        member = message.mentions[0]

        try:
            await member.send("boo")
        except discord.Forbidden:
            await message.channel.send("I don't have permission to send a direct message to that user.")
        except Exception as e:
            await message.channel.send(f"An error occurred while trying to send a direct message: {e}")

    await bot.process_commands(message)




#-------------------------Proxmox API Functions-------------------------

def shutdown_vm(node, vmid):
    r = requests.post(
        f"{pve_url}/api2/json/nodes/{node}/lxc/{vmid}/status/shutdown",
        headers=headers, verify=False
    )
    return r.json()

def get_status(node, vmid):
    r = requests.get(
        f"{pve_url}/api2/json/nodes/{node}/lxc/{vmid}/status/current",
        headers=headers, verify=False
    )
    print(f"[get_status] status_code={r.status_code}, body={r.text!r}")
    return r.json()["data"]["status"]


#-------------------------Discord Commands-------------------------

#------------------------Server Control Commands-------------------------

@bot.tree.command(name="startserver", description="Starts the minecraft server", guilds=[guild_id1, guild_id2])
async def startServer(interaction: discord.Interaction):
    await interaction.response.send_message("Starting the server...")
    if get_status("pve", 101) == "stopped":
        r = requests.post(
            f"{pve_url}/api2/json/nodes/pve/lxc/101/status/start",
            headers=headers, verify=False
        )
        if r.status_code == 200:
            await interaction.followup.send("Server started successfully!")
        else:
            await interaction.followup.send("Failed to start the server.")
    else:
        await interaction.followup.send("Server is already running.")


@bot.tree.command(name="stopserver", description="Stops the minecraft server", guilds=[guild_id1, guild_id2])
async def stopServer(interaction: discord.Interaction):
    await interaction.response.send_message("Stopping the server...")
    if get_status("pve", 101) == "running":
        r = requests.post(
            f"{pve_url}/api2/json/nodes/pve/lxc/101/status/shutdown",
            headers=headers, verify=False
        )
        if r.status_code == 200:
            await interaction.followup.send("Server stopped successfully!")
        else:
            await interaction.followup.send("Failed to stop the server.")
    else:
        await interaction.followup.send("Server is already stopped.")



#-------------------------Navidrome Commands-------------------------


#Bot joins your voice channel

@bot.tree.command(name="join", description="Joins your voice channel", guilds=[guild_id1, guild_id2])
async def join(interaction: discord.Interaction):

    await interaction.response.defer()  # Defer the response to give the bot more time to process

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("You need to be in a voice channel!")
        return
    
    channel = interaction.user.voice.channel

    try:
        await channel.connect()
        await interaction.followup.send(f"Joined {channel.name}")
    except Exception as e:
        await interaction.followup.send(f"Error joining channel: {e}")


#Bot leaves voice channel

@bot.tree.command(name="leave", description="Leaves the voice channel", guilds=[guild_id1, guild_id2])
async def leave(interaction: discord.Interaction):
    if not interaction.guild.voice_client or not interaction.guild.voice_client.channel:
        await interaction.response.defer()
        await interaction.followup.send("Not in a voice channel!")
        return
    
    queue = get_queue(interaction.guild.id)
    queue.clear()
    await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("Left the voice channel")


#   Play Mommy ASMR
@bot.tree.command(name="playmommyasmr", description="Search and play Mommy ASMR", guilds=[guild_id1, guild_id2])
async def playMommyASMR(interaction: discord.Interaction):

    await interaction.response.defer()
    
    voice_client = interaction.guild.voice_client
    if not voice_client:
        await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.")
        return
    
    results = await navidrome_client.search("Mommy Praises Her Sleepy Boy [F4M][good boy][head pats][baby talk]")
    
    if not results:
        await interaction.followup.send(f'could not find the track')
        return

    print(results)
    track = results[0]
    queue = get_queue(interaction.guild_id)
    queue.add(track)
    await interaction.followup.send(f'playing: {track.title} - {track.artist}')

    # Start music loop if not already running
    if not queue.is_playing:
        queue.is_playing = True
        await play_track(voice_client, queue.next(), interaction.guild_id)
        asyncio.create_task(music_loop(interaction.guild_id))


#   Play Music
@bot.tree.command(name="play", description="Search and play songs", guilds=[guild_id1, guild_id2])
async def play(interaction: discord.Interaction, query: str):

    await interaction.response.defer()
    
    voice_client = interaction.guild.voice_client
    if not voice_client:
        await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.")
        return
    
    results = await navidrome_client.search(query)
    
    if not results:
        await interaction.followup.send(f'could not find the track')
        return

    print(results)
    track = results[0]
    queue = get_queue(interaction.guild_id)
    queue.add(track)
    await interaction.followup.send(f'playing: {track.title} - {track.artist}')

    # Start music loop if not already running
    if not queue.is_playing:
        queue.is_playing = True
        await play_track(voice_client, queue.next(), interaction.guild_id)
        asyncio.create_task(music_loop(interaction.guild_id))


#   Download music using yt-dlp (YouTube-DL fork)
@bot.tree.command(name="add", description="add new songs", guilds=[guild_id1, guild_id2])
async def add(interaction: discord.Interaction, url: str):

    os.makedirs(music_library_path, exist_ok=True)

    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'outtmpl': os.path.join(music_library_path, '%(title)s.%(ext)s'),
        # ℹ️ See help(yt_dlp.postprocessor) for a list of available Postprocessors and their arguments
        'postprocessors': [{  # Extract audio using ffmpeg
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }]
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        error_code = ydl.download([url])

bot.run(bot_token)
