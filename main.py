from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
from discord import app_commands
import time
import requests
import aiohttp


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



bot.run(bot_token)
