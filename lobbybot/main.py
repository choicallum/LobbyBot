# library imports
import discord
import logging
import re

from discord.ext import commands

from .timezones import set_time_zone
from lobbybot.settings import DISCORD_API_SECRET, VERSION
from .wordle.wordle_grader import grade_wordle
from .lobby import LobbyController
from .images import get_img_store
logger = logging.getLogger(__name__)

def log_cmd_start(interaction: discord.Interaction, name: str):
    logger.info(f"{interaction.user.name}({interaction.user.id}) started {name} command")

async def bot_can_send(interaction: discord.Interaction) -> bool:
    perms = interaction.channel.permissions_for(interaction.guild.me)
    if not perms.send_messages or not perms.view_channel or not perms.manage_messages:
        await interaction.response.send_message(
            "I don’t have permission to talk in this channel.", ephemeral=True
        )
        return False
    return True

def run():

    lobby_controller = LobbyController()
    image_store = get_img_store()
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
        logger.info("Bot is online!")

    # bump messages in gundan_lobby
    @bot.event
    async def on_message(message: discord.Message):
        if message.author.bot:
            return
        
        # reprint twitter links
        message_content = message.content
        
        pattern = re.compile(r'https?://(twitter\.com|x\.com)/(.+)/status/(\d+)', re.IGNORECASE)

        # Replace 'twitter.com' or 'x.com' with 'fxtwitter.com'
        message_content = re.sub(pattern, r'https://fxtwitter.com/\2/status/\3', message_content)

        if pattern.search(message.content):
            await message.channel.send(f"{message.author.display_name}: {message_content}", reference=message.reference)
            await message.delete()

    @bot.tree.command(name="ping", description="Pong!")
    async def ping(interaction: discord.Interaction):
        log_cmd_start(interaction, "ping")
        await interaction.response.send_message("Pong!")
    
    @bot.tree.command(name="version", description="What version is CallumBot running?")
    async def version(interaction: discord.Interaction):
        log_cmd_start(interaction, "version")
        await interaction.response.send_message(VERSION)
    
    #TODO: implement help
    #@bot.tree.command(name="help", description="Lists and describes LobbyBot's commands")
    #async def ping(interaction: discord.Interaction):
    #    log_cmd_start(interaction, "help")
    #    await interaction.response.send_message("Pong!")

    @bot.tree.command(name="set", description="Set your time zone")
    async def set(interaction: discord.Interaction):
        log_cmd_start(interaction, "set")
        await set_time_zone(interaction)

    @bot.tree.command(name="lobby", description="Starts a new lobby")
    async def lobby(interaction: discord.Interaction, time: str, lobby_size: int = 5, game: str = "Valorant"):
        """
        :param time: eg. 4PM, 4:20PM or asap/now. What time you want the lobby to start.
        :param lobby_size: Max number of players in the lobby.
        :param game: The game being played.
        """
        if not await bot_can_send(interaction):
            return
        log_cmd_start(interaction, "lobby")
        await lobby_controller.create_lobby(interaction, time, lobby_size, game)
    
    @bot.tree.command(name="flexnow", description="Starts a new flex lobby")
    async def flexnow(interaction: discord.Interaction, lobby_size: int = 5):
        """
        :param lobby_size: Max number of players in the lobby.
        """
        if not await bot_can_send(interaction):
            return
        log_cmd_start(interaction, "flexnow")
        await lobby_controller.create_lobby(interaction, "now", lobby_size, "flex")

    @bot.tree.command(name="close", description="Closes an existing lobby")
    async def close(interaction: discord.Interaction):
        if not await bot_can_send(interaction):
            return
        log_cmd_start(interaction, "close")
        await lobby_controller.handle_close_lobby(interaction)
        
    # @bot.tree.command(name="show", description="Gives you a list of all the lobbies and lets you bump one of them")
    # async def show(interaction: discord.Interaction):
    #     if not await bot_can_send(interaction):
    #         return
    #     log_cmd_start(interaction, "show")
    #     await show_lobbies(interaction)

    # @bot.tree.command(name="bump", description="Bump your own (or someone else's) lobby.")
    # async def bump(interaction: discord.Interaction, owner: discord.Member=None):
    #     if not await bot_can_send(interaction):
    #         return
    #     log_cmd_start(interaction, "bump")
    #     if owner == None:
    #         owner = interaction.user

    #     await bump_lobby(interaction, owner)
    
    @bot.tree.command(name="forceadd", description="Force adds a user to your owned lobby.")
    async def add(interaction: discord.Interaction, player: discord.Member):
        if not await bot_can_send(interaction):
            return
        log_cmd_start(interaction, "forceadd")
        await lobby_controller.add_player_to_lobby(interaction, interaction.user, player, forced=True)

    @bot.tree.command(name="gradewordle", description="Grades how well you played Wordle (Hard Mode only)")
    async def gradewordle(interaction: discord.Interaction, guesses: str, answer: str = "", try_all_words: bool = False):
        """
        :param guesses: Comma separated guesses. (ex: meows, adieu, blend, where blend was today's wordle)
        :param answer: The Wordle's answer. Use this if you failed today's wordle.
        :param try_all_words: Whether or not to include more obscure words in the guess pool. May lead to extended processing times.
        """
        log_cmd_start(interaction, "gradewordle")
        await grade_wordle(interaction, guesses, answer, try_all_words)
    
    @bot.tree.command(name="add_img", description="Add an image to the Lobby image pool")
    async def add_lobby_image(interaction: discord.Interaction, url: str):
        """
        :param url: URL to an image or gif. Must be a direct link to the image (i.e. ends in .png, .jpg, .gif, etc.)
        """
        await interaction.response.defer(thinking=True)
        success, err = image_store.add_img(url, f"{interaction.user.name} ({interaction.user.id})")
        if success:
            await interaction.followup.send("✅ Image added successfully!")
        else:
            await interaction.followup.send(f"❌ Failed to add image! {err}", ephemeral=True)

    @bot.tree.command(name="remove_img", description="Remove an image to the Lobby image pool")
    async def remove_lobby_image(interaction: discord.Interaction, url: str):
        """
        :param url: URL to an image or gif that has already been added to the pool.
        """
        await interaction.response.defer(thinking=True)
        success = image_store.remove_img(url)
        if success:
            await interaction.followup.send("✅ Image removed successfully!")
        else:
            await interaction.followup.send(f"❌ Failed to remove image!", ephemeral=True)

    bot.run(DISCORD_API_SECRET, root_logger=True)

if __name__ == "__main__":
    run()
