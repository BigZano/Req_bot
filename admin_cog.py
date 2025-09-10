from discord import app_commands, Interaction
from discord.ext import commands
import discord
import os
import logging

logger = logging.getLogger('cogs')

AUTH_ID = 279763886134132736


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='resync', description='Clear and resync application commands (owner only)')
    async def resync(self, interaction: Interaction):
        if interaction.user.id != AUTH_ID:
            await interaction.response.send_message('You are not authorized to run this command.', ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            guild_id = os.getenv('GUILD')
            if guild_id:
                guild_obj = discord.Object(id=int(guild_id))
                # clear_commands is synchronous; do not await it
                self.bot.tree.clear_commands(guild=guild_obj)
                await self.bot.tree.sync(guild=guild_obj)
                await interaction.followup.send(f'Cleared and synced commands for guild {guild_id}')
                logger.info('Resynced guild commands for %s by %s', guild_id, interaction.user)
            else:
                # clear_commands is synchronous; do not await it
                self.bot.tree.clear_commands()
                await self.bot.tree.sync()
                await interaction.followup.send('Cleared and synced global commands')
                logger.info('Resynced global commands by %s', interaction.user)
        except Exception as e:
            logger.error('Resync failed: %s', e)
            try:
                await interaction.followup.send(f'Resync failed: {e}')
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
