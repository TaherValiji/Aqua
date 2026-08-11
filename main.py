from dotenv import load_dotenv
import os
import discord
from discord.ext import commands
from discord import app_commands
import time
import requests

load_dotenv()

client_token = os.getenv('CLIENT_TOKEN')
pve_host = os.getenv('PVE_HOST')
pve_user_token = os.getenv('PVE_USER_TOKEN')
guild_id1 = discord.Object(os.getenv('SERVER_ID1'))
guild_id2 = discord.Object(os.getenv('SERVER_ID2'))

class Client(commands.Bot):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

        try:
            sync_to_server1 = await self.tree.sync(guild=guild_id1)
            print(f'Synced {len(sync_to_server1)} commands to guild {guild_id1}.')
            sync_to_server2 = await self.tree.sync(guild=guild_id2)
            print(f'Synced {len(sync_to_server2)} commands to guild {guild_id2}.')

        except Exception as e:
            print(f"Error syncing commands: {e}")

        cmds1 = await self.tree.fetch_commands(guild=guild_id1)
        print([c.name for c in cmds1])

        cmds2 = await self.tree.fetch_commands(guild=guild_id2)
        print([c.name for c in cmds2])


    async def on_message(self, message):
        if message.author == self.user:
            return
        
        if message.content[::-1].startswith(("guys boo him")[::-1]):
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


intents = discord.Intents.default()
intents.message_content= True

client = Client(command_prefix='/', intents=intents)

headers = {"Authorization": f"PVEAPIToken={pve_user_token}"}


def shutdown_vm(node, vmid):
    r = requests.post(
        f"{pve_host}/api2/json/nodes/{node}/lxc/{vmid}/status/shutdown",
        headers=headers, verify=False
    )
    return r.json()

def get_status(node, vmid):
    r = requests.get(
        f"{pve_host}/api2/json/nodes/{node}/lxc/{vmid}/status/current",
        headers=headers, verify=False
    )
    print(f"[get_status] status_code={r.status_code}, body={r.text!r}")
    return r.json()["data"]["status"]


@client.tree.command(name="startserver", description="Starts the minecraft server", guilds=[guild_id1, guild_id2])
async def startServer(interaction: discord.Interaction):
    await interaction.response.send_message("Starting the server...")
    if get_status("pve", 101) == "stopped":
        r = requests.post(
            f"{pve_host}/api2/json/nodes/pve/lxc/101/status/start",
            headers=headers, verify=False
        )
        if r.status_code == 200:
            await interaction.followup.send("Server started successfully!")
        else:
            await interaction.followup.send("Failed to start the server.")
    else:
        await interaction.followup.send("Server is already running.")


@client.tree.command(name="stopserver", description="Stops the minecraft server", guilds=[guild_id1, guild_id2])
async def stopServer(interaction: discord.Interaction):
    await interaction.response.send_message("Stopping the server...")
    if get_status("pve", 101) == "running":
        r = requests.post(
            f"{pve_host}/api2/json/nodes/pve/lxc/101/status/shutdown",
            headers=headers, verify=False
        )
        if r.status_code == 200:
            await interaction.followup.send("Server stopped successfully!")
        else:
            await interaction.followup.send("Failed to stop the server.")
    else:
        await interaction.followup.send("Server is already stopped.")

client.run(client_token)
