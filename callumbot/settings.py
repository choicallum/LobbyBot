import os
import logging

from dotenv import load_dotenv

logger = logging.getLogger()

load_dotenv()
DISCORD_API_SECRET = os.getenv("DISCORD_API_TOKEN")
USERS_PATH = os.getenv("USERS_PATH")
LOG_PATH = os.getenv("LOG_PATH")

logger.setLevel(logging.INFO)
# logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename=f"{LOG_PATH}/infos.log", encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

