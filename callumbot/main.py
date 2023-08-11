# library imports
import settings
import discord
from discord.ext import commands
import logging 

# src imports
from lobby import close_lobby_by_uid, makeLobby
from timezone import setTimeZone

logger = logging.getLogger('discord')
logging.basicConfig(level=logging.NOTSET)

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

    @bot.hybrid_command()
    async def ping(ctx):
        """ Answers with Pong """
        await ctx.send("pong")
    
    @bot.tree.command(name="set", description="Set your time zone")
    async def set(interaction: discord.Interaction):
        select = discord.ui.Select(
            placeholder="Please set your time zone.",
            options=[
                discord.SelectOption(label="PST", emoji="🤢"),
                discord.SelectOption(label="MST", emoji="🏔"),
                discord.SelectOption(label="CST", emoji="🐛"),
                discord.SelectOption(label="EST", emoji="😍"),
                discord.SelectOption(label="Goose", emoji="🦢"),
                discord.SelectOption(label="Troll", emoji="🧌")
            ]
        )
        timezoneView = discord.ui.View(timeout=60)
        timezoneView.add_item(select)
        await interaction.response.send_message(view=timezoneView, ephemeral=True)
        async def on_select(interaction: discord.Interaction):
            setTimeZone(interaction.user.id, select.values[0])
            await interaction.response.send_message(content="Your timezone has been set successfully.", ephemeral=True)
 
        select.callback = on_select
    
    bot.tree.command(name="lobby", description="Starts a new lobby")(makeLobby)
    
    @bot.tree.command(name="flexnow", description="Starts a new flex lobby")
    async def flexnow(interaction: discord.Interaction, lobby_size: int = 5):
        await makeLobby(interaction, "now", lobby_size, "flex")

    @bot.tree.command(name="close", description="Closes an existing lobby")
    async def close(interaction: discord.Interaction):
        await close_lobby_by_uid(interaction.user.id, interaction, True, True)

    bot.run(settings.DISCORD_API_SECRET, root_logger=True)
    
if __name__ == "__main__":
    run()
