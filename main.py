import settings
import discord
import pytz 
import datetime as dt

from pathlib import Path
from discord.ext import commands
from discord.ui import Select
from datetime import datetime, date

logger = settings.logging.getLogger("bot")

class Lobby:
    def __init__(self, owner: int, time: int, maxPlayers: int, interaction: discord.Interaction):
        self.owner = owner
        self.players = []
        self.fillers = []
        self.time = time
        self.maxPlayers = maxPlayers
        self.interaction: discord.Interaction = interaction
        self.message = None

        self.players.append(owner)

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
                              description= f"This is a Valorant Lobby aiming to start at <t:{self.time}:t>", 
                              color=discord.Color.blurple())
        embed.add_field(name="Players", value = "\n".join([f"<@{player}>" for player in self.players]), inline=True)
        embed.add_field(name="Fillers", value = "\n".join([f"<@{filler}>" for filler in self.fillers]), inline=True)
        embed.set_footer(text=f"Max players: {self.maxPlayers}")  
        return embed

    def in_lobby(self, user_id: int) -> bool:
        return user_id in self.players or user_id in self.fillers
    
    async def update_message(self):
        if self.message:
            new_embed = self.create_embed()
            await self.message.edit(embed=new_embed)
    
Lobbies = {}
async def close_lobby(user_id: int, interaction: discord.Interaction):
    if user_id not in Lobbies:
        await interaction.response.send_message(content="You did not have an active lobby.", ephemeral=True)
    else:
        del Lobbies[user_id]
        await interaction.response.send_message(content="Lobby successfully closed.", ephemeral=False)

class LobbyView(discord.ui.View):
    def __init__(self, timeout: int, lobby: Lobby):
        super().__init__(timeout=timeout)
        self.lobby = lobby

    @discord.ui.button(label="I am a gamer", style=discord.ButtonStyle.primary, custom_id="play_button")
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.lobby.in_lobby(interaction.user.id):
            await interaction.response.send_message(content="You're already in this lobby! 😡", ephemeral=True)
            return

        if len(self.lobby.players) < self.lobby.maxPlayers:
            self.lobby.players.append(interaction.user.id)
            await interaction.response.send_message(content="You are now a gamer 🥺", ephemeral=True)
        else:
            await interaction.response.send_message(content="The lobby is already full 😞", ephemeral=True)
        await self.lobby.update_message()
    
    @discord.ui.button(label="I will fill", style=discord.ButtonStyle.secondary, custom_id="fill_button")
    async def fill_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.lobby.in_lobby(interaction.user.id):
            await interaction.response.send_message(content="You're already in this lobby! 😡", ephemeral=True)
            return

        self.lobby.fillers.append(interaction.user.id)
        await interaction.response.send_message(content="You are now a filler 🥺", ephemeral=True)
        await self.lobby.update_message()

    @discord.ui.button(label="I no longer want to play", style=discord.ButtonStyle.red, custom_id="leave_button")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user.id
        if user in self.lobby.players:
            self.lobby.players.remove(user)
        elif user in self.lobby.fillers:
            self.lobby.fillers.remove(user)
        else:
            await interaction.response.send_message(content="You weren't in this lobby! 😡", ephemeral=True)
            return
        await interaction.response.send_message(content="You were successfully removed from the lobby!", ephemeral=True)
        await self.lobby.update_message()
    
    #@discord.ui.button(label="Start lobby [does not work yet]", style=discord.ButtonStyle.green, custom_id="start_button")
    #async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #    if interaction.user.id != self.lobby.owner:
    #        await interaction.response.send_message(content="You are not the owner of this lobby!", ephemeral=True)
    #        return
        
    @discord.ui.button(label="Close lobby", style=discord.ButtonStyle.red, custom_id="close_button")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.lobby.owner:
            await interaction.response.send_message(content="You are not the owner of this lobby!", ephemeral=True)
            return
        await close_lobby(self.lobby.owner, interaction)

        
        
        

