import os
from dotenv import load_dotenv
import asyncio
import discord
from discord import Object
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('TOKEN')
GUILD = os.getenv('GUILD')

if not TOKEN:
    raise SystemExit('TOKEN not set')

intents = discord.Intents.none()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print('Logged in as', bot.user)
    if GUILD:
        guild = Object(id=int(GUILD))
        cmds = await bot.tree.fetch_commands(guild=guild)
        print(f'Guild commands for {GUILD}:')
    else:
        cmds = await bot.tree.fetch_commands()
        print('Global commands:')
    for c in cmds:
        print('-', c.name, '(', getattr(c, 'description', '') ,')')
    await bot.close()

if __name__ == '__main__':
    bot.run(TOKEN)
