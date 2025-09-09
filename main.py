import discord
from discord import ui
import os
from dotenv import load_dotenv
import asyncio
import logging
from datetime import datetime, timezone
from dateutil import parser
import pytz

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
client.tree = discord.app_commands.CommandTree(client)

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

class TimerModal(ui.Modal, title='Set Timer'):
    target_date = ui.TextInput(
        label='Date and Time',
        placeholder='Example: 2025-09-10 15:30 UTC',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse the input date/time
            target_time = parser.parse(self.target_date.value)
            
            # Convert to UTC for Discord timestamp
            if target_time.tzinfo is None:
                # If no timezone provided, assume UTC
                utc = pytz.UTC
                target_time = utc.localize(target_time)
            
            # Check if the date is in the past
            if target_time < datetime.now(timezone.utc):
                await interaction.response.send_message(
                    "Error: Cannot set a timer for a past date/time.",
                    ephemeral=True
                )
                return

            # Convert to UTC timestamp
            unix_timestamp = int(target_time.timestamp())

            # Create Discord timestamp formats
            relative_timestamp = f"<t:{unix_timestamp}:R>"  # Relative time
            full_timestamp = f"<t:{unix_timestamp}:F>"     # Full date and time
            time_timestamp = f"<t:{unix_timestamp}:t>"     # Time only
            date_timestamp = f"<t:{unix_timestamp}:D>"     # Date only

            # Get time remaining for status indicator
            time_until = target_time - datetime.now(timezone.utc)
            hours_remaining = time_until.total_seconds() / 3600

            # Set status indicator based on time remaining
            if hours_remaining > 24:
                status_emoji = "🟢"  # Green circle for > 24 hours
            elif hours_remaining > 1:
                status_emoji = "🟡"  # Yellow circle for 1-24 hours
            else:
                status_emoji = "🔴"  # Red circle for < 1 hour

            embed = discord.Embed(
                title=f"{status_emoji} Countdown Timer",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Event Time", 
                value=f"• {full_timestamp}\n• {time_timestamp}\n• {date_timestamp}", 
                inline=False
            )
            embed.add_field(
                name="Time Remaining", 
                value=f"Countdown: {relative_timestamp}", 
                inline=False
            )
            embed.set_footer(text=f"Timer created by {interaction.user.display_name}")

            await interaction.response.send_message(embed=embed)
            logging.info(f"Created timer for {target_time} UTC by {interaction.user.display_name}")

            # Start the countdown update loop
            asyncio.create_task(self.update_countdown(interaction, unix_timestamp, embed))

        except Exception as e:
            error_msg = f"Error: Could not parse the date/time. Please use format: YYYY-MM-DD HH:MM UTC\nError details: {str(e)}"
            logging.error(f"Timer creation error by {interaction.user.display_name}: {str(e)}")
            await interaction.response.send_message(error_msg, ephemeral=True)

    async def update_countdown(self, interaction, target_timestamp, original_embed):
        try:
            message = await interaction.original_response()
            
            while True:
                now = datetime.now(timezone.utc)
                target_time = datetime.fromtimestamp(target_timestamp, timezone.utc)
                
                # If we've passed the target time
                if now >= target_time:
                    original_embed.clear_fields()
                    original_embed.add_field(
                        name="Status",
                        value=f"⏰ Time's Up! {interaction.user.mention}",
                        inline=False
                    )
                    original_embed.color = discord.Color.red()
                    await message.edit(embed=original_embed)
                    logging.info(f"Timer completed for event set by {interaction.user.display_name}")
                    break
                
                # Update status indicator based on time remaining
                time_until = target_time - now
                hours_remaining = time_until.total_seconds() / 3600
                
                if hours_remaining > 24:
                    status_emoji = "🟢"
                elif hours_remaining > 1:
                    status_emoji = "🟡"
                else:
                    status_emoji = "🔴"

                original_embed.title = f"{status_emoji} Countdown Timer"
                
                # Update the embed with new relative time
                relative_timestamp = f"<t:{target_timestamp}:R>"
                original_embed.set_field_at(
                    1,  # Index of the "Time Remaining" field
                    name="Time Remaining",
                    value=f"Countdown: {relative_timestamp}",
                    inline=False
                )
                
                await message.edit(embed=original_embed)
                await asyncio.sleep(60)  # Update every minute
        except Exception as e:
            logging.error(f"Error in countdown update: {str(e)}")

@client.event
async def on_ready():
    try:
        synced = await client.tree.sync()
        logging.info(f'Synced {len(synced)} command(s)')
        logging.info(f'Bot {client.user} has connected to Discord!')
    except Exception as e:
        logging.error(f'Failed to sync commands: {str(e)}')

    # Register commands using hybrid commands
    @client.hybrid_command(name="timer")
    async def timer(ctx):
        """Create a new countdown timer"""
        try:
            # Check if the command is used in the LFG channel
            if str(ctx.channel.id) != LFG_CHANNEL:
                await ctx.reply("Please use this command in the LFG channel.")
                logging.warning(f"User {ctx.author.display_name} attempted to use /timer in wrong channel")
                return

            # Create and show the modal
            modal = TimerModal()
            await ctx.send_modal(modal)
            logging.info(f"Sent timer creation modal to {ctx.author.display_name}")

        except Exception as e:
            logging.error(f"Error processing /timer command: {str(e)}")
            await ctx.reply("An error occurred while processing your request.")

    @client.hybrid_command(name="req")
    async def req(ctx):
        """Create a new voice channel"""
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

client.run(TOKEN)