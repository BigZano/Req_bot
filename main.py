import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('TOKEN')
GUILD = os.getenv('GUILD')

# Validate required env vars
if not TOKEN:
    raise SystemExit("TOKEN not set in environment")

# Set up logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Update intents for the client
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True


class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='/', intents=intents)

    async def setup_hook(self):
        """Load cogs and sync commands"""
        # Load cogs
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

        # Sync commands to guild if GUILD is set, otherwise global
        try:
            if GUILD:
                guild_obj = discord.Object(id=int(GUILD))
                synced = await self.tree.sync(guild=guild_obj)
                logging.info(f'Synced {len(synced)} slash commands to guild {GUILD}.')
            else:
                synced = await self.tree.sync()
                logging.info(f'Synced {len(synced)} slash commands globally.')
        except Exception as e:
            logging.error(f'Failed to sync slash commands: {e}')


client = Bot()


@client.event
async def on_ready():
    logging.info(f'Bot {client.user} has connected to Discord!')


@client.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    """Handle app command errors gracefully"""
    try:
        if isinstance(error, discord.app_commands.CommandNotFound):
            # Handle stale commands that Discord still has cached
            try:
                await interaction.response.send_message(
                    "⚠️ This command has been updated. Please try using `/request` for voice channels or `/set` for timers. Discord will refresh the command list automatically.",
                    ephemeral=True
                )
            except Exception:
                try:
                    await interaction.followup.send(
                        "⚠️ This command has been updated. Please try using `/request` for voice channels or `/set` for timers.",
                        ephemeral=True
                    )
                except Exception:
                    pass
            
            # Log the error for debugging
            cmd_name = getattr(interaction.data, 'name', 'unknown') if hasattr(interaction, 'data') else 'unknown'
            logging.warning(f"Stale command '{cmd_name}' invoked by {interaction.user.display_name} (ID: {interaction.user.id})")
            return
        
        # Handle other app command errors
        logging.error(f"App command error: {error}", exc_info=True)
        try:
            await interaction.response.send_message("An error occurred while processing your command.", ephemeral=True)
        except Exception:
            try:
                await interaction.followup.send("An error occurred while processing your command.", ephemeral=True)
            except Exception:
                pass
                
    except Exception as handler_error:
        logging.error(f"Error in app command error handler: {handler_error}", exc_info=True)


if __name__ == '__main__':
    client.run(TOKEN)