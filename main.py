import secrets
from statistics import mode
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
from musicPlayer import Track, MusicQueue
from navidromeClient import NavidromeClient

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
    
navidrome_client = NavidromeClient(navidrome_url, navidrome_username, navidrome_password)
music_queues = {}  # Store queue for each guild


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

def get_status(node, vmid):
    r = requests.get(
        f"{pve_url}/api2/json/nodes/{node}/lxc/{vmid}/status/current",
        headers=headers, verify=False
    )
    print(f"[get_status] status_code={r.status_code}, body={r.text!r}")
    return r.json()["data"]["status"]


#-------------------------Discord Modal UI-------------------------

class PlayNowSongModal(discord.ui.Modal, title="Search and play songs"):

    query_input = discord.ui.TextInput(
        label="Song title or query",
        placeholder="Enter song name, artist, or URL...",
        required=True,
        max_length=100,
        min_length=1
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        query = self.query_input.value.strip()

        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.")
            return

        results = await navidrome_client.search(query)
        
        if not results:
            await interaction.followup.send(f'Could not find the track')
            return

        print(results)
        track = results[0]
        queue = get_queue(interaction.guild_id)
        queue.is_playing = False
        voice_client.stop()
        await interaction.followup.send(f'playing: {track.title} - {track.artist}')
        await play_track(voice_client, track, interaction.guild_id)

        # Start music loop if not already running
        if not queue.is_playing:
            queue.is_playing = True
            await play_track(voice_client, queue.next(), interaction.guild_id)
            asyncio.create_task(music_loop(interaction.guild_id))

class PlaySongModal(discord.ui.Modal, title="Add a song to the queue"):

    query_input = discord.ui.TextInput(
        label="Song Title or Query",
        placeholder="Enter song name, artist, or URL...",
        required=True,
        max_length=100,
        min_length=1
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        query = self.query_input.value.strip()
            
        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.")
            return
    
        results = await navidrome_client.search(query)
        
        if not results:
            await interaction.followup.send(f'Could not find the track')
            return
    
        print(results)
        track = results[0]
        queue = get_queue(interaction.guild_id)
        queue.add(track)
        await interaction.followup.send(f'Playing: {track.title} - {track.artist}')
    
        # Start music loop if not already running
        if not queue.is_playing:
            queue.is_playing = True
            await play_track(voice_client, queue.next(), interaction.guild_id)
            asyncio.create_task(music_loop(interaction.guild_id))
#-------------------------Discord UI Components-------------------------

class MusicPlayerView(discord.ui.View):
    def __init__(self, timeout=None):
        super().__init__(timeout=timeout)

    # Play song
    @discord.ui.button(label="Play now", style=discord.ButtonStyle.success)
    async def playNow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PlayNowSongModal())

    # Add song to queue
    @discord.ui.button(label="Queue song", style=discord.ButtonStyle.success)
    async def queueAdd_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PlaySongModal())

    # Skip button to skip to the next song
    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        voice_client = interaction.guild.voice_client
        if not voice_client:
                await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.")
                return
        
        queue = get_queue(interaction.guild_id)
        
        if not queue.is_playing:
            await interaction.followup.send("Bot is not playing songs from queue.")
            return
            
        else:
            if queue.loop_mode == 2:
                track = queue.current()
                await interaction.followup.send(f'Playing: {track.title} - {track.artist}')
                await play_track(voice_client, queue.current(), interaction.guild_id)
            else:
                track = queue.next()
                voice_client.stop()
                await interaction.followup.send(f'Playing: {track.title} - {track.artist}')
                await play_track(voice_client, queue.next(), interaction.guild_id)

    # Stop button to stop playback
    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.followup.send("Bot is not in a voice channel!")
            return
        
        await interaction.response.send_message("Playback stopped", ephemeral=True)
        
        voice_client.stop()

    # Button to clear queue
    @discord.ui.button(label="Clear queue", style=discord.ButtonStyle.danger)
    async def clearQueue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()    
        queue = get_queue(interaction.guild_id)
        queue.clear()
        await interaction.followup.send("Queue cleared")

    # Loop button callback
    @discord.ui.button(label="Loop", style=discord.ButtonStyle.primary)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        queue = get_queue(interaction.guild_id)
        next_mode = (queue.loop_mode + 1) % 3
        queue.set_loop_mode(next_mode)
        
        mode_names = {
            0: "No Loop",
            1: "Queue Loop",
            2: "Song Loop"
        }
        
        mode_name = mode_names[next_mode]
        
        await interaction.response.send_message(f"Loop mode changed to: {mode_name}", ephemeral=True)

    # Button to view the queue
    @discord.ui.button(label="View queue", style=discord.ButtonStyle.secondary)
    async def viewQueue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
            
        queue = get_queue(interaction.guild_id)
        
        if not queue.current and not queue.queue:
            await interaction.followup.send("Queue is empty!")
            return
        
        embed = discord.Embed(title="Music Queue", color=discord.Color.blue())
        
        if queue.current:
            embed.add_field(name="Now Playing", value=str(queue.current), inline=False)
        
        if queue.queue:
            queue_str = "\n".join([f"{i+1}. {track}" for i, track in enumerate(queue.queue[:10])])
            embed.add_field(name="Up Next", value=queue_str, inline=False)
            
            if len(queue) > 10:
                embed.add_field(name="More", value=f"... and {len(queue) - 10} more", inline=False)
        
        await interaction.followup.send(embed=embed)

            
