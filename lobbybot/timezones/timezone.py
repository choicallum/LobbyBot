import discord
import logging
from pathlib import Path
from ..settings import USERS_PATH
from datetime import datetime, date, timedelta
import pytz
from .times import ASAP_TIME
logger = logging.getLogger(__name__)

async def get_time_zone(id: int) -> str:
    user_file = Path(f'{USERS_PATH}/{id}.txt')
    if not user_file.exists():
        logger.info(f"Failed to find {id}'s timezone data file")
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
    timezone_view = discord.ui.View(timeout=60)
    timezone_view.add_item(select)
    await interaction.response.send_message(view=timezone_view, ephemeral=True)
    
    async def on_select(interaction: discord.Interaction):
        write_timezone(interaction.user.id, select.values[0])
        await interaction.response.send_message(content="Your timezone has been set successfully.", ephemeral=True)
 
    select.callback = on_select

def write_timezone(id: int, timezone: str):
    verbose_timezone = {
        "PST": "US/Pacific",
        "MST": "US/Mountain",
        "CST": "US/Central",
        "EST": "US/Eastern"
    }[timezone]

    user_file = Path(f'{USERS_PATH}/{id}.txt')
    
    # Ensure the directory exists
    user_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Write the timezone to the file
    with user_file.open("w") as f:
        f.write(verbose_timezone)

async def parse_time_input(interaction: discord.Interaction, time: str, timezone: str):
    """Parse time input """
    if time.lower() in ["now", "asap"]:
        return ASAP_TIME
        
    try:
        if ':' in time:
            input_time = datetime.strptime(time, "%I:%M%p")
        else:
            input_time = datetime.strptime(time, "%I%p")
    except ValueError:
        await interaction.response.send_message(
            "Invalid time format. Please use `[hour]:[minutes][AM|PM]`, `[hour][AM|PM]`, or `asap/now`.", 
            ephemeral=True
        )
        return None
    
    user_tz = pytz.timezone(timezone)
    now_in_user_tz = datetime.now(user_tz)
    
    today = now_in_user_tz.date()
    target_time = input_time.replace(year=today.year, month=today.month, day=today.day)
    localized_target = user_tz.localize(target_time)
    
    # If the target time has already passed today (given a buffer), schedule for tomorrow
    buffer = timedelta(minutes=30)
    if localized_target <= now_in_user_tz - buffer:
        localized_target += timedelta(days=1)
    
    utc_time = int(localized_target.timestamp())
    
    return utc_time
