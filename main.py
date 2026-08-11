from dotenv import load_dotenv
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
from urllib.parse import urljoin, quote



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

#-------------------------Bot setup-------------------------

intents = discord.Intents.default()
intents.message_content= True
intents.voice_states = True
bot = commands.Bot(command_prefix='/', intents=intents)


#-------------------------Track information class-------------------------

class Track:
    def __init__(self, data):
        self.id = data.get('id')
        self.title = data.get('title', 'Unknown')
        self.artist = data.get('artist', 'Unknown')
        self.album = data.get('album', 'Unknown')
        self.duration = data.get('duration', 0)
        self.path = data.get('path', '')
        self.stream_url = f"{navidrome_url}/rest/stream.view?u={navidrome_username}&p={navidrome_password}&c=bot&id={self.id}&format=raw"
    
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
        self.auth_token = None

    async def navidromeAuthenticate(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'u': self.username, 
                    'p': self.password, 
                    'c': 'Aqua', 
                    'v': '1.16.1',
                    'f': 'json'
                }

                async with session.get(
                    f"{self.url}/rest/ping.view",
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.auth_token = data.get("subsonic-response", {}).get("authentication", {}).get("token")
                        print(f"Successfully authenticated with Navidrome")
                        return True
                    
                    else:
                        text = await response.text()
                        print(f"Failed to authenticate with Navidrome: {text}")
                        return False
                    
        except Exception as e:
            print(f"Error during Navidrome authentication: {e}")
            return False
    
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
        source = discord.FFmpegPCMAudio(
            track.stream_url,
            options="-vn -b:a 128k"
        )
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

@bot.command(name="join")
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel!")
        return
    
    channel = ctx.author.voice.channel
    try:
        await channel.connect()
        await ctx.send(f"Joined {channel.name}")
    except Exception as e:
        await ctx.send(f"Error joining channel: {e}")


#Bot leaves voice channel

@bot.command(name="leave")
async def leave(ctx):
    if not ctx.voice_client:
        await ctx.send("Not in a voice channel!")
        return
    
    queue = get_queue(ctx.guild.id)
    queue.clear()
    await ctx.voice_client.disconnect()
    await ctx.send("Left voice channel")

bot.run(bot_token)
