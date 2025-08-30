import discord
from datetime import datetime
from lobbybot.lobby.models import Lobby
from lobbybot.images.image_store import get_img_store
from lobbybot.timezones import ASAP_TIME
from typing import List, Optional

def make_lobby_ready_embed(lobby: Lobby, guild: Optional[str] = None, channel: Optional[str] = None) -> discord.Embed:
    embed = discord.Embed(
        description=f"{lobby.owner.name}'s {lobby.game} lobby is starting now!",
        color=discord.Color.green()
    )
    if guild and channel:
        # add link to channel
        embed.description += f"\n[Jump to lobby channel](https://discord.com/channels/{guild}/{channel})"
        # also add an image for fun since it's in dms anyways
        embed.set_image(url=get_img_store().get_random_img())
    embed.set_author(
        name=f"{lobby.owner.name}'s {lobby.game} lobby",
        icon_url=lobby.owner.display_avatar.url
    )

    if lobby.time != ASAP_TIME:
        ts = datetime.fromtimestamp(lobby.time)
    else:
        ts = datetime.fromtimestamp(lobby.created_at)

    embed.set_footer(text="Originally scheduled for")
    embed.timestamp = ts
    return embed

def make_lobby_invite_embed(lobby: Lobby, guild: Optional[str] = None, channel: Optional[str] = None):
    embed = discord.Embed(
        description=f"You're invited to fill {lobby.owner.name}'s {lobby.game} lobby!",
        color=discord.Color.green()
    )
    if guild and channel:
        # add link to channel
        embed.description += f"\n[Jump to lobby channel](https://discord.com/channels/{guild}/{channel})"
        # also add an image for fun since it's in dms anyways
        embed.set_image(url=get_img_store().get_random_img())
    embed.set_author(
        name=f"{lobby.owner.name}'s {lobby.game} lobby",
        icon_url=lobby.owner.display_avatar.url
    )

    if lobby.time != ASAP_TIME:
        ts = datetime.fromtimestamp(lobby.time)
    else:
        ts = datetime.fromtimestamp(lobby.created_at)

    embed.set_footer(text="Originally scheduled for")
    embed.timestamp = ts
    return embed

def make_lobby_overview_embed(lobbies: List[Lobby], threads: List[discord.Thread]) -> discord.Embed:
    """Creates an embed listing all active lobbies in this channel with links to their threads"""
    embed = discord.Embed(
        title="Active Lobbies",
        description="Here are the currently active lobbies in this channel:",
        color=discord.Color.pink()
    )

    for lobby, thread in zip(lobbies, threads):
        if thread:
            embed.add_field(
                name=f"{lobby.game} by {lobby.owner.display_name}",
                value=f"[Join Thread]({thread.jump_url})",
                inline=False
            )
    return embed

