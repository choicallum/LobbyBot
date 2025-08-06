import discord
import logging
from pathlib import Path
from settings import USERS_PATH

logger = logging.getLogger(__name__)

async def get_time_zone(interaction: discord.Interaction) -> str:
    user_file = Path(f'{USERS_PATH}/{interaction.user.id}.txt')
    if not user_file.exists():
        logger.info(f"Failed to find {interaction.user.id}'s timezone data file")
        await interaction.response.send_message("Your timezone has not been set yet. Please use /set to set your timezone.", ephemeral=True)
        return ""
    with user_file.open() as f:
        return f.read()

async def set_time_zone(interaction: discord.Interaction):
    select = discord.ui.Select(
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
        write_time_zone(interaction.user.id, select.values[0])
        await interaction.response.send_message(content="Your timezone has been set successfully.", ephemeral=True)
 
    select.callback = on_select

def write_time_zone(userId: str, timezone: str):
    verboseTimeZone = {
        "PST": "US/Pacific",
        "MST": "US/Mountain",
        "CST": "US/Central",
        "EST": "US/Eastern"
    }[timezone]

    user_file = Path(f'{USERS_PATH}/{userId}.txt')
    
    # Ensure the directory exists
    user_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write the timezone to the file
    with user_file.open("w") as f:
        f.write(verboseTimeZone)
