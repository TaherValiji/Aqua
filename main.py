from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
from discord import app_commands
import time
import requests

client_token = os.getenv('CLIENT_TOKEN')
pve_host = os.getenv('PVE_HOST')
pve_user_token = os.getenv('PVE_USER_TOKEN')
guild_id = discord.Object(os.getenv('SERVER_ID'))

load_dotenv()

class Client(commands.Bot):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.lower().startswith('gimme') or message.content.lower().startswith('on in'):
            number : int = int(message.content.split(' ')[-1])
            timestamp = int(time.time())
            countdown = timestamp + number * 60
            await message.channel.send(f'{message.author} is on <t:{countdown}:R>')

    async def on_message_edit(self, before, after):
        await before.channel.send(f'bro think he slick changing: `{before.content}` \n to : `{after.content}`')


intents = discord.Intents.default()
intents.message_content= True

client = Client(command_prefix='/', intents=intents)

headers = {"Authorization": f"PVEAPIToken={pve_user_token}"}


def shutdown_vm(node, vmid):
    r = requests.post(
        f"{pve_host}/api2/json/nodes/{node}/qemu/{vmid}/status/shutdown",
        headers=headers, verify=False
    )
    return r.json()

def get_status(node, vmid):
    r = requests.get(
        f"{pve_host}/api2/json/nodes/{node}/qemu/{vmid}/status/current",
        headers=headers, verify=False
    )
    return r.json()["data"]["status"]


@client.tree.command(name="startserver", description="Starts the minecraft server", guild=guild_id)
async def startServer(interaction: discord.Interaction):
    await interaction.response.send_message("Starting the server...")
    if get_status("pve", 101) == "stopped":
        r = requests.post(
            f"{pve_host}/api2/json/nodes/pve/qemu/101/status/start",
            headers=headers, verify=False
        )
        if r.status_code == 200:
            await interaction.followup.send("Server started successfully!")
        else:
            await interaction.followup.send("Failed to start the server.")
    else:
        await interaction.followup.send("Server is already running.")


@client.tree.command(name="stopserver", description="Stops the minecraft server", guild=guild_id)
async def stopServer(interaction: discord.Interaction):
    await interaction.response.send_message("Stopping the server...")
    if get_status("pve", 101) == "running":
        r = requests.post(
            f"{pve_host}/api2/json/nodes/pve/qemu/101/status/shutdown",
            headers=headers, verify=False
        )
        if r.status_code == 200:
            await interaction.followup.send("Server stopped successfully!")
        else:
            await interaction.followup.send("Failed to stop the server.")
    else:
        await interaction.followup.send("Server is already stopped.")

client.run(client_token)
