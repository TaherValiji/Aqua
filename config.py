import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from navidromeClient import NavidromeClient


#-------------------------Environment Setup-------------------------

load_dotenv()

# Bot general settings
bot_token = os.getenv('BOT_TOKEN')
guild_id1 = discord.Object(os.getenv('SERVER_ID1'))
guild_id2 = discord.Object(os.getenv('SERVER_ID2'))

# Proxmox API settings
pve_url = os.getenv('PVE_URL')
pve_user_token = os.getenv('PVE_USER_TOKEN')
headers = {"Authorization": f"PVEAPIToken={pve_user_token}"}

# Navidrome API Settings
navidrome_url = os.getenv('NAVIDROME_URL')
navidrome_username = os.getenv('NAVIDROME_USERNAME')
navidrome_password = os.getenv('NAVIDROME_PASSWORD')
music_library_path = os.getenv('MUSIC_LIBRARY_PATH')



#-------------------------Bot Initialization-------------------------

# Bot setup
intents = discord.Intents.default()
intents.message_content= True
intents.voice_states = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Navidrome client
navidrome_client = NavidromeClient(navidrome_url, navidrome_username, navidrome_password)

# Store music queue for each guild
music_queues = {}