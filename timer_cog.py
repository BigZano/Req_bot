from discord import app_commands, Interaction
import discord
from discord.ext import commands
import os
from datetime import datetime, timezone, timedelta
import asyncio
import logging

# Use the shared 'cogs' logger by name to avoid circular import with main
logger = logging.getLogger('cogs')

# Inline command parameters will be used for /set (amount, unit, description)

class TimerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.display_channel = None
        self.timer_channel = None
        self._setup_channels()
    # app command methods in this cog are registered when the cog is added by the bot

    def _setup_channels(self):
        import os
        self.timer_channel_id = os.getenv('TIMER_CHANNEL')
        self.display_channel_id = os.getenv('TIMER_CHANNEL_DISPLAY')
        if not all([self.timer_channel_id, self.display_channel_id]):
            logger.warning("[Timer] Channels not properly configured in environment")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("[Timer] Cog is ready")

    @app_commands.command(name="set", description="Create a new countdown timer")
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD'))))
    @app_commands.describe(
        days="Days (0 or more)",
        hours="Hours (0-23)",
        minutes="Minutes (0-59)",
        description="Optional description"
    )
    async def set_timer(self, interaction: Interaction, days: int = 0, hours: int = 0, minutes: int = 0, description: str = None):
        if not self.timer_channel_id:
            await interaction.response.send_message("Timer channel not configured.", ephemeral=True)
            return

        try:
            if str(interaction.channel_id) != self.timer_channel_id:
                await interaction.response.send_message(
                    f"Please use this command in <#{self.timer_channel_id}>",
                    ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message("Invalid timer channel configuration.", ephemeral=True)
            return

        # Validate numeric fields
        try:
            if days < 0 or hours < 0 or minutes < 0:
                raise ValueError()
            if hours > 23 or minutes > 59:
                raise ValueError()
        except Exception:
            await interaction.response.send_message("Invalid time fields. Use non-negative values; hours 0-23, minutes 0-59.", ephemeral=True)
            return

        total_seconds = days * 86400 + hours * 3600 + minutes * 60
        if total_seconds <= 0:
            await interaction.response.send_message("Duration must be greater than zero.", ephemeral=True)
            return

        desc = description.strip() if description else None

        now = datetime.now(tz=timezone.utc)
        target_dt = now + timedelta(seconds=total_seconds)
        target_ts = int(target_dt.timestamp())

        remaining = max(0, target_ts - int(datetime.now(tz=timezone.utc).timestamp()))

        embed = discord.Embed(
            title="⏰ Countdown Timer",
            description=desc or "No description provided.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Ends At (UTC)",
            value=target_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        embed.add_field(name="Time Remaining", value=self.format_hms(remaining))
        embed.set_footer(
            text=f"Created by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
        )

        try:
            display_channel = self.bot.get_channel(int(self.display_channel_id))
            if not display_channel:
                display_channel = await self.bot.fetch_channel(int(self.display_channel_id))

            msg = await display_channel.send(embed=embed)
            await interaction.response.send_message(
                f"Timer created and posted in {display_channel.mention}",
                ephemeral=True
            )

            # Start countdown task (updates every second for HH:MM:SS style)
            self.bot.loop.create_task(self.update_countdown(msg, target_ts, interaction.user))
        except Exception as e:
            logger.error("[Timer] Failed to create timer: %s", e)
            await interaction.response.send_message(
                "Failed to create timer. Please try again.",
                ephemeral=True
            )

    # Modal-based handler removed; /set now uses inline parameters above

    @staticmethod
    def format_remaining(seconds: int) -> str:
        seconds = max(0, int(seconds))
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return " ".join(parts)

    @staticmethod
    def format_hms(seconds: int) -> str:
        seconds = max(0, int(seconds))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02}:{minutes:02}:{secs:02}"

    async def update_countdown(self, message: discord.Message, target_ts: int, user: discord.User):
        try:
            while True:
                now_ts = int(datetime.now(tz=timezone.utc).timestamp())
                remaining = target_ts - now_ts

                if remaining <= 0:
                    embed = message.embeds[0].copy()
                    embed.color = discord.Color.red()
                    embed.clear_fields()
                    embed.add_field(name="Status", value="⏰ Timer Complete!")
                    await message.edit(embed=embed)

                    # DM the owner
                    try:
                        await user.send(f"Your timer has completed: {message.jump_url}")
                        logger.info("[Timer] Sent DM to owner %s for timer completion", user)
                    except Exception:
                        logger.warning("[Timer] Could not DM owner %s", user)

                    break

                # Update embed with HH:MM:SS remaining
                embed = message.embeds[0].copy()
                ends_dt = datetime.fromtimestamp(target_ts, tz=timezone.utc)
                embed.clear_fields()
                embed.add_field(
                    name="Ends At (UTC)",
                    value=ends_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                )
                embed.add_field(name="Time Remaining", value=self.format_hms(remaining))
                await message.edit(embed=embed)

                # update every second for a smooth HH:MM:SS countdown
                await asyncio.sleep(1)
        except Exception as e:
            logger.exception("Error in countdown task: %s", e)

async def setup(bot):
    await bot.add_cog(TimerCog(bot))
