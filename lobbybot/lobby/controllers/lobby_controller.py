import discord
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional, List
from lobbybot.lobby.models import LobbyManager, Lobby, LobbyAddResult, LobbyRemoveResult, LobbyState, ReadyResult, Player
from lobbybot.lobby.views import (
    WaitingLobbyView, 
    ActiveLobbyView,
    ForceStartView,
    LobbySelectView,
    CloseConfirmationView,
    ReadyCheckLobbyView,
    make_lobby_notif_embed,
    make_lobby_invite_embed
)
from lobbybot.timezones import get_time_zone, parse_time_input, ASAP_TIME
from lobbybot.settings import BUMP_LOBBY_CHANNEL_ID
import logging
logger = logging.getLogger(__name__)


class LobbyController:
    """Main controller for handling lobby operations"""
    
    def __init__(self):
        self.lobby_manager = LobbyManager() 
        self.lobby_to_view: dict[int, discord.ui.View] = {} # lobby id -> view
        self.lobby_to_msg: dict[int, discord.Message] = {} # lobby id -> message NOTE: you must fetch the message from an interaction response so the webhook doesn't expire
        self.spam_tasks = {}
    
    async def create_lobby(self, interaction: discord.Interaction, time: str, 
                          lobby_size: int = 5, game: str = "Valorant"):
        """Create a new lobby"""
        if lobby_size < 1:
            await interaction.response.send_message("The lobby size must be greater than 0.", ephemeral=True)
            return
        
        # check timezone data
        owner = interaction.user
        timezone = await get_time_zone(interaction.user.id)
        if timezone == "":
            await interaction.response.send_message("Your timezone is not set yet! Run /set to register your timezone.", ephemeral=True)
            return
        
        # check if user already has a lobby
        if self.lobby_manager.get_lobby_by_owner(owner.id):
            await interaction.response.send_message("You already have an active lobby! If this is a mistake, run /close.", ephemeral=True)
            return
        
        # parse time input
        parsed_time = await parse_time_input(interaction, time, timezone)
        if not parsed_time:
            return  # error message already sent in parse_time_input
        
        lobby = self.lobby_manager.create_lobby(
            owner=owner,
            time=parsed_time,
            max_players=lobby_size,
            game=game
        )
        
        # automatically close lobby after 6 hours
        if parsed_time == ASAP_TIME:
            timeout = 21600  # 6 hours
        else:
            timeout = parsed_time - int(datetime.now().timestamp()) + 10800 # 3 hours for listed time lobbies
        
        # create view and setup lobby
        view = WaitingLobbyView(timeout=timeout, lobby=lobby, controller=self)
        self.lobby_to_view[lobby.id] = view
        
        # setup spam updates if in bump channel
        if interaction.channel_id == BUMP_LOBBY_CHANNEL_ID:
            self._setup_spam_updates(lobby, interaction.channel)
        
        # send initial message

        await self._update_lobby_message(lobby=lobby, view=view, interaction=interaction)
        
        # setup auto-close
        asyncio.create_task(self._auto_close_lobby(lobby, timeout, LobbyState.WAITING))
    
    async def handle_join_lobby(self, interaction: discord.Interaction, lobby: Lobby, 
                               user: discord.Member, is_filler: bool = False):
        """Handle user joining lobby as player or filler"""
        if lobby.is_completed():
            await interaction.response.send_message("This lobby is already completed! 🙊", ephemeral=True)
            return
        
        result = None
        if is_filler:
            result = lobby.add_filler(user, forced=False)
        else:
            result = lobby.add_player(user, forced=False)

        if result == LobbyAddResult.SUCCESS:
            await self._update_lobby_message(lobby=lobby, interaction=interaction)
        else:
            await self._handle_add_result(interaction, result, is_filler)
    
    async def handle_leave_lobby(self, interaction: discord.Interaction, lobby: Lobby, user: discord.Member):
        """Handle user leaving lobby"""
        if lobby.is_completed():
            await interaction.response.send_message("This lobby is already completed! 🙊", ephemeral=True)
            return
        
        await self._handle_participant_dropout(interaction, lobby, user)
    
    # ---------------------
    # Ready Check
    # ---------------------
    async def handle_start_ready_check(self ,interaction: discord.Interaction, lobby: Lobby):
        """ Handle starting ready check from a waiting lobby state """
        if lobby.is_completed():
            await interaction.response.send_message("This lobby is already completed! 🙊", ephemeral=True)
            return True
        
        if not lobby.in_lobby(interaction.user.id):
            await interaction.response.send_message("You can't start ready check for this lobby, you're not playing in it! 😡", ephemeral=True)
            return False

        lobby.start_ready_check()
        ready_check_view = ReadyCheckLobbyView(300, lobby, self, int((datetime.now(timezone.utc)).timestamp()) + 300)
        self.lobby_to_view[lobby.id] = ready_check_view
        await self._update_lobby_message(lobby=lobby, view=ready_check_view, interaction=interaction)

        asyncio.create_task(self._ready_check_timeout(lobby, 300))

        end_time = int((datetime.now(timezone.utc)).timestamp()) + 300
        for player in lobby.get_players:
            dm_embed = make_lobby_notif_embed(lobby, f"'s ready check has started!\nThe deadline to respond is <t:{end_time}:R>", interaction.guild_id, interaction.channel_id)
        
            try:
                user = interaction.client.get_user(player.id) or await interaction.client.fetch_user(player.id)
                await user.send(embed=dm_embed)
            except Exception as e:
                    logger.exception(f"Unexpected error while DMing user {player.id} -- {e}")
    
    async def _ready_check_timeout(self, lobby: Lobby, timeout: int):
        await asyncio.sleep(timeout)
        
        if lobby.state != LobbyState.READY_CHECK or lobby.is_completed():
            return
        
        if lobby.all_ready(True):
            lobby.start_from_ready_check()
            logger.info(f"Starting {lobby.id} due to successful ready check timeout.")
            await self.lobby_to_msg[lobby.id].channel.send("Ready Check timing out...\nAny pending or declined players are being replaced with ready fillers.")
            await self._handle_after_starting_lobby(lobby)
        else:
            logger.info(f"Returning {lobby.id} to waiting due to unsuccessful ready check timeout.")
            await self._end_ready_check(None, lobby)
            await self.lobby_to_msg[lobby.id].channel.send("Ready Check timing out...\nNot enough players were ready! Lobby is returning to waiting for more players.")

    async def handle_ready(self, interaction: discord.Interaction, lobby: Lobby):
        res = lobby.ready_up(interaction.user)

        if res == ReadyResult.NOT_IN_LOBBY:
            await interaction.response.send_message("No one asked if you're ready! 🤣", ephemeral=True)
        elif res == ReadyResult.ALREADY_READY:
            await interaction.response.send_message("You're already readied up! 🦐", ephemeral=True)
        elif res == ReadyResult.SUCCESS_FILLER or res == ReadyResult.SUCCESS_PLAYER:
            if lobby.all_ready():
                lobby.start_from_ready_check()
                await self._handle_after_starting_lobby(lobby, interaction)
            else:
                await self._update_lobby_message(lobby=lobby, interaction=interaction)
                await interaction.followup.send("You've successfully readied up!", ephemeral=True)

    async def _end_ready_check(self, interaction: discord.Interaction, lobby: Lobby):
        res = lobby.end_ready_check()
        if res == LobbyRemoveResult.LOBBY_EMPTY:
            await interaction.channel.send(f"{lobby.owner.name}'s lobby is closing as there are no players or fillers ready to play.")
            await self._close_lobby_internal(lobby.owner.id, interaction)
            return
        
        if lobby.time == ASAP_TIME:
            timeout = 21600  # 6 hours
        else:
            timeout = lobby.time - int(datetime.now().timestamp()) + 10800 # 3 hours for listed time lobbies
        waiting_view = WaitingLobbyView(timeout=timeout, lobby=lobby, controller=self)
        self.lobby_to_view[lobby.id] = waiting_view
        await self._update_lobby_message(lobby=lobby, view=waiting_view, interaction=interaction)
        
    async def handle_not_ready(self, interaction: discord.Interaction, lobby: Lobby) -> bool:
        res = lobby.unready(interaction.user)

        if res == ReadyResult.ALREADY_READY:
            await interaction.response.send_message("You're already not ready! 🦐", ephemeral=True)
            return
        
        if res == ReadyResult.NOT_IN_LOBBY:
            await interaction.response.send_message("No one asked if you're ready! 🤣", ephemeral=True)
            return
        
        elif res == ReadyResult.SUCCESS_PLAYER:
            # if there are no backup players, end the ready check and return to waiting state
            if len(lobby.get_fillers) == 0:
                await self._end_ready_check(interaction, lobby)
                # if there are still players (i.e. we didn't just close the lobby)
                if lobby.get_players:
                    await interaction.followup.send(f"Not enough players were ready after {interaction.user} said they were not ready.\nLobby is returning to waiting state.")
            elif lobby.all_ready():
                lobby.start_from_ready_check()
                await self._handle_after_starting_lobby(lobby, interaction)
                return
            else:
                await self._update_lobby_message(lobby=lobby, interaction=interaction)
                # ping all fillers
                msg = f"Player {interaction.user.name} is not ready! This lobby needs a filler!\n"
                for filler in lobby.get_fillers:
                    msg += f"<@{filler.id}>"
                await interaction.channel.send(msg)
                # dm all fillers
                for player in lobby.get_fillers:
                    if not player.is_pending_ready():
                        continue
                    dm_embed = make_lobby_notif_embed(lobby, " is about to start and needs fillers!", interaction.guild_id, interaction.channel_id)
                    try:
                        user = interaction.client.get_user(player.id) or await interaction.client.fetch_user(player.id)
                        await user.send(embed=dm_embed)
                    except Exception as e:
                        logger.exception(f"Unexpected error while DMing user {player.id} -- {e}")
        elif res == ReadyResult.SUCCESS_FILLER:
            await self._update_lobby_message(lobby=lobby, interaction=interaction)

    async def handle_end_ready_check(self, interaction: discord.Interaction, lobby: Lobby):
        if not lobby.in_lobby(interaction.user.id):
            await interaction.response.send_message("You can't end ready check for this lobby, you're not playing in it! 😡", ephemeral=True)
            return False
        await self._end_ready_check(interaction, lobby)
        await interaction.followup.send(f"{interaction.user.name} has cancelled Ready Check!")

    async def handle_start_lobby(self, interaction: discord.Interaction, lobby: Lobby, forced: bool) -> bool:
        """Handle starting a lobby"""
        if lobby.is_completed():
            await interaction.response.send_message("This lobby is already completed! 🙊", ephemeral=True)
            return True
        
        if not lobby.in_lobby(interaction.user.id):
            await interaction.response.send_message("You can't start this lobby, you're not playing in it! 😡", ephemeral=True)
            return False
        
        if not forced and lobby.state == LobbyState.PENDING:
            await interaction.response.send_message("This lobby is already starting! 🙊", ephemeral=True)
            return True
        
        success, final_players = lobby.start(forced)
        if success:
            # notify players
            await self._handle_after_starting_lobby(lobby, interaction)
            return True
        else:
            # offer force start if there are not enough players
            force_start_view = ForceStartView(timeout=60, lobby=lobby, controller=self)
            await interaction.response.send_message(
                embed=force_start_view.get_embed(),
                view=force_start_view,
                content=f"<@{interaction.user.id}>"
            )
            force_start_view.message = await interaction.original_response()
            return True
    
    async def handle_force_start_deny(self, lobby: Lobby, interaction: discord.Interaction = None) -> bool:
        """Handle denying force start. Returns True if handled, False otherwise."""
        if lobby.is_completed():
            await interaction.response.send_message("This lobby is already completed! 🙊", ephemeral=True)
            return False
        
        if interaction and not lobby.in_lobby(interaction.user.id):
            await interaction.response.send_message("You can't respond for this lobby, you're not playing in it! 😡", ephemeral=True)
            return False
        
        lobby.reset_pending()
        if interaction:
            await interaction.response.send_message("❌ Did not force start. The lobby is still waiting for more players.")
        else:
            await self.lobby_to_msg[lobby.id].channel.send(f"⏰ Force start expired. The lobby is still waiting for more players.")
        return True

    async def handle_close_lobby(self, interaction: discord.Interaction, lobby: Lobby=None):
        """Handle closing a lobby -- anyone who is not the owner is asked again to confirm """
        # if there's no explicit lobby passed in, get it by owner

        if lobby is None:
            lobby = self.lobby_manager.get_lobby_by_owner(interaction.user.id)
            if not lobby:
                await interaction.response.send_message("You do not have an active lobby. 😒", ephemeral=True)
                return
        
        if lobby.is_completed():
            await interaction.response.send_message("This lobby is already completed! 🙊", ephemeral=True)
            return
        
        if interaction.user.id != lobby.owner.id:
            close_confirm_view = CloseConfirmationView(60, None, interaction.user.id, lobby, self)
            await interaction.response.send_message(
                f"This is not your lobby <@{interaction.user.id}>! Are you sure you want to close it?", 
                view=close_confirm_view)
            close_confirm_view.msg = await interaction.original_response()
            return
        
        await self._close_lobby_internal(lobby.owner.id, interaction)
    
    async def handle_close_confirmation(self, msg: discord.Message, user_id: int, interaction: discord.Interaction, lobby: Lobby, close: bool):
        if user_id != interaction.user.id:
            await interaction.response.send_message(f"This is not your interaction!", ephemeral=True)
            return
        
        if close:
            await self._close_lobby_internal(lobby.owner.id, interaction)
        else:
            await msg.delete() 

    async def handle_dropout_active(self, interaction: discord.Interaction, lobby: Lobby, user: discord.Member):
        """Handle dropout lobby from active lobby"""
        if lobby.is_completed():
            await interaction.response.send_message("This lobby is already completed! 🙊", ephemeral=True)
            return
    
        await self._handle_participant_dropout(interaction, lobby, user)
    
    # async def handle_fill_in(self, interaction: discord.Interaction, lobby: Lobby, 
    #                        user: discord.Member, view: ActiveLobbyView):
    #     """Handle filling in to active lobby"""
    #     user_id = user.id
    #     current_players = len(lobby.get_players)
    #     strict_count = len(view.strict_ids)
        
    #     if user_id in view.strict_ids:
    #         # User is specifically invited
    #         result = lobby.add_player(user, forced=False)
    #         if result == LobbyAddResult.SUCCESS:
    #             view.strict_ids.remove(user_id)
    #             await self._update_lobby_message(lobby=lobby, interaction=interaction)
    #         else:
    #             await self._handle_add_result(interaction, result)
    #     elif current_players + strict_count == lobby.max_players:
    #         await interaction.response.send_message("You aren't a filler being waited for and/or there is no extra room. ☹", ephemeral=True)
    #     elif current_players + strict_count < lobby.max_players:
    #         result = lobby.add_player(user, forced=False)
    #         if result == LobbyAddResult.SUCCESS:
    #             await self._update_lobby_message(lobby=lobby, interaction=interaction)
    #         else:
    #             await self._handle_add_result(interaction, result)
    #     else:
    #         await interaction.response.send_message("A filler wasn't needed yet! 😡", ephemeral=True)
    
    async def handle_end_lobby(self, interaction: discord.Interaction, lobby: Lobby):
        """Handle ending an active lobby"""
        if lobby.is_completed():
            await interaction.response.send_message("This lobby is already completed! 🙊", ephemeral=True)
            return
        
        if not lobby.is_player(interaction.user.id):
            close_confirm_view = CloseConfirmationView(60, None, interaction.user.id, lobby, self)
            await interaction.response.send_message(
                f"This is not your lobby <@{interaction.user.id}>! Are you sure you want to close it?", 
                view=close_confirm_view)
            close_confirm_view.msg = await interaction.original_response()
            return
        
        await self._close_lobby_internal(lobby.owner.id, interaction)
    
    async def handle_show_specific_lobby(self, interaction: discord.Interaction, lobby_id: int, **kwargs):
        """Show a specific lobby"""
        lobby = self.lobby_manager.get_lobby_by_id(lobby_id)
        if lobby:
            await self._update_lobby_message(lobby=lobby, interaction=interaction)
        else:
            await interaction.response.send_message("Lobby not found!", ephemeral=True)
    
    async def show_lobbies(self, interaction: discord.Interaction):
        """Show all active lobbies in a dropdown"""
        all_lobbies = self.lobby_manager.get_all_lobbies()
        
        if not all_lobbies:
            await interaction.response.send_message("There are no currently active lobbies!", ephemeral=True)
            return
        
        timezone = await get_time_zone(interaction.user.id)
        if timezone == "":
            await interaction.response.send_message("Your timezone is not set yet! Run /set to register your timezone.", ephemeral=True)
            return
        
        view = LobbySelectView(120, timezone, all_lobbies, self, self.handle_show_specific_lobby)
        await interaction.response.send_message(view=view, ephemeral=True)

    async def bump_lobby(self, interaction: discord.Interaction, user: discord.Member):
        """Bump a user's lobby"""
        lobby = self.lobby_manager.get_lobby_by_owner(user.id)
        if not lobby:
            await interaction.response.send_message(f"{user.name} did not have an active lobby 😔", ephemeral=True)
            return
        
        await self._update_lobby_message(lobby=lobby, interaction=interaction)
    
    async def add_player_to_lobby(self, interaction: discord.Interaction, addee: discord.Member, forced: bool):
        """Force add a player to someone's lobby"""
        player = interaction.user
        lobbies = self.lobby_manager.get_lobbies_by_participant(player.id)
        if not lobbies:
            await interaction.response.send_message(f"{player.name} was not a part of any lobbies 😔", ephemeral=True)
            return
        elif len(lobbies) == 1:
            result = lobbies[0].add_player(addee, forced=forced)
            if result == LobbyAddResult.SUCCESS:
                await self._update_lobby_message(lobby=lobbies[0], interaction=interaction)
            else:
                await self._handle_add_result(interaction, result)
        else:
            timezone = await get_time_zone(interaction.user.id)
            if timezone == "":
                await interaction.response.send_message("Your timezone is not set yet! Run /set to register your timezone.", ephemeral=True)
                return
            
            view = LobbySelectView(120, timezone, lobbies, self, self.handle_force_add_to_specific_lobby, player=addee)
            await interaction.response.send_message(view=view, ephemeral=True)
                
    async def handle_force_add_to_specific_lobby(self, interaction: discord.Interaction, lobby_id: int, **kwargs):
        """Force-add a player to a specific lobby. Expects 'player': discord.Member in kwargs. """
        lobby = self.lobby_manager.get_lobby_by_id(lobby_id)
        if lobby:
            result = lobby.add_player(kwargs.get('player'), True)
            if result == LobbyAddResult.SUCCESS:
                await self._update_lobby_message(lobby=lobby, interaction=interaction)
            else:
                await self._handle_add_result(interaction, result)
        else:
            await interaction.response.send_message("Lobby not found!", ephemeral=True)

    async def remove_participant_from_lobby(self, interaction: discord.Interaction, removee: discord.Member):
        """Force remove a player to someone's lobby"""
        player = interaction.user
        lobbies = self.lobby_manager.get_lobbies_by_participant(player.id)
        if not lobbies:
            await interaction.response.send_message(f"{player.name} was not a part of any lobbies 😔", ephemeral=True)
            return
        elif len(lobbies) == 1:
            await self._handle_participant_dropout(interaction, lobbies[0], removee) 
        else:
            timezone = await get_time_zone(interaction.user.id)
            if timezone == "":
                await interaction.response.send_message("Your timezone is not set yet! Run /set to register your timezone.", ephemeral=True)
                return
            
            view = LobbySelectView(120, timezone, lobbies, self, self.handle_force_remove_from_specific_lobby, player=removee)
            await interaction.response.send_message(view=view, ephemeral=True)
        
        await interaction.followup.send(f"{interaction.user.name} has forcefully removed {removee.name} from this lobby!")

    async def handle_force_remove_from_specific_lobby(self, interaction: discord.Interaction, lobby_id: int, **kwargs):
        """Force-add a player to a specific lobby. Expects 'player': discord.Member in kwargs. """
        lobby = self.lobby_manager.get_lobby_by_id(lobby_id)
        if lobby:
            removee = kwargs.get('player')
            await self._handle_participant_dropout(interaction, lobby, removee)
        else:
            await interaction.response.send_message("Lobby not found!", ephemeral=True)

    async def _update_lobby_message(
            self, 
            lobby: Lobby,
            view: discord.ui.View=None,
            interaction: discord.Interaction=None):
        """Update the lobby message"""
        if interaction and not interaction.response.is_done():
            await interaction.response.defer()
        current_view = view or self.lobby_to_view[lobby.id]

        # disable play button if lobby is full
        # lowkey i hate how this is done but every other solution seemed worse
        if hasattr(current_view, 'play_button') and lobby.is_full():
            current_view.play_button.disabled = True
        elif hasattr(current_view, 'play_button'):
            current_view.play_button.disabled = False
        
        embed = current_view.create_lobby_embed()
        
        if lobby.id in self.lobby_to_msg:
            try:
                old_msg = self.lobby_to_msg[lobby.id]
                await old_msg.delete()
            except discord.HTTPException as e:
                if e.code == 50027:  # Invalid Webhook Token
                    # Refetch as regular message again and delete
                    logger.warning(f"Webhook expired for lobby message {old_msg.id}, refetching as regular message.")
                    regular_msg = await old_msg.channel.fetch_message(old_msg.id)
                    await regular_msg.delete()
                else:
                    logger.warning(f"Failed to delete old lobby message: {e}")
            except Exception as e:
                logger.warning(f"Failed to delete old lobby message: {e}")
        
        if interaction:
            sent = await interaction.followup.send(embed=embed, view=current_view)
            fetched = await sent.channel.fetch_message(sent.id)
        else:
            if lobby.id in self.lobby_to_msg:
                channel = self.lobby_to_msg[lobby.id].channel
            else:
                logger.error(f"No previous emssage foudn for lobby {lobby.id} and no interaction provided")
                return
            sent = await channel.send(embed=embed, view=current_view)
            fetched = await sent.channel.fetch_message(sent.id)
        self.lobby_to_msg[lobby.id] = fetched
    
    async def _handle_add_result(self, interaction: discord.Interaction, result: LobbyAddResult, is_filler: bool = False):
        """Handle the result of adding a player/filler"""
        if result == LobbyAddResult.ALREADY_IN_LOBBY:
            action = "filling" if is_filler else "playing"
            await interaction.response.send_message(f"This player is already {action} in this lobby! 😡", ephemeral=True)
        elif result == LobbyAddResult.LOBBY_FULL:
            await interaction.response.send_message("The lobby is already full 😞", ephemeral=True)
        elif result == LobbyAddResult.LOBBY_COMPLETED:
            await interaction.response.send_message("This lobby is already completed! 🙊", ephemeral=True)

    async def _handle_participant_dropout(self, interaction: discord.Interaction, lobby: Lobby, participant: discord.Member):
        # Handle when a player or filler leaves from an active lobby.
        
        result = lobby.remove_participant(participant)
        if result == LobbyRemoveResult.SUCCESS_PLAYER:
            await self._update_lobby_message(lobby=lobby, interaction=interaction)
            if lobby.is_active():
                # handle when a player drops out of an active lobby
                if not lobby._fillers:
                    await self.lobby_to_msg[lobby.id].channel.send("There are no fillers! This lobby needs fillers! 🐀🐁")
                else:
                    # Invite all fillers
                    mentions = " ".join(f"<@{filler.id}>" for filler in lobby.get_fillers)
                    channel_embed = make_lobby_invite_embed(lobby)
                    await self.lobby_to_msg[lobby.id].channel.send(
                        content=mentions,
                        embed=channel_embed
                    )
                    for player in lobby.get_fillers:
                        dm_embed = make_lobby_invite_embed(lobby, interaction.guild_id, interaction.channel_id)
                        try:
                            user = interaction.client.get_user(player.id) or await interaction.client.fetch_user(player.id)
                            await user.send(embed=dm_embed)
                        except Exception as e:
                            logger.exception(f"Unexpected error while DMing user {player.id} -- {e}")
        elif result == LobbyRemoveResult.SUCCESS_FILLER:
            await self._update_lobby_message(lobby=lobby, interaction=interaction)
        elif result == LobbyRemoveResult.LOBBY_EMPTY:
            await self._close_lobby_internal(lobby.owner.id, interaction)
            return
        elif result == LobbyRemoveResult.NOT_IN_LOBBY:
            await interaction.response.send_message("This player was not in the lobby! 😡", ephemeral=True)
            return

    # async def _wait_for_filler_response(self, filler_id: int, view: ActiveLobbyView, lobby: Lobby):
    #     """Wait for filler to respond to invitation"""
    #     await asyncio.sleep(300)  # 5 minutes
    #     if filler_id in view.strict_ids:
    #         view.strict_ids.remove(filler_id)
    #         message_parts = [f"<@{filler_id}> declined their spot. Anyone is free to join."]
    #         message_parts.extend([f"<@{filler.id}>" for filler in lobby._fillers])
    #         await self.lobby_to_msg[lobby.id].channel.send(' '.join(message_parts))
    
    async def _close_lobby_internal(self, owner_id: int, interaction: Optional[discord.Interaction] = None):
        """Internal method to close a lobby"""
        lobby_id = self.lobby_manager.get_lobby_by_owner(owner_id).id
        success = self.lobby_manager.close_lobby(owner_id)
        # delete lobby message, if it exists
        await self.lobby_to_msg[lobby_id].delete()
        
        if success:
            # cancel spam task if exists
            if owner_id in self.spam_tasks:
                self.spam_tasks[owner_id].cancel()
                del self.spam_tasks[owner_id]
            
            message = "Lobby successfully closed. 🔒"
            ephemeral = False
        else:
            message = "You did not have an active lobby. 😒"
            ephemeral = True
            
        if interaction:
            await interaction.response.send_message(content=message, ephemeral=ephemeral)
        # If no interaction (auto-close), we would send to the lobby channel
    
    def _setup_spam_updates(self, lobby: Lobby, channel):
        """Setup spam updates for bump channel"""
        async def spam_update_task():
            while lobby._state != LobbyState.COMPLETED:
                await asyncio.sleep(300) # wait 5 minutes between updates
                
                # Check if last message is from bot
                async for message in channel.history(limit=1):
                    if message.author.bot:
                        break
                    else:
                        # Update the message
                        embed = self.lobby_to_view[lobby.id].create_lobby_embed()
                        try:
                            old_msg = self.lobby_to_msg[lobby.id]
                            await old_msg.delete()
                            new_msg = await channel.send(embed=embed, view=self.lobby_to_view[lobby.id])
                            self.lobby_to_msg[lobby.id] = new_msg
                        except Exception as e:
                            logger.warning(f"Failed to update lobby message: {e}")
                    break
        
        task = asyncio.create_task(spam_update_task())
        self.spam_tasks[lobby.owner.id] = task
    
    async def _auto_close_lobby(self, lobby: Lobby, timeout: int, curr_lobby_state: LobbyState):
        """Auto-close lobby after timeout"""
        await asyncio.sleep(timeout)
        if curr_lobby_state != lobby.state:
            return 
        
        if lobby.state != LobbyState.COMPLETED:
            logger.info(f"Auto-closing lobby {lobby.id} due to timeout.")
            msg = f"{lobby.owner.display_name}'s lobby timing out. Closing lobby." if lobby.state != LobbyState.ACTIVE else \
                f"{lobby.owner.display_name}'s's lobby timing out. You've been playing for 6 hours. Touch some grass. 🌳"
            await self.lobby_to_msg[lobby.id].channel.send(msg)
            await self._close_lobby_internal(lobby.owner.id)

    async def handle_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        lobbies = self.lobby_manager.get_lobbies_by_participant(member.id, active=False)
        if not lobbies:
            return
        
        for lobby in lobbies:
            lobby.edit_participant_voicestate(member.id, after)
            
            # only perform following checks if the lobby is active
            if not lobby.is_active():
                continue

            # if the lobby hasn't become 'voice active' yet (i.e. not everyone, at some point in time, has joined voice), then don't check
            if not all(player.joined_voice for player in lobby.get_players):
                continue

            if after.channel == None: # meaning no longer connected to a channel
                channel_to_participant_count = defaultdict(int)
                
                participants = lobby.get_participants()
                for participant in participants:
                    # this can happen if person A leaves first and then person B causes this check again
                    if not participant.voice_state:
                        continue
                    if participant.voice_state.channel:
                        channel_to_participant_count[participant.voice_state.channel.id] += 1
                
                # if current players is low, make it so everyone has to leave to close the lobby
                num_curr_players = len(lobby.get_players)
                threshold = num_curr_players * 0.5 if num_curr_players > 3 else 1
                still_active = False
                for num_participants in channel_to_participant_count.values():
                    if num_participants >= threshold:
                        still_active = True
                
                # otherwise, threshold not met in any channel, close lobby.
                if not still_active:
                    logger.info(f"Auto-closing lobby {lobby.id} due to participants not being in voice.")
                    logger.info(channel_to_participant_count)
                    logger.info(lobby)
                    
                    await self.lobby_to_msg[lobby.id].channel.send(f"{lobby.owner.display_name}'s lobby is closing because most players left voice! 🙀")
                    await self._close_lobby_internal(lobby.owner.id)


    async def _handle_after_starting_lobby(self, lobby: Lobby, interaction: discord.Interaction = None) -> bool:
        await interaction.response.defer()
        message_parts = [f"<@{player.id}>" for player in lobby.get_players]
        channel_embed = make_lobby_notif_embed(lobby, " is starting now!")

        # update lobby to active state
        timeout = 21600 # 6 hours until timeout for active lobby
        new_view = ActiveLobbyView(timeout=timeout, lobby=lobby, controller=self)
        self.lobby_to_view[lobby.id] = new_view
        
        await interaction.channel.send(content=' '.join(message_parts), embed=channel_embed)
        await self._update_lobby_message(lobby=lobby, view=new_view, interaction=interaction)

        dm_embed = make_lobby_notif_embed(lobby, " is starting now!", interaction.guild_id, interaction.channel_id)
        for player in lobby.get_players:
            try:
                user = interaction.client.get_user(player.id) or await interaction.client.fetch_user(player.id)
                await user.send(embed=dm_embed)
            except Exception as e:
                logger.exception(f"Unexpected error while DMing user {player.id} -- {e}")
        
        
        # create new auto close task for the active lobby view
        asyncio.create_task(self._auto_close_lobby(lobby, timeout, LobbyState.ACTIVE))

        # update every player's voice state as the baseline now that the lobby is active
        for player in lobby.get_players:
            player.update_joined_voice()
