from discord import app_commands, Interaction
import discord
import os
from discord.ext import commands
import logging
import asyncio
from datetime import datetime

# Use the shared 'cogs' logger by name to avoid circular import with main
logger = logging.getLogger('cogs')

# Modal removed; we use inline command parameters for /req

class VoiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.created_channels = {}
        self._setup_config()
    # app command methods in this cog are registered when the cog is added by the bot
        
    def _setup_config(self):
        self.category_id = os.getenv('CATEGORY')
        self.embarkation_deck_id = os.getenv('CHANNEL')
        self.lfg_channel_id = os.getenv('LFG_CHANNEL')

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("[Voice] Cog is ready")

    @app_commands.command(name="req", description="Request a private voice channel")
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD'))))
    @app_commands.describe(
        channel_name="Name for your voice channel",
        teammate1="Teammate to move (optional)",
        teammate2="Teammate to move (optional)",
        capacity="Max members (optional)"
    )
    async def req(self, interaction: Interaction, channel_name: str, teammate1: discord.Member = None, teammate2: discord.Member = None, capacity: int = None):
        """Inline parameter version of /req matching the original main.py behavior."""
        # Reuse handle_channel_creation logic by delegating with parsed params
        await self._req_inline(interaction, channel_name, teammate1, teammate2, capacity)

    async def _req_inline(self, interaction: Interaction, channel_name: str, teammate1: discord.Member = None, teammate2: discord.Member = None, capacity: int = None):
        try:
            # Check for required configuration
            if not self.category_id or not self.lfg_channel_id:
                await interaction.response.send_message("Bot misconfiguration: CATEGORY or LFG_CHANNEL not set.", ephemeral=True)
                logger.error("CATEGORY or LFG_CHANNEL environment variable not set.")
                return

            # Check if the command is used in the correct LFG channel
            if str(interaction.channel.id) != str(self.lfg_channel_id):
                await interaction.response.send_message("Please use this command in the LFG channel.", ephemeral=True)
                logger.warning(f"User {interaction.user.display_name} attempted to use /req in wrong channel")
                return

            # Validate capacity
            if capacity is not None and (capacity < 1 or capacity > 99):
                await interaction.response.send_message("Capacity must be between 1 and 99.", ephemeral=True)
                return

            # Resolve category
            try:
                category = interaction.guild.get_channel(int(self.category_id))
            except (TypeError, ValueError):
                await interaction.response.send_message("Bot misconfiguration: CATEGORY is not a valid channel ID.", ephemeral=True)
                logger.error("CATEGORY environment variable is not a valid integer.")
                return

            if not category:
                await interaction.response.send_message("Category channel not found.", ephemeral=True)
                return

            # Create the voice channel
            new_channel = await interaction.guild.create_voice_channel(
                name=channel_name,
                user_limit=capacity,
                category=category
            )

            # Track channel
            self.created_channels[new_channel.id] = {
                'name': channel_name,
                'creator': interaction.user.id,
                'created_at': datetime.now()
            }

            logger.info(f"Created voice channel: {channel_name} (ID: {new_channel.id})")

            # Move the creator if they're in a voice channel
            moved_members = []
            if interaction.user.voice and interaction.user.voice.channel:
                await interaction.user.move_to(new_channel)
                moved_members.append(interaction.user.display_name)
                logger.info(f"Moved creator {interaction.user.display_name} to channel {channel_name}")

            # Move teammates
            for teammate in [teammate1, teammate2]:
                if teammate and teammate.voice and teammate.voice.channel:
                    try:
                        await teammate.move_to(new_channel)
                        moved_members.append(teammate.display_name)
                        logger.info(f"Moved member {teammate.display_name} to channel {channel_name}")
                    except discord.errors.HTTPException as e:
                        logger.error(f"Failed to move {teammate.display_name}: {str(e)}")
                        continue

            await interaction.response.send_message(
                f"Created channel '{channel_name}' and moved {len(moved_members)} teammates.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"[Voice] Failed to create voice channel: {str(e)}")
            try:
                await interaction.response.send_message(
                    "Failed to create voice channel. Please try again.",
                    ephemeral=True
                )
            except Exception:
                pass

    async def handle_channel_creation(self, interaction: Interaction, name: str, members_str: str, capacity_str: str):
        try:
            # This block mirrors the original main.py /req implementation.
            # Parse capacity
            capacity = None
            if capacity_str:
                try:
                    capacity = int(capacity_str)
                    if capacity < 1:
                        capacity = None
                except ValueError:
                    pass

            # Parse up to two teammates from the members_str (space-separated mentions or IDs)
            teammate_objs = []
            if members_str:
                tokens = members_str.split()
                for tok in tokens[:2]:
                    id_str = tok.strip('<@!>')
                    if id_str.isdigit():
                        member = interaction.guild.get_member(int(id_str))
                        if member:
                            teammate_objs.append(member)

            # Validate category configuration
            if not self.category_id or not self.lfg_channel_id:
                await interaction.response.send_message("Bot misconfiguration: CATEGORY or LFG_CHANNEL not set.", ephemeral=True)
                logger.error("CATEGORY or LFG_CHANNEL environment variable not set.")
                return

            # Ensure command used in configured LFG channel
            try:
                if str(interaction.channel.id) != str(self.lfg_channel_id):
                    await interaction.response.send_message("Please use this command in the LFG channel.", ephemeral=True)
                    logger.warning(f"User {interaction.user.display_name} attempted to use /req in wrong channel")
                    return
            except Exception:
                # Fall back to configured check failure
                await interaction.response.send_message("Please use this command in the LFG channel.", ephemeral=True)
                return

            # Validate capacity range
            if capacity is not None and (capacity < 1 or capacity > 99):
                await interaction.response.send_message("Capacity must be between 1 and 99.", ephemeral=True)
                return

            # Resolve category object
            try:
                category = interaction.guild.get_channel(int(self.category_id))
            except (TypeError, ValueError):
                await interaction.response.send_message("Bot misconfiguration: CATEGORY is not a valid channel ID.", ephemeral=True)
                logger.error("CATEGORY environment variable is not a valid integer.")
                return

            if not category:
                await interaction.response.send_message("Category channel not found.", ephemeral=True)
                return

            # Create the voice channel
            new_channel = await interaction.guild.create_voice_channel(
                name=name,
                user_limit=capacity,
                category=category
            )

            # Track channel like original
            self.created_channels[new_channel.id] = {
                'name': name,
                'creator': interaction.user.id,
                'created_at': datetime.now()
            }

            logger.info(f"Created voice channel: {name} (ID: {new_channel.id})")

            # Move the creator if they're in voice
            moved_members = []
            if interaction.user.voice and interaction.user.voice.channel:
                await interaction.user.move_to(new_channel)
                moved_members.append(interaction.user.display_name)
                logger.info(f"Moved creator {interaction.user.display_name} to channel {name}")

            # Move parsed teammates if they are in voice channels
            for teammate in teammate_objs:
                if teammate and teammate.voice and teammate.voice.channel:
                    try:
                        await teammate.move_to(new_channel)
                        moved_members.append(teammate.display_name)
                        logger.info(f"Moved member {teammate.display_name} to channel {name}")
                    except discord.errors.HTTPException as e:
                        logger.error(f"Failed to move {teammate.display_name}: {str(e)}")
                        continue

            await interaction.response.send_message(
                f"Created channel '{name}' and moved {len(moved_members)} teammates.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"[Voice] Failed to create voice channel: {str(e)}")
            try:
                await interaction.response.send_message(
                    "Failed to create voice channel. Please try again.",
                    ephemeral=True
                )
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle cleanup of empty voice channels"""
        if before.channel and before.channel.id in self.created_channels:
            # Wait briefly to ensure state is stable
            await asyncio.sleep(1)
            
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete()
                    del self.created_channels[before.channel.id]
                except Exception as e:
                    logger.error("[Voice] Failed to delete empty channel: %s", e)

async def setup(bot):
    await bot.add_cog(VoiceCog(bot))
