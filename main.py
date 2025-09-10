import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('TOKEN')
GUILD = os.getenv('GUILD')  # optional, use for guild sync if set

# Validate required env vars quickly
if not TOKEN:
    raise SystemExit("TOKEN not set in environment")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('log.txt', encoding='utf-8')
    ]
)

# Create logger for this file
logger = logging.getLogger(__name__)

# Create logger for cogs
cog_logger = logging.getLogger('cogs')

# Update intents for the client
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='/', intents=intents, application_id=None)

    async def setup_hook(self):
        # If a guild is configured, clear guild-scoped commands first to remove stray commands
        try:
            if GUILD:
                guild_obj = discord.Object(id=int(GUILD))
                # clear_commands is synchronous; do not await it
                self.tree.clear_commands(guild=guild_obj)
                logger.info("Cleared existing guild commands for guild %s", GUILD)
        except Exception as e:
            logger.warning("Failed to clear existing guild commands: %s", e)

        # Load cogs by importing their modules and adding cog instances
        try:
            import voice_cog
            await self.add_cog(voice_cog.VoiceCog(self))
            logger.info("Loaded cog: voice_cog")
        except Exception as e:
            logger.error("Failed to load voice_cog: %s", e)

        try:
            import timer_cog
            await self.add_cog(timer_cog.TimerCog(self))
            logger.info("Loaded cog: timer_cog")
        except Exception as e:
            logger.error("Failed to load timer_cog: %s", e)

        try:
            import admin_cog
            await self.add_cog(admin_cog.AdminCog(self))
            logger.info("Loaded cog: admin_cog")
        except Exception as e:
            logger.error("Failed to load admin_cog: %s", e)

        # Sync commands to guild if GUILD is set, otherwise global
        try:
            if GUILD:
                guild_obj = discord.Object(id=int(GUILD))
                await self.tree.sync(guild=guild_obj)
                logger.info("Command tree synced to guild %s", GUILD)
            else:
                await self.tree.sync()
                logger.info("Command tree synced globally")
        except Exception as e:
            logger.error("Failed to sync command tree: %s", e)

client = Bot()

@client.event
async def on_connect():
    logger.info("Bot connected to Discord gateway")

@client.event
async def on_ready():
    # Log available commands
    app_cmds = [c.name for c in await client.tree.fetch_commands()] if client.tree else []
    logger.info("Application commands: %s", ", ".join(app_cmds))
    
    # Log guild information
    if GUILD:
        guild = client.get_guild(int(GUILD))
        if guild:
            logger.info("Connected to guild: %s (ID: %s)", guild.name, guild.id)
        else:
            logger.warning("Configured guild ID %s not found", GUILD)
            
    logger.info("Bot %s is ready!", client.user)


# Note: resync is provided by AdminCog in admin_cog.py

client.run(TOKEN)