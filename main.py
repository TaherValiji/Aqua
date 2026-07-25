import discord
from discord.ext import commands
from discord import app_commands
import time


class Client(commands.Bot):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.startswith('hello'):
            await message.channel.send(f'Hi there {message.author}')

        if message.content.lower().startswith('gimme') or message.content.lower().startswith('on in'):
            number : int = int(message.content.split(' ')[-1])
            timestamp = int(time.time())
            countdown = timestamp + number * 60
            await message.channel.send(f'{message.author} is on <t:{countdown}:R>')

    async def on_message_edit(self, before, after):
        print(f'before: {before.content} after: {after.content}')
    


intents = discord.Intents.default()
intents.message_content= True

client = Client(command_prefix='/', intents=intents)

@client.tree.command(name="startServer", description="Starts the minecraft server")
async def startServer(interaction: discord.Interaction):
    await interaction.response.send_message("Starting the server...")
    # Add your logic to start the Minecraft server here


client.run('MTUzMDYwMzA5MzkyMDg0NTk5Ng.GQ5o69.7U911QVECy3nu18LH3OFskywK2Smm5Yd4jTiCU')