def create_player_embed():
    """Create the music player embed"""
    embed = discord.Embed(
        title="🎵 Music Player",
        description="Control your music with the buttons below",
        color=discord.Color.purple()
    )
    return embed


#-------------------------Music Player Functions-------------------------

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
            next_track = None
            
            if queue.loop_mode == 2: #song loop
                next_track = queue.current

            elif queue.loop_mode == 1: #queue loop
                next_track = queue.next()

                if not next_track and queue.original_queue:
                    queue.queue = queue.original_queue.copy()
                    next_track = queue.next()
            else: #no loop
                next_track = queue.next()
            
            if next_track:
                await play_track(voice_client, next_track, guild_id)
            else:
                queue.is_playing = False


#Autocomplete for the play command
async def track_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    if len(current) < 2:
        return []
    
    results = await navidrome_client.search(current)
    
    # Return up to 25 choices (Discord limit)
    choices = [
        app_commands.Choice(
            name=f"{track.title} - {track.artist}",
            value=track.title
        )
        for track in results[:25]
    ]
    return choices


#-------------------------------------------Discord Commands-------------------------------------------

#-------------------------Minecraft Server Control Commands-------------------------

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



#-------------------------Music Player Commands-------------------------


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


#   Play Music
@bot.tree.command(name="playnow", description="Search and play songs", guilds=[guild_id1, guild_id2])
@app_commands.autocomplete(query=track_autocomplete)
async def playNow(interaction: discord.Interaction, query: str):

    await interaction.response.defer()
    
    voice_client = interaction.guild.voice_client
    if not voice_client:
        await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.")
        return

    results = await navidrome_client.search(query)
    
    if not results:
        await interaction.followup.send(f'Could not find the track')
        return

    print(results)
    track = results[0]
    queue = get_queue(interaction.guild_id)
    queue.is_playing = False
    voice_client.stop()
    await interaction.followup.send(f'playing: {track.title} - {track.artist}')
    await play_track(voice_client, track, interaction.guild_id)

    # Start music loop if not already running
    if not queue.is_playing:
        queue.is_playing = True
        await play_track(voice_client, queue.next(), interaction.guild_id)
        asyncio.create_task(music_loop(interaction.guild_id))

@bot.tree.command(name="skip", description="skip the current song", guilds=[guild_id1, guild_id2])
async def skip(interaction: discord.Interaction):

    await interaction.response.defer()

    voice_client = interaction.guild.voice_client
    if not voice_client:
            await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.")
            return

    queue = get_queue(interaction.guild_id)

    if not queue.is_playing:
        await interaction.followup.send("Bot is not playing songs from queue.")
        return
    
    else:
        if queue.loop_mode == 2:
            track = queue.current()
            await interaction.followup.send(f'Playing: {track.title} - {track.artist}')
            await play_track(voice_client, queue.current(), interaction.guild_id)
        else:
            track = queue.next()
            voice_client.stop()
            await interaction.followup.send(f'Playing: {track.title} - {track.artist}')
            await play_track(voice_client, queue.next(), interaction.guild_id)
    