def run():
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        logger.info(f"User: {bot.user} (ID: {bot.user.id})")
        logger.info(f"id: {bot.guilds[0].id}")

        bot.tree.copy_global_to(guild=settings.GUILDS_ID)
        await bot.tree.sync(guild=settings.GUILDS_ID)

    @bot.hybrid_command()
    async def ping(ctx):
        """ Answers with Pong """
        await ctx.send("pong")
    
    @bot.tree.command(name="set", description="Set your time zone")
    async def set(interaction: discord.Interaction):
        select = Select(
            placeholder="Please set your time zone.",
            options=[
                discord.SelectOption(label="PST", emoji="🤢"),
                discord.SelectOption(label="MST", emoji="🏔"),
                discord.SelectOption(label="CST", emoji="🐛"),
                discord.SelectOption(label="EST", emoji="😍")
            ]
        )
        timezoneView = discord.ui.View(timeout=60)
        timezoneView.add_item(select)
        await interaction.response.send_message(view=timezoneView, ephemeral=True)
        async def on_select(interaction: discord.Interaction):
            setTimeZone(interaction.user.id, select.values[0])
            await interaction.response.send_message(content="Your timezone has been set successfully.", ephemeral=True)
 
        select.callback = on_select

    @bot.tree.command(name="lobby", description="Starts a new lobby")
    async def lobby(interaction: discord.Interaction, time: str, lobby_size: int = 5):
        """
        Starts a new lobby
        
        :param time: eg. 4:20PM or "now". What time you want the lobby to start.
        :param lobby_size: Max number of players in the lobby.
        """

        owner = interaction.user.id
        timezone = getTimeZone(owner)
        if timezone == "":
            await interaction.response.send_message("Your timezone has not been set yet. Please use /set to set your timezone.", ephemeral=True)
            return

            
        #Try to parse the time input.
        try:
            if time.lower() == "now":
                start_time = datetime.now() + dt.timedelta(minutes=5)
                utc_time = int(start_time.timestamp())
            else:
                today = date.today()
                input_time = datetime.strptime(time, "%I:%M%p")
                start_time = input_time.replace(year=today.year, month=today.month, day=today.day)
                localized_time = pytz.timezone(timezone).localize(start_time)
                utc_time = int(localized_time.timestamp())
    
            timeUntilLobby = int(start_time.timestamp()) - int(datetime.now().timestamp())
            # if the user meant tomorrow (i.e. 1am tmrw when it's 11pm today, then move it by a day)
            if timeUntilLobby < 0:
                utc_time = utc_time + 86400 #86400 is 1 day in seconds.
                start_time += dt.timedelta(days=1)

            timeout = int(start_time.timestamp()) - int(datetime.now().timestamp()) + 3600
     
        except ValueError:
            await interaction.response.send_message("Invalid time format. Please use `[hour]:[minutes][AM|PM]` format or `now`.", ephemeral=True)
            return
        
        if owner in Lobbies:
            await interaction.response.send_message("You already have an active lobby! If this is a mistake, run /close.", ephemeral=True)
            return
        else:
            lobby = Lobby(owner=owner, time=utc_time, maxPlayers=lobby_size, interaction=interaction)
            Lobbies[owner] = lobby

        view = LobbyView(timeout=timeout, lobby=lobby)

        await interaction.response.send_message(embed=lobby.create_embed(), view=view)
        message = await interaction.original_response()
        lobby.message = message
    
    @bot.tree.command(name="close", description="Closes an existing lobby")
    async def close(interaction: discord.Interaction):
        await close_lobby(interaction.user.id, interaction)
    
    bot.run(settings.DISCORD_API_SECRET, root_logger=True)

def getTimeZone(userId: str) -> str:
    user_file = Path(f'users/{userId}.txt')
    if not user_file.exists():
        return ''    
    with user_file.open() as f:
        return f.read()

def setTimeZone(userId: str, timezone: str):
    verboseTimeZone = {
        "PST": "US/Pacific",
        "MST": "US/Mountain",
        "CST": "US/Central",
        "EST": "US/Eastern"
    }[timezone]

    user_file = Path(f'users/{userId}.txt')
    with user_file.open("w") as f:
        f.write(verboseTimeZone)
    
if __name__ == "__main__":
    run()
