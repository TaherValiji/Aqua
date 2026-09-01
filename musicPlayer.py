from typing import List
import discord
from config import (
    music_queues,
    bot,
    navidrome_client
    )
import asyncio
from discord import app_commands
from musicPlayerModels import (
    Playlist,
    Track,
    MusicQueue
    )



#-------------------------Music Browser-------------------------

class MusicBrowser:
    def __init__(self):
        self.all_songs = []
        self.current_page = 0
        self.page_size = 10

    def get_current_page(self):
        return self.current_page

    #   Load all songs once on startup
    async def load_library(self):
        self.all_songs = await navidrome_client.getAllSongs()
        print(f"Loaded {len(self.all_songs)} songs")

    #   Get the current 25 songs
    def view_current_page(self):
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self.all_songs[start:end]

    #   Incerment current_page
    def next_page(self):
        max_pages = (len(self.all_songs) + self.page_size - 1) // self.page_size
        if self.current_page < max_pages - 1:
            self.current_page += 1
            return

    #   Decrement current_page
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            return


class MusicBrowserView(discord.ui.View):
    def __init__(self, music_browser: MusicBrowser, timeout=None):
        super().__init__(timeout=timeout)
        self.music_browser = music_browser


    #   Previous page button
    @discord.ui.button(label="Prev", style=discord.ButtonStyle.danger)
    async def previous_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        self.music_browser.prev_page()
        embed = discord.Embed(title="Song browser", color=discord.Color.purple())
        page_str = "\n".join([f"{track}" for i, track in enumerate(self.music_browser.view_current_page())])
        embed.add_field(name="Page " + str(self.music_browser.get_current_page()), value=page_str, inline=False)

        view = MusicBrowserView(self.music_browser)
        
        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral = True
            )


    #   Next page button
    @discord.ui.button(label="Next", style=discord.ButtonStyle.success)
    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        self.music_browser.next_page()
        embed = discord.Embed(title="Song browser", color=discord.Color.purple())
        page_str = "\n".join([f"{track}" for i, track in enumerate(self.music_browser.view_current_page())])
        embed.add_field(name="Page " + str(self.music_browser.get_current_page()), value=page_str, inline=False)

        view = MusicBrowserView(self.music_browser)
        
        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral = True
            )



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
                await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.", ephemeral = True)
                return
        
        queue = get_queue(interaction.guild_id)
        
        if not queue.is_playing:
            await interaction.followup.send("Bot is not playing songs from queue.", ephemeral = True)
            return
            
        else:
            if queue.loop_mode == 2:
                track = queue.current()
                await interaction.followup.send(f'Playing: {track.title} - {track.artist}', ephemeral = True)
                await play_track(voice_client, queue.current(), interaction.guild_id)
            else:
                track = queue.next()
                voice_client.stop()
                await interaction.followup.send(f'Playing: {track.title} - {track.artist}', ephemeral = True)
                await play_track(voice_client, queue.next(), interaction.guild_id)


    # Stop button to stop playback
    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.followup.send("Bot is not in a voice channel!", ephemeral = True)
            return
        
        await interaction.response.send_message("Playback stopped", ephemeral=True)
        
        voice_client.stop()


    # Button to clear queue
    @discord.ui.button(label="Clear queue", style=discord.ButtonStyle.danger)
    async def clearQueue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()    
        queue = get_queue(interaction.guild_id)
        queue.clear()
        await interaction.followup.send("Queue cleared", ephemeral = True)


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
        
        await interaction.followup.send(embed=embed, ephemeral = True)



#-------------------------Music Player Functions-------------------------

# Get or create queue for guild
def get_queue(guild_id: int) -> MusicQueue:
    if guild_id not in music_queues:
        music_queues[guild_id] = MusicQueue()
    return music_queues[guild_id]



# Play a track in voice channel
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



# Auto-play next track in queue
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



# Autocomplete for the add play command
async def track_autocomplete(interaction: discord.Interaction, current: str,) -> List[app_commands.Choice[str]]:
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

# Autocomplete for the add playlist command
async def playlist_autocomplete(interaction: discord.Interaction, current:str) -> List[app_commands.Choice[str]]:
    results = await navidrome_client.getPlaylists()
    
    # Return up to 25 choices (Discord limit)
    choices = [
        app_commands.Choice(
            name=f"{playlist.name} - {playlist.songCount} songs",
            value=f"{playlist.id}|{playlist.name}|{playlist.songCount}"
        )
        for playlist in results[:25]
    ]
    return choices

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
            await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.", ephemeral = True)
            return

        results = await navidrome_client.search(query)
        
        if not results:
            await interaction.followup.send(f'Could not find the track', ephemeral = True)
            return

        print(results)
        track = results[0]
        queue = get_queue(interaction.guild_id)
        queue.is_playing = False
        voice_client.stop()
        await interaction.followup.send(f'playing: {track.title} - {track.artist}', ephemeral = True)
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
            await interaction.followup.send("Bot is not in a voice channel! Use `/join` first.", ephemeral = True)
            return
    
        results = await navidrome_client.search(query)
        
        if not results:
            await interaction.followup.send(f'Could not find the track', ephemeral = True)
            return
    
        print(results)
        track = results[0]
        queue = get_queue(interaction.guild_id)
        queue.add(track)
        await interaction.followup.send(f'Playing: {track.title} - {track.artist}', ephemeral = True)
    
        # Start music loop if not already running
        if not queue.is_playing:
            queue.is_playing = True
            await play_track(voice_client, queue.next(), interaction.guild_id)
            asyncio.create_task(music_loop(interaction.guild_id))