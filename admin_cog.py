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
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD'))))
    async def resync(self, interaction: Interaction):
        if interaction.user.id != AUTH_ID:
            await interaction.response.send_message('You are not authorized to run this command.', ephemeral=True)
            return

        # Respond immediately to avoid timeout
        await interaction.response.send_message('🔄 Starting command resync...', ephemeral=True)
        
        try:
            guild_id = os.getenv('GUILD')
            if guild_id:
                guild_obj = discord.Object(id=int(guild_id))
                logger.info('Clearing guild commands...')
                # clear_commands is synchronous; do not await it
                self.bot.tree.clear_commands(guild=guild_obj)
                
                logger.info('Syncing guild commands...')
                synced = await self.bot.tree.sync(guild=guild_obj)
                
                await interaction.edit_original_response(content=f'✅ Cleared and synced {len(synced)} commands for guild {guild_id}')
                logger.info('Resynced %d guild commands for %s by %s', len(synced), guild_id, interaction.user)
            else:
                logger.info('Clearing global commands...')
                # clear_commands is synchronous; do not await it
                self.bot.tree.clear_commands()
                
                logger.info('Syncing global commands...')
                synced = await self.bot.tree.sync()
                
                await interaction.edit_original_response(content=f'✅ Cleared and synced {len(synced)} global commands')
                logger.info('Resynced %d global commands by %s', len(synced), interaction.user)
                
        except Exception as e:
            logger.error('Resync failed: %s', e)
            try:
                await interaction.edit_original_response(content=f'❌ Resync failed: {str(e)[:100]}...')
            except Exception as edit_error:
                logger.error('Failed to edit resync response: %s', edit_error)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
