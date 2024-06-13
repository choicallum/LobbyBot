import discord
import logging
import pytz 
import asyncio

import datetime as dt

from datetime import datetime, date
from typing import Union, Dict, List
from timezone import getTimeZone
from settings import BUMP_LOBBY_CHANNEL_ID
from discord.ext import tasks

logger = logging.getLogger(__name__)

lobby_id = 0
ASAP_TIME = "ASAP"

class Player:
    def __init__(self, id: int, forceAdded: bool = False):
        self.id = id
        self.forceAdded = forceAdded
    
    def __eq__(self, other):
        if isinstance(other, Player):
            return self.id == other.id
        return self.id == other

class Lobby:
    def __init__(self, owner: Union[discord.Member, discord.User], time: Union[int, str], maxPlayers: int, game: str, spam: bool, started_at: int):
        global lobby_id
        self.id = lobby_id
        self.owner = owner
        self.time = time
        self.maxPlayers = maxPlayers
        self.game = game
        self.spam = spam
        self.started_at = started_at

        self.active = False
        self.completed = False
        self.view = None
        self.message = None
        self.channel = None
        self.players: list[Player] = list()
        self.fillers: list[Player] = list()
        self.players.append(Player(owner.id))
        lobby_id += 1

        if self.spam:
            self.update_message_no_interaction_task.start()
    
    @tasks.loop(minutes=1)
    async def update_message_no_interaction_task(self):
        if not self.message:
            return

        async for message in self.channel.history(limit=1):
            # Skip updating if the last message in the channel is also CallumBot
            if message.author.bot:
                return
            else:
                new_embed = self.create_embed()
                last_bot_message = await self.channel.fetch_message(self.message)
                await last_bot_message.delete()
                new_msg = await self.channel.send(embed=new_embed, view=self.view)
                self.message = new_msg.id

    async def add_player(self, interaction: discord.Interaction, player: discord.Member, forced: bool):
        if await self.is_lobby_done(interaction):
            return
        
        if player.id in self.players:
            await interaction.response.send_message(content="You're already playing in this lobby! 😡", ephemeral=True)
            return
        if len(self.players) < self.maxPlayers:
            if player.id in self.fillers: 
                self.fillers.remove(Player(player.id))
            self.players.append(Player(player.id, forced))
            await self.update_message(interaction)
        else:
            await interaction.response.send_message(content="The lobby is already full 😞", ephemeral=True)
        
    def create_embed(self) -> discord.Embed:
        time = f"ASAP (Started at <t:{self.started_at}:t>)" if self.time == ASAP_TIME else f"<t:{self.time}:t>"
        if self.active:
            color = discord.Color.red()
        else:
            color = discord.Color.blue()
        embed = discord.Embed (
            title = f"{self.owner.display_name}'s {self.game} Lobby - {time}",
            color=color
        )
        embed.add_field(name="Players", value = "\n".join([f"<@{player.id}> (force added)" if player.forceAdded else f"<@{player.id}>" for player in self.players]), inline=True)
        embed.add_field(name="Fillers", value = "\n".join([f"<@{filler.id}>" for filler in self.fillers]), inline=True)
        embed.set_footer(text=f"ID: {self.id} | Max players: {self.maxPlayers}")  
        return embed

    def in_lobby(self, user_id: int) -> bool:
        return any(player.id == user_id for player in self.players) or any(player.id == user_id for player in self.fillers)
    
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
        player_list = ", ".join([f"<@{player.id}>" for player in self.players])
        filler_list = ", ".join([f"<@{filler.id}>" for filler in self.fillers])
        parts = [f"ID: {self.id}",f"Owner: <@{self.owner.id}>", f"Game: {self.game}", f"Max Players: {self.maxPlayers}", f"Time: {self.time} (<t:{self.time}>)", f"Players: {player_list}", f"Fillers: {filler_list}"]
        return delimiter.join(parts)
    
    def log_button(self, interaction: discord.Interaction, name: str):
        logger.info(f"Lobby {self.id}: {interaction.user.name}({interaction.user.id}) pressed {name} button. Old state: {self.__str__(', ')}.")

# A list of all the active lobbies.
Lobbies: Dict[int, Lobby] = {}

async def show_lobbies(interaction: discord.Interaction):
    if len(Lobbies) == 0:
        await interaction.response.send_message("There are no currently active lobbies!", ephemeral=True)
        return
    
    timezone = await getTimeZone(interaction)
    if timezone == "":
        return
    
    options = []
    for index, lobby in Lobbies.items():
        if lobby.time != ASAP_TIME:
            utc_time = datetime.utcfromtimestamp(lobby.time)
            time_str = utc_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(timezone)).strftime("%I:%M %p")
        else:
            time_str = ASAP_TIME
        options.append(discord.SelectOption(label=f"ID: {lobby.id} - Owner: {lobby.owner.name} - {time_str}", value=index))
    
    select = discord.ui.Select(
        placeholder="Which lobby? 🤔",
        options=options
    )
    view = discord.ui.View(timeout=60)
    view.add_item(select)
    await interaction.response.send_message(view=view, ephemeral=True)
    async def on_select(interaction: discord.Interaction):
        await Lobbies[int(select.values[0])].update_message(interaction)

    select.callback = on_select

