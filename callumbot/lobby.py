import discord
import logging
import pytz 
import traceback

import datetime as dt
from datetime import datetime, date

from timezone import getTimeZone
logger = logging.getLogger(__name__)

Lobbies = {}
lobby_id = 0
ASAP_TIME = -1

class Lobby:
    def __init__(self, owner: int, time: int, maxPlayers: int, game: str):
        global lobby_id
        self.id = lobby_id
        self.owner = owner
        self.time = time
        self.maxPlayers = maxPlayers
        self.game = game

        self.completed = False
        self.view = None
        self.message = None
        self.channel = None
        self.players = []
        self.fillers = []
        self.players.append(owner)
        lobby_id += 1

    def create_embed(self) -> discord.Embed:
        description = f"This is a {self.game} lobby starting"
        if self.time == ASAP_TIME:
            description += " ASAP"
        else: 
            description += f" at <t:{self.time}:t>"

        embed = discord.Embed(
            description=description,
            color=discord.Color.blue()
        )
        embed.add_field(name="Players", value = "\n".join([f"<@{player}>" for player in self.players]), inline=True)
        embed.add_field(name="Fillers", value = "\n".join([f"<@{filler}>" for filler in self.fillers]), inline=True)
        embed.set_footer(text=f"ID: {self.id} | Max players: {self.maxPlayers}")  
        return embed

    def in_lobby(self, user_id: int) -> bool:
        return user_id in self.players or user_id in self.fillers
    
    async def update_message(self, interaction: discord.Interaction):
        """ completes the interaction by sending a new message of the embed """
        new_embed = self.create_embed()
        if self.message:
            oldmsg = await self.channel.fetch_message(self.message)
            await oldmsg.delete()
        await interaction.response.send_message(embed=new_embed, view=self.view)
        interMsg = await interaction.original_response() # expires in 15 minutes
        self.message = interMsg.id
        self.channel = interaction.channel

    async def is_lobby_done(self, interaction: discord.Interaction) -> bool:
        if self.completed:
            await interaction.response.send_message("This lobby is already completed! 😿", ephemeral=True)
        
        return self.completed
    
    def __str__(self, delimiter="\n"):
        player_list = ", ".join([f"<@{player}>" for player in self.players])
        filler_list = ", ".join([f"<@{filler}>" for filler in self.fillers])
        parts = [f"ID: {self.id}",f"Owner: <@{self.owner}>", f"Game: {self.game}", f"Max Players: {self.maxPlayers}", f"Time: {self.time} (<t:{self.time}>)", f"Players: {player_list}", f"Fillers: {filler_list}"]
        return delimiter.join(parts)
    
    def log_button(self, interaction: discord.Interaction, name: str):
        logger.info(f"Lobby {self.id}: {interaction.user.name}({interaction.user.id}) pressed {name} button. Old state: {self.__str__(', ')}.")

async def show_all_lobbies(interaction: discord.Interaction):
    if len(Lobbies) == 0:
        await interaction.response.send_message("There are no currently active lobbies!")
        return
    
    embed = discord.Embed(
        title= f"All Active Lobbies", 
        color=discord.Color.blue())
    embed.add_field(name="Lobbies", value = "\n---\n".join([f"{lobby}" for lobby in Lobbies.values()]), inline=True)
    await interaction.response.send_message(embed=embed)


async def close_lobby_by_uid(user_id: int, interaction: discord.Interaction, sendMessage: bool, delete: bool):
    message = ""
    ephemeral = True
    if user_id not in Lobbies:
        message = "You did not have an active lobby. 😒"
        ephemeral = True
    else:
        stack_trace = traceback.format_stack()
        for line in stack_trace:
            logger.info(line.strip())
    
        message = "Lobby successfully closed. 🔒"
        ephemeral = False
        Lobbies[user_id].completed = True
        if delete:
            oldmsg = await Lobbies[user_id].channel.fetch_message(Lobbies[user_id].message)
            await oldmsg.delete()
        del Lobbies[user_id]

    if sendMessage:
        await interaction.response.send_message(content=message, ephemeral=ephemeral)

