import discord
from discord import ui
import os
from dotenv import load_dotenv
import asyncio
import logging
from datetime import datetime

load_dotenv()
TOKEN = os.getenv('TOKEN')
GUILD = os.getenv('GUILD')
CATEGORY = os.getenv('CATEGORY')
EMBARKATION_DECK = os.getenv('EMBARKATION_DECK')
LFG_CHANNEL = os.getenv('LFG_CHANNEL')

# Set up logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log.txt')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # Also print to console
    ]
)

# Update intents for the client
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

# We need to use commands.Bot instead of Client for UI components

from discord.ext import commands
from discord import app_commands
client = commands.Bot(command_prefix='/', intents=intents)


# Dictionary to track created voice channels
created_voice_channels = {}

@client.event
async def on_ready():
    logging.info(f'Bot {client.user} has connected to Discord!')
    try:
        synced = await client.tree.sync()
        logging.info(f'Synced {len(synced)} slash commands.')
    except Exception as e:
        logging.error(f'Failed to sync slash commands: {e}')

@client.event
async def on_voice_state_update(member, before, after):
    """
    Handle voice state updates to track and cleanup empty channels
    """
    try:
        # Check if the user left a voice channel
        if before.channel and before.channel.id in created_voice_channels:
            # Wait a short moment to ensure the state is stable
            await asyncio.sleep(1)
            
            # If the channel is empty
            if len(before.channel.members) == 0:
                try:
                    # Get channel info for logging
                    channel_info = created_voice_channels[before.channel.id]
                    
                    # Delete the channel
                    await before.channel.delete()
                    
                    # Remove from tracking
                    del created_voice_channels[before.channel.id]
                    
                    logging.info(f"Deleted empty voice channel: {channel_info['name']} (ID: {before.channel.id})")
                except Exception as e:
                    logging.error(f"Error deleting channel {before.channel.id}: {str(e)}")

    except Exception as e:
        logging.error(f"Error in voice state update handler: {str(e)}")



# Register as a slash command with options

@client.tree.command(name="req", description="Request a voice channel for your group.")
@app_commands.describe(
    channel_name="Name for your voice channel",
    teammate1="Teammate to move (optional)",
    teammate2="Teammate to move (optional)",
    capacity="Max members (optional)"
)
@app_commands.guild_only()
async def req(
    interaction: discord.Interaction,
    channel_name: str,
    teammate1: discord.Member = None,
    teammate2: discord.Member = None,
    capacity: int = None
):
    try:
        # Check for required environment variables
        if not CATEGORY or not LFG_CHANNEL:
            await interaction.response.send_message("Bot misconfiguration: CATEGORY or LFG_CHANNEL not set.", ephemeral=True)
            logging.error("CATEGORY or LFG_CHANNEL environment variable not set.")
            return

        # Check if the command is used in the LFG channel
        if str(interaction.channel.id) != str(LFG_CHANNEL):
            await interaction.response.send_message("Please use this command in the LFG channel.", ephemeral=True)
            logging.warning(f"User {interaction.user.display_name} attempted to use /req in wrong channel")
            return

        # Validate capacity
        if capacity is not None and (capacity < 1 or capacity > 99):
            await interaction.response.send_message("Capacity must be between 1 and 99.", ephemeral=True)
            return


        # Create the voice channel
        try:
            category_id = int(CATEGORY)
        except (TypeError, ValueError):
            await interaction.response.send_message("Bot misconfiguration: CATEGORY is not a valid channel ID.", ephemeral=True)
            logging.error("CATEGORY environment variable is not a valid integer.")
            return
        category = interaction.guild.get_channel(category_id)
        if not category:
            await interaction.response.send_message("Category channel not found.", ephemeral=True)
            return

        new_channel = await interaction.guild.create_voice_channel(
            name=channel_name,
            user_limit=capacity,
            category=category
        )

        # Add channel to tracking dictionary
        created_voice_channels[new_channel.id] = {
            'name': channel_name,
            'creator': interaction.user.id,
            'created_at': datetime.now()
        }

        logging.info(f"Created voice channel: {channel_name} (ID: {new_channel.id})")


        # Move the command author if they're in a voice channel
        if interaction.user.voice and interaction.user.voice.channel:
            await interaction.user.move_to(new_channel)
            logging.info(f"Moved creator {interaction.user.display_name} to channel {channel_name}")


        # Move valid teammates
        moved_members = []
        for teammate in [teammate1, teammate2]:
            if teammate and teammate.voice and teammate.voice.channel:
                try:
                    await teammate.move_to(new_channel)
                    moved_members.append(teammate.display_name)
                    logging.info(f"Moved member {teammate.display_name} to channel {channel_name}")
                except discord.errors.HTTPException as e:
                    logging.error(f"Failed to move {teammate.display_name}: {str(e)}")
                    continue

        await interaction.response.send_message(
            f"Created channel '{channel_name}' and moved {len(moved_members)} teammates.",
            ephemeral=True
        )

    except Exception as e:
        logging.error(f"Error processing /req command: {str(e)}")
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred while processing your request.", ephemeral=True)


        
client.run(TOKEN)