async def bump_lobby(interaction: discord.Interaction, user: discord.Member):
    if user.id not in Lobbies:
        await interaction.response.send_message(f"{user.name} did not have an active lobby 😔", ephemeral=True)
        return
    
    await Lobbies[user.id].update_message(interaction)

async def add_player_to_lobby(interaction: discord.Interaction, owner: discord.Member, addee: discord.Member, forced: bool):
    if owner.id not in Lobbies:
        await interaction.response.send_message(f"{owner.name} did not have an active lobby 😔", ephemeral=True)
        return
    
    await Lobbies[owner.id].add_player(interaction, addee, forced)
    
    
async def close_lobby(user_id: int, interaction: discord.Interaction):
    message = ""
    ephemeral = True
    if user_id not in Lobbies:
        message = "You did not have an active lobby. 😒"
        ephemeral = True
    else:
        message = "Lobby successfully closed. 🔒"
        ephemeral = False
        Lobbies[user_id].update_message_no_interaction_task.cancel()
        Lobbies[user_id].completed = True
        channel = Lobbies[user_id].channel
        oldmsg = await Lobbies[user_id].channel.fetch_message(Lobbies[user_id].message)
        await oldmsg.delete()
        del Lobbies[user_id]

    if interaction:
        await interaction.response.send_message(content=message, ephemeral=ephemeral)
    else:
        await channel.send(content=message)
    

## inactive lobby view
class LobbyView(discord.ui.View):
    def __init__(self, timeout: int, lobby: Lobby):
        super().__init__(timeout=timeout)
        self.lobby = lobby
    
    @discord.ui.button(label="I am a gamer", style=discord.ButtonStyle.primary)
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "play")
        await self.lobby.add_player(interaction, interaction.user, forced=False)
    
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
        self.lobby.fillers.append(Player(user))
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
    
    @discord.ui.button(label="Start Lobby", style=discord.ButtonStyle.green)
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
        
        if len(playerList) == self.lobby.maxPlayers or button.label == "Force Start":
            message = ["Your game is ready!\n"]
            for player in playerList:
                message.append(f"<@{player.id}>")
            # add fillers into players
            # if it's force starting, add all the players (even tho it might not fill the lobby)
            if button.label == "Force Start":
                needed_players = len(self.lobby.fillers)
            for i in range(0, needed_players):
                filler = self.lobby.fillers.pop()
                self.lobby.players.append(filler)
            self.lobby.active = True
            self.lobby.game = f"Active {self.lobby.game}"
            self.lobby.view = ActiveLobbyView(timeout=self.timeout, lobby=self.lobby)
            await self.lobby.channel.send(content=' '.join(message))
            await self.lobby.update_message(interaction)
        else:
            button.label = "Force Start"
            await self.lobby.update_message(interaction)
            await interaction.channel.send(content=f"<@{interaction.user.id}> There are not enough players to fill this lobby. Force Start anyways?")
    
    @discord.ui.button(label="Close lobby", style=discord.ButtonStyle.red)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "close")
        if await self.lobby.is_lobby_done(interaction):
            return
        
        if interaction.user.id != self.lobby.owner.id:
            await interaction.response.send_message(content="You are not the owner of this lobby!", ephemeral=True)
            return
        await close_lobby(self.lobby.owner.id, interaction)
        
