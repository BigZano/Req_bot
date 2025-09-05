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
EMBARKATION_DECK = os.getenv('CHANNEL')
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
client = commands.Bot(command_prefix='/', intents=intents)

# Dictionary to track created voice channels
created_voice_channels = {}

class VoiceChannelModal(ui.Modal, title='Create Voice Channel'):
    channel_name = ui.TextInput(
        label='Channel Name',
        placeholder='Enter a name for your voice channel',
        required=True,
        max_length=100
    )
    
    members = ui.TextInput(
        label='Members',
        placeholder='@mention members to add (separate with spaces)',
        required=False,
        style=discord.TextStyle.paragraph
    )
    
    capacity = ui.TextInput(
        label='Capacity',
        placeholder='Enter max members (or leave blank for unlimited)',
        required=False,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_name = self.channel_name.value

            capacity = None
            if self.capacity.value:
                try:
                    capacity = int(self.capacity.value)
                    if capacity < 1:
                        capacity = None
                except ValueError:
                    capacity = None
                    logging.warning(f"Invalid capacity value provided: {self.capacity.value}")

            valid_members = []
            embarkation_channel = interaction.guild.get_channel(int(EMBARKATION_DECK))
            
            if embarkation_channel and self.members.value:
                embarkation_members = embarkation_channel.members
                mention_ids = [
                    int(id_str) for id_str in 
                    [m.strip('<@!>') for m in self.members.value.split()]
                    if id_str.isdigit()
                ]
                
                for member_id in mention_ids:
                    member = interaction.guild.get_member(member_id)
                    if member and member in embarkation_members:
                        valid_members.append(member)
                    else:
                        logging.info(f"Member {member_id} not found in Embarkation Deck")

            # Create the voice channel
            category = interaction.guild.get_channel(int(CATEGORY))
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
            if interaction.user.voice:
                await interaction.user.move_to(new_channel)
                logging.info(f"Moved creator {interaction.user.display_name} to channel {channel_name}")

            # Move valid members
            moved_members = []
            for member in valid_members:
                if member.voice:
                    try:
                        await member.move_to(new_channel)
                        moved_members.append(member.display_name)
                        logging.info(f"Moved member {member.display_name} to channel {channel_name}")
                    except discord.errors.HTTPException as e:
                        logging.error(f"Failed to move {member.display_name}: {str(e)}")
                        continue

            await interaction.response.send_message(
                f"Created channel '{channel_name}' and moved {len(moved_members)} members.",
                ephemeral=True
            )

        except Exception as e:
            logging.error(f"Error in channel creation: {str(e)}")
            await interaction.response.send_message(
                f"An error occurred: {str(e)}",
                ephemeral=True
            )

@client.event
async def on_ready():
    logging.info(f'Bot {client.user} has connected to Discord!')

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

@client.command()
async def req(ctx):
    try:
        # Check if the command is used in the LFG channel
        if str(ctx.channel.id) != LFG_CHANNEL:
            await ctx.reply("Please use this command in the LFG channel.")
            logging.warning(f"User {ctx.author.display_name} attempted to use /req in wrong channel")
            return

        # Create and show the modal
        modal = VoiceChannelModal()
        await ctx.send_modal(modal)
        logging.info(f"Sent voice channel creation modal to {ctx.author.display_name}")

    except Exception as e:
        logging.error(f"Error processing /req command: {str(e)}")
        await ctx.reply("An error occurred while processing your request.")


        
client.run(TOKEN)