#   Add music to Queue Music
@bot.tree.command(name="play", description="Search and play songs", guilds=[guild_id1, guild_id2])
@app_commands.autocomplete(query=track_autocomplete)
async def play(interaction: discord.Interaction, query: str):

    await interaction.response.defer()
    
    voice_client = interaction.guild.voice_client
    if not voice_client:
        await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.")
        return

    results = await navidrome_client.search(query)
    
    if not results:
        await interaction.followup.send(f'Could not find the track')
        return

    print(results)
    track = results[0]
    queue = get_queue(interaction.guild_id)
    queue.add(track)
    await interaction.followup.send(f'Playing: {track.title} - {track.artist}')

    # Start music loop if not already running
    if not queue.is_playing:
        queue.is_playing = True
        await play_track(voice_client, queue.next(), interaction.guild_id)
        asyncio.create_task(music_loop(interaction.guild_id))

#Stop playback and clear queue
@bot.tree.command(name="stop", description="Stop playback", guilds=[guild_id1, guild_id2])
async def stop(interaction: discord.Interaction):
    await interaction.response.defer()
    
    voice_client = interaction.guild.voice_client
    if not voice_client:
        await interaction.followup.send("Bot is not in a voice channel!")
        return
    
    voice_client.stop()
    await interaction.followup.send("Playback stopped")


#Clear queue
@bot.tree.command(name="clear", description="Clear the queue", guilds=[guild_id1, guild_id2])
async def clear_queue(interaction: discord.Interaction):
    await interaction.response.defer()
    
    queue = get_queue(interaction.guild_id)
    queue.clear()
    await interaction.followup.send("Queue cleared")


#display the queue
@bot.tree.command(name="queue", description="Show current queue", guilds=[guild_id1, guild_id2])
async def show_queue(interaction: discord.Interaction):
    await interaction.response.defer()
    
    queue = get_queue(interaction.guild_id)
    
    if not queue.current and not queue.queue:
        await interaction.followup.send("Queue is empty!")
        return
    
    embed = discord.Embed(title="Music Queue", color=discord.Color.blue())
    
    if queue.current:
        embed.add_field(name="Now Playing", value=str(queue.current), inline=False)
    
    if queue.queue:
        queue_str = "\n".join([f"{i+1}. {track}" for i, track in enumerate(queue.queue[:10])])
        embed.add_field(name="Up Next", value=queue_str, inline=False)
        
        if len(queue) > 10:
            embed.add_field(name="More", value=f"... and {len(queue) - 10} more", inline=False)
    
    await interaction.followup.send(embed=embed)


# Cycle loop mode
@bot.tree.command(name="loop", description="Cycle loop mode: no loop → queue loop → song loop", guilds=[guild_id1, guild_id2])
async def loop_cmd(interaction: discord.Interaction):

    await interaction.response.defer()
    
    queue = get_queue(interaction.guild_id)
    
    next_mode = (queue.loop_mode + 1) % 3
    queue.set_loop_mode(next_mode)
    
    mode_names = {
        0: "No Loop",
        1: "Queue Loop",
        2: "Song Loop"
    }
    
    mode_name = mode_names[next_mode]
    
    embed = discord.Embed(title="Loop mode changed", color=discord.Color.blue())
    embed.add_field(name="Mode", value=mode_name, inline=False)
    
    await interaction.followup.send(embed=embed)


#   Download music using yt-dlp (YouTube-DL fork)
@bot.tree.command(name="get", description="Get new songs", guilds=[guild_id1, guild_id2])
async def get(interaction: discord.Interaction, url: str):

    await interaction.response.defer(thinking=True)

    os.makedirs(music_library_path, exist_ok=True)

    ydl_opts = {
    'format': 'm4a/bestaudio/best',
    'js_runtimes': {'node': {}},
    'outtmpl': os.path.join(music_library_path, '%(title)s.%(ext)s'),
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    },
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a',
    }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download([url])

        if error_code == 0:
            await interaction.followup.send(f"Successfully added to the music library")
        else:
            print(f"Failed to add the song. Error code: {error_code}")
            await interaction.followup.send(f"Failed to add the song. Error code: {error_code}")

    except Exception as e:
        print(f"Full error: {type(e).__name__}: {e}")  # Print full details
        import traceback
        traceback.print_exc() 
        await interaction.followup.send(f"An error occurred while adding the song: {e}")


# Display music player UI
@bot.tree.command(name="player", description="Display the music player", guilds=[guild_id1, guild_id2])
async def player(interaction: discord.Interaction):
    embed = create_player_embed()
    view = MusicPlayerView()
    
    await interaction.response.send_message(
        embed=embed,
        view=view
    )

bot.run(bot_token)
