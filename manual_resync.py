import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()
TOKEN = os.getenv('TOKEN')
GUILD = os.getenv('GUILD')

# Validate required env vars
if not TOKEN:
    raise SystemExit("TOKEN not set in environment")

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Update intents for the client
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

class ResyncBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='/', intents=intents)

    async def setup_hook(self):
        """Load cogs and then clear/resync commands"""
        logging.info("Loading cogs...")
        
        # Load cogs first
        try:
            await self.load_extension('voice_cog')
            logging.info('Loaded cog: voice_cog')
        except Exception as e:
            logging.error(f'Failed to load voice_cog: {e}')

        try:
            await self.load_extension('timer_cog')
            logging.info('Loaded cog: timer_cog')
        except Exception as e:
            logging.error(f'Failed to load timer_cog: {e}')

        try:
            await self.load_extension('admin_cog')
            logging.info('Loaded cog: admin_cog')
        except Exception as e:
            logging.error(f'Failed to load admin_cog: {e}')

    async def on_ready(self):
        logging.info(f'Bot {self.user} has connected to Discord!')
        
        # Now clear and resync commands
        try:
            if GUILD:
                guild_obj = discord.Object(id=int(GUILD))
                logging.info("Clearing guild commands...")
                self.tree.clear_commands(guild=guild_obj)
                
                logging.info("Syncing new commands...")
                synced = await self.tree.sync(guild=guild_obj)
                logging.info(f'✅ Cleared and synced {len(synced)} slash commands to guild {GUILD}.')
            else:
                logging.info("Clearing global commands...")
                self.tree.clear_commands()
                
                logging.info("Syncing new commands...")
                synced = await self.tree.sync()
                logging.info(f'✅ Cleared and synced {len(synced)} slash commands globally.')
                
        except Exception as e:
            logging.error(f'Failed to resync commands: {e}')
        
        # Wait a moment then exit
        await asyncio.sleep(2)
        logging.info("Resync complete - shutting down...")
        await self.close()

if __name__ == '__main__':
    client = ResyncBot()
    client.run(TOKEN)
    print("\n🎉 Command resync completed! The stale commands should now be cleared.")
