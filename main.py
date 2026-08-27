import os
import discord
from discord import app_commands
import requests
import asyncio
import yt_dlp
from musicPlayer import (
    MusicBrowser,
    MusicPlayerView,
    MusicBrowserView,
    get_queue,
    track_autocomplete,
    play_track,
    music_loop
    )
from config import (
    bot, 
    bot_token, 
    guild_id1, 
    guild_id2,
    pve_url,
    headers,
    navidrome_client,
    music_library_path
)


music_browser = MusicBrowser()

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
            await message.channel.send("I don't have permission to send a direct message to that user.", ephemeral = True)
        except Exception as e:
            await message.channel.send(f"An error occurred while trying to send a direct message: {e}", ephemeral = True)

    await bot.process_commands(message)



#-------------------------Proxmox API Functions-------------------------

def get_status(node, vmid):
    r = requests.get(
        f"{pve_url}/api2/json/nodes/{node}/lxc/{vmid}/status/current",
        headers=headers, verify=False
    )
    print(f"[get_status] status_code={r.status_code}, body={r.text!r}")
    return r.json()["data"]["status"]



#-------------------------------------------Discord Commands-------------------------------------------

#-------------------------Minecraft Server Control Commands-------------------------


# Start the minecraft server
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



# Stop the minecraft server
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

# Bot joins your voice channel
@bot.tree.command(name="join", description="Joins your voice channel", guilds=[guild_id1, guild_id2])
async def join(interaction: discord.Interaction):

    await interaction.response.defer()  # Defer the response to give the bot more time to process

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("You need to be in a voice channel!", ephemeral = True)
        return
    
    channel = interaction.user.voice.channel

    try:
        await channel.connect()
        await interaction.followup.send(f"Joined {channel.name}", ephemeral = True)
    except Exception as e:
        await interaction.followup.send(f"Error joining channel: {e}", ephemeral = True)



# Bot leaves voice channel
@bot.tree.command(name="leave", description="Leaves the voice channel", guilds=[guild_id1, guild_id2])
async def leave(interaction: discord.Interaction):
    if not interaction.guild.voice_client or not interaction.guild.voice_client.channel:
        await interaction.response.defer()
        await interaction.followup.send("Not in a voice channel!", ephemeral = True)
        return
    
    queue = get_queue(interaction.guild.id)
    queue.clear()
    await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("Left the voice channel", ephemeral = True)



# Play music
@bot.tree.command(name="playnow", description="Search and play songs (stops current song)", guilds=[guild_id1, guild_id2])
@app_commands.autocomplete(query=track_autocomplete)
async def playNow(interaction: discord.Interaction, query: str):

    await interaction.response.defer()
    
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



# Skip current song
@bot.tree.command(name="skip", description="Skip the current song", guilds=[guild_id1, guild_id2])
async def skip(interaction: discord.Interaction):

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



# Add music to queue
@bot.tree.command(name="play", description="Search and play songs (adds song to the end of the queue)", guilds=[guild_id1, guild_id2])
@app_commands.autocomplete(query=track_autocomplete)
async def play(interaction: discord.Interaction, query: str):

    await interaction.response.defer()
    
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



# Stop playback and clear queue
@bot.tree.command(name="stop", description="Stop playback", guilds=[guild_id1, guild_id2])
async def stop(interaction: discord.Interaction):
    await interaction.response.defer()
    
    voice_client = interaction.guild.voice_client
    if not voice_client:
        await interaction.followup.send("Bot is not in a voice channel!", ephemeral = True)
        return
    
    voice_client.stop()
    await interaction.followup.send("Playback stopped", ephemeral = True)



# Clear queue
@bot.tree.command(name="clear", description="Clear the queue", guilds=[guild_id1, guild_id2])
async def clear_queue(interaction: discord.Interaction):
    await interaction.response.defer()
    
    queue = get_queue(interaction.guild_id)
    queue.clear()
    await interaction.followup.send("Queue cleared", ephemeral = True)



# Display the queue
@bot.tree.command(name="queue", description="Show current queue", guilds=[guild_id1, guild_id2])
async def show_queue(interaction: discord.Interaction):
    await interaction.response.defer()
    
    queue = get_queue(interaction.guild_id)
    
    if not queue.current and not queue.queue:
        await interaction.followup.send("Queue is empty!", ephemeral = True)
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
    
    await interaction.followup.send(embed=embed, ephemeral = True)



# Download music using yt-dlp (YouTube-DL fork)
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
            await interaction.followup.send(f"Successfully added to the music library", ephemeral = True)
        else:
            print(f"Failed to add the song. Error code: {error_code}")
            await interaction.followup.send(f"Failed to add the song. Error code: {error_code}"), ephemeral = True

    except Exception as e:
        print(f"Full error: {type(e).__name__}: {e}")  # Print full details
        import traceback
        traceback.print_exc() 
        await interaction.followup.send(f"An error occurred while adding the song: {e}", ephemeral = True)



# Browse music
@bot.tree.command(name="browse", description="Browse the selection of music", guilds=[guild_id1, guild_id2])
async def browse(interaction: discord.Interaction):
    await interaction.response.defer()

    print("loading music files")
    await music_browser.load_library()

    print("loading embed")
    embed = discord.Embed(title="Song browser", color=discord.Color.purple())
    page_str = "\n".join([f"{track.title}" for i, track in enumerate(MusicBrowser.view_current_page(music_browser))])
    embed.add_field(name="Page " + str(MusicBrowser.get_current_page(music_browser) + 1), value=page_str, inline=False)

    view = MusicBrowserView(music_browser)

    await interaction.followup.send(
        embed=embed,
        view=view,
        ephemeral = True
    )



# Display music player UI
@bot.tree.command(name="player", description="Display the music player", guilds=[guild_id1, guild_id2])
async def player(interaction: discord.Interaction):

    embed = discord.Embed(
            title="🎵 Music Player",
            description="Control your music with the buttons below",
            color=discord.Color.purple()
        )
    
    view = MusicPlayerView()
    
    await interaction.response.send_message(
        embed=embed,
        view=view
    )



# lists all availiable commands
@bot.tree.command(name="help", description="Shows all available commands", guilds=[guild_id1, guild_id2])
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Available Commands", description="Here are all my commands:")
    
    for command in bot.tree.get_commands(guild=discord.Object(id=interaction.guild_id)):
        embed.add_field(name=f"/{command.name}", value=command.description, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral = True)



bot.run(bot_token)