import os
import logging

from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger()
VERSION = "2025/08/26 v2"

load_dotenv()
DISCORD_API_SECRET = os.getenv("DISCORD_API_TOKEN")
TENOR_API_KEY = os.getenv("TENOR_API_KEY")
BASE_DIR = Path(__file__).parent
USERS_PATH = BASE_DIR / os.getenv("USERS_PATH")
LOG_PATH = BASE_DIR / os.getenv("LOG_PATH")
RESOURCES_PATH = BASE_DIR / os.getenv("RESOURCES_PATH")
BUMP_LOBBY_CHANNEL_ID = int(os.getenv("BUMP_LOBBY_CHANNEL_ID"))


logger.setLevel(logging.INFO)
# logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename=f"{LOG_PATH}/infos.log", encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

