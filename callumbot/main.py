# library imports
import discord
import logging

from discord.ext import commands

# src imports
from lobby import close_lobby_by_uid, makeLobby, show_all_lobbies
from timezone import setTimeZone
from settings import DISCORD_API_SECRET

logger = logging.getLogger(__name__)

def log_cmd_start(interaction: discord.Interaction, name: str):
    logger.info(f"{interaction.user.name}({interaction.user.id}) started {name} command")

def run():
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        logger.info(f"User: {bot.user} (ID: {bot.user.id})")

        for guild in bot.guilds:
            logger.info(f"Guild: {guild}")

        await bot.tree.sync()
        logger.info("synced!")
        logger.info("CallumBot is online!")

    @bot.tree.command(name="ping", description="Pong!")
    async def ping(interaction: discord.Interaction):
        log_cmd_start(interaction, "ping")
        await interaction.response.send_message("Pong!")
    
    @bot.tree.command(name="set", description="Set your time zone")
    async def set(interaction: discord.Interaction):
        log_cmd_start(interaction, "set")
        await setTimeZone(interaction)

    @bot.tree.command(name="lobby", description="Starts a new lobby")
    async def lobby(interaction: discord.Interaction, time: str, lobby_size: int = 5, game: str = "Valorant"):
        """
        :param time: eg. 4PM, 4:20PM or asap/now. What time you want the lobby to start.
        :param lobby_size: Max number of players in the lobby.
        :param game: The game being played.
        """
        log_cmd_start(interaction, "lobby")
        await makeLobby(interaction, time, lobby_size, game)
    
    @bot.tree.command(name="flexnow", description="Starts a new flex lobby")
    async def flexnow(interaction: discord.Interaction, lobby_size: int = 5):
        """
        :param lobby_size: Max number of players in the lobby.
        """
        log_cmd_start(interaction, "flexnow")
        await makeLobby(interaction, "now", lobby_size, "flex")

    @bot.tree.command(name="close", description="Closes an existing lobby")
    async def close(interaction: discord.Interaction):
        log_cmd_start(interaction, "close")
        await close_lobby_by_uid(interaction.user.id, interaction, True, True)
        
    @bot.tree.command(name="showall", description="shows all active lobbies")
    async def showall(interaction: discord.Interaction):
        log_cmd_start(interaction, "showall")
        await show_all_lobbies(interaction)
    
    bot.run(DISCORD_API_SECRET, root_logger=True)
    
if __name__ == "__main__":
    run()