class LobbyView(discord.ui.View):
    def __init__(self, timeout: int, lobby: Lobby):
        super().__init__(timeout=timeout)
        self.lobby = lobby

    @discord.ui.button(label="I am a gamer", style=discord.ButtonStyle.primary)
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "play")
        if await self.lobby.is_lobby_done(interaction):
            return
        
        user = interaction.user.id
        if user in self.lobby.players:
            await interaction.response.send_message(content="You're already playing in this lobby! 😡", ephemeral=True)
            return
        if len(self.lobby.players) < self.lobby.maxPlayers:
            if user in self.lobby.fillers: 
                self.lobby.fillers.remove(user)
            self.lobby.players.append(user)
            await self.lobby.update_message(interaction)
        else:
            await interaction.response.send_message(content="The lobby is already full 😞", ephemeral=True)
    
    @discord.ui.button(label="I will fill", style=discord.ButtonStyle.secondary)
    async def fill_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "fill")
        if await self.lobby.is_lobby_done(interaction):
            return
        
        user = interaction.user.id
        if user in self.lobby.fillers:
            await interaction.response.send_message(content="You're already filling in this lobby! 😡", ephemeral=True)
            return
        
        if user in self.lobby.players: 
            self.lobby.players.remove(user)
        self.lobby.fillers.append(user)
        await self.lobby.update_message(interaction)

    @discord.ui.button(label="I no longer want to play", style=discord.ButtonStyle.red)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "leave")
        if await self.lobby.is_lobby_done(interaction):
            return
        user = interaction.user.id
        if user in self.lobby.players:
            self.lobby.players.remove(user)
        elif user in self.lobby.fillers:
            self.lobby.fillers.remove(user)
        else:
            await interaction.response.send_message(content="You weren't in this lobby! 😡", ephemeral=True)
            return
        await self.lobby.update_message(interaction)
    
    @discord.ui.button(label="Start lobby", style=discord.ButtonStyle.green)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "start")
        if await self.lobby.is_lobby_done(interaction):
            return
        
        if interaction.user.id not in self.lobby.players and interaction.user.id not in self.lobby.fillers:
            await interaction.response.send_message(content="You aren't in this lobby! 😡", ephemeral=True)
            return
        
        playerList = self.lobby.players[:self.lobby.maxPlayers]
        needed_players = self.lobby.maxPlayers - len(self.lobby.players)
        if needed_players > 0:
            playerList.extend(self.lobby.fillers[:needed_players])
        
        if len(playerList) == self.lobby.maxPlayers:
            message = ["Your game is ready!\n"]
            for player in playerList:
                message.append(f"<@{player}>")
            await close_lobby_by_uid(self.lobby.owner, interaction, False, False)
            await interaction.response.send_message(content=''.join(message))
        else: 
            await interaction.response.send_message(content="There are not enough players to start this lobby.", ephemeral=True)
        
    @discord.ui.button(label="Close lobby", style=discord.ButtonStyle.red)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "close")
        if await self.lobby.is_lobby_done(interaction):
            return
        
        if interaction.user.id != self.lobby.owner:
            await interaction.response.send_message(content="You are not the owner of this lobby!", ephemeral=True)
            return
        await close_lobby_by_uid(self.lobby.owner, interaction, True, True)

async def makeLobby(interaction: discord.Interaction, time: str, lobby_size: int = 5, game: str = "Valorant"):
    if lobby_size < 0:
        await interaction.response.send_message("The lobby size must be greater than 0.", ephemeral=True)
        return
        
    owner = interaction.user.id
    timezone = getTimeZone(owner)
    if timezone == "":
        await interaction.response.send_message("Your timezone has not been set yet. Please use /set to set your timezone.", ephemeral=True)
        return

    #Try to parse the time input.
    if time.lower() == "now" or time.lower() =="asap":
        start_time = datetime.now()
        utc_time = ASAP_TIME
    else:
        try:
            if ':' in time:
                input_time = datetime.strptime(time, "%I:%M%p")
            else:
                input_time = datetime.strptime(time, "%I%p")
        except ValueError:
            logger.info(f"Parsing start time failed. Input: {time}")
            await interaction.response.send_message("Invalid time format. Please use `[hour]:[minutes][AM|PM]`, `[hour][AM|PM]`, or `now`.", ephemeral=True)
            return
        today = date.today()
        start_time = input_time.replace(year=today.year, month=today.month, day=today.day)
        localized_time = pytz.timezone(timezone).localize(start_time)
        utc_time = int(localized_time.timestamp())

    timeUntilLobby = int(start_time.timestamp()) - int(datetime.now().timestamp())
    # if the user meant tomorrow (i.e. 1am tmrw when it's 11pm today, then move it by a day)
    if timeUntilLobby < 0:
        utc_time = utc_time + 86400 #86400 is 1 day in seconds.
        start_time += dt.timedelta(days=1)

    timeout = int(start_time.timestamp()) - int(datetime.now().timestamp()) + 43200 # 12 hours
    
    if owner in Lobbies:
        await interaction.response.send_message("You already have an active lobby! If this is a mistake, run /close.", ephemeral=True)
        return
    else:
        lobby = Lobby(owner=owner, time=utc_time, maxPlayers=lobby_size, game=game)
        Lobbies[owner] = lobby

    view = LobbyView(timeout=timeout, lobby=lobby)
    logger.info(f"New LobbyView was created for the lobby: {view.lobby.__str__(', ')} which will timeout in {timeout} seconds, which is at {start_time + dt.timedelta(seconds=timeout)}")
    lobby.view = view

    await lobby.update_message(interaction)