class ActiveLobbyView(discord.ui.View):
    def __init__(self, timeout: int, lobby: Lobby):
        super().__init__(timeout=timeout)
        self.lobby = lobby
        self.strict_ids = []

    @discord.ui.button(label="I want to fill if a spot opens up", style=discord.ButtonStyle.primary)
    async def fill_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "fill")
        if await self.lobby.is_lobby_done(interaction):
            return
        
        user = interaction.user.id
        if user in self.lobby.fillers:
            await interaction.response.send_message(content="You're already filling in this lobby! 😡", ephemeral=True)
            return
        
        if user in self.lobby.players: 
            await interaction.response.send_message(content="HUH? you are already playing. silly goose.", ephemeral=True)
            return
        
        self.lobby.fillers.append(Player(user))
        await self.lobby.update_message(interaction)

    async def wait_filler(self, filler):
        await asyncio.sleep(300)
        if filler in self.strict_ids: # still in strict ids after 5 minutes
            self.strict_ids.remove(filler)
            message = [f"<@{filler}> declined their spot. Anyone is free to join."]
            for f in self.lobby.fillers:
                message.append(f"<@{f.id}>")
            await self.lobby.channel.send(content=' '.join(message))
        else:
            return

    @discord.ui.button(label="Drop out of lobby / No longer want to fill", style=discord.ButtonStyle.secondary)
    async def dropout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "dropout_active")
        if await self.lobby.is_lobby_done(interaction):
            return
        user = interaction.user.id
        if user in self.strict_ids:
            self.strict_ids.remove(user)
            message = [f"<@{filler.id}> declined their spot. Anyone is free to join."]
            for filler in self.lobby.fillers:
                message.append(f"<@{filler.id}>")
            await self.lobby.channel.send(content=' '.join(message))
            return
        if user in self.lobby.players:
            self.lobby.players.remove(user)
            if len(self.lobby.fillers) == 0:
                await self.lobby.update_message(interaction)
                await self.lobby.channel.send(content="There are no fillers! This lobby needs fillers! 🐀🐁")
            else:
                # ask the first filler, give them 5 minutes, then FFA.
                filler = self.lobby.fillers[0]
                await self.lobby.update_message(interaction)
                await self.lobby.channel.send(content=f"<@{filler.id}>, you are invited to join the lobby! Please click 'Fill In!' within 5 minutes. Press Drop Out to decline.")
                self.strict_ids.append(filler.id)
                await self.wait_filler(filler.id)
        elif user in self.lobby.fillers:
            self.lobby.fillers.remove(user)
            await self.lobby.update_message(interaction)
        else:
            await interaction.response.send_message(content="You weren't playing or filling in this lobby! 😡", ephemeral=True)
            return

    @discord.ui.button(label="Fill In!", style=discord.ButtonStyle.green)
    async def fillin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "fillin_active")
        if interaction.user.id in self.strict_ids:
            await self.lobby.add_player(interaction, interaction.user, forced=False)
            self.strict_ids.remove(interaction.user.id)
        elif len(self.lobby.players) + len(self.strict_ids) == self.lobby.maxPlayers:
            await interaction.response.send_message(content="You aren't a filler being waited for and/or there is no extra room. ☹", ephemeral=True)
        elif len(self.lobby.players) + len(self.strict_ids) < self.lobby.maxPlayers:
            await self.lobby.add_player(interaction, interaction.user, forced=False)
        else:
            await interaction.response.send_message(content="A filler wasn't needed yet! 😡", ephemeral=True)
        
    @discord.ui.button(label="End Lobby", style=discord.ButtonStyle.red)
    async def end_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.lobby.log_button(interaction, "end_active")
        if await self.lobby.is_lobby_done(interaction):
            return
        if interaction.user.id not in self.lobby.players:
            await interaction.response.send_message(content="You are not playing in this lobby!", ephemeral=True)
            return
        await close_lobby(self.lobby.owner.id, interaction)


async def close_lobby_auto(lobby: Lobby, timeout):
    await asyncio.sleep(timeout)
    print("running!")
    if lobby and not lobby.completed:
        await lobby.channel.send(content=f"{lobby.owner.display_name}'s lobby timing out...")
        await close_lobby(lobby.owner.id, None)   
        
async def makeLobby(interaction: discord.Interaction, time: str, lobby_size: int = 5, game: str = "Valorant"):
    if lobby_size < 0:
        await interaction.response.send_message("The lobby size must be greater than 0.", ephemeral=True)
        return
        
    owner = interaction.user
    timezone = await getTimeZone(interaction)
    if timezone == "":
        return

    #Try to parse the time input.
    if time.lower() == "now" or time.lower() =="asap":
        start_time = datetime.now()
        utc_time = ASAP_TIME
        started_at = int(start_time.timestamp())
    else:
        started_at = None
        try:
            if ':' in time:
                input_time = datetime.strptime(time, "%I:%M%p")
            else:
                input_time = datetime.strptime(time, "%I%p")
        except ValueError:
            logger.info(f"Parsing start time failed. Input: {time}")
            await interaction.response.send_message("Invalid time format. Please use `[hour]:[minutes][AM|PM]`, `[hour][AM|PM]`, or `asap/now`.", ephemeral=True)
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

    timeout = int(start_time.timestamp()) - int(datetime.now().timestamp()) + 21600 # 6 hours
    
    if owner.id in Lobbies:
        await interaction.response.send_message("You already have an active lobby! If this is a mistake, run /close.", ephemeral=True)
        return
    else:
        if interaction.channel_id == BUMP_LOBBY_CHANNEL_ID:
            spam = True
        else:
            spam = False
        
        lobby = Lobby(owner=owner, time=utc_time, maxPlayers=lobby_size, game=game, spam=spam, started_at=started_at)
        Lobbies[owner.id] = lobby

    view = LobbyView(timeout=timeout, lobby=lobby)
    logger.info(f"New LobbyView was created for the lobby: {view.lobby.__str__(', ')} which will timeout in {timeout} seconds, which is at {start_time + dt.timedelta(seconds=timeout)}")
    lobby.view = view

    await lobby.update_message(interaction)
    await close_lobby_auto(lobby, timeout)
