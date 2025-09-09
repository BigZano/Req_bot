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
            
            # Convert to UTC timestamp
            unix_timestamp = int(target_time.timestamp())

            # Create Discord timestamp formats
            relative_timestamp = f"<t:{unix_timestamp}:R>"  # Relative time (e.g., "in 2 hours")
            full_timestamp = f"<t:{unix_timestamp}:F>"     # Full date and time
            time_timestamp = f"<t:{unix_timestamp}:t>"     # Time only
            date_timestamp = f"<t:{unix_timestamp}:D>"     # Date only

            embed = discord.Embed(
                title="⏰ Countdown Timer",
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
                
                # If we've passed the target time, update the embed and stop
                if now >= target_time:
                    original_embed.clear_fields()
                    original_embed.add_field(
                        name="Status",
                        value="⏰ Time's Up!",
                        inline=False
                    )
                    await message.edit(embed=original_embed)
                    logging.info(f"Timer completed for event set by {interaction.user.display_name}")
                    break
                
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

@client.command()
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

@client.event
async def on_ready():
    logging.info(f'Timer Bot {client.user} has connected to Discord!')

client.run(TOKEN)