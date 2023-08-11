from pathlib import Path
from settings import USERS_PATH
def getTimeZone(userId: str) -> str:
    user_file = Path(f'{USERS_PATH}/{userId}.txt')
    if not user_file.exists():
        return ''    
    with user_file.open() as f:
        return f.read()

def setTimeZone(userId: str, timezone: str):
    verboseTimeZone = {
        "PST": "US/Pacific",
        "MST": "US/Mountain",
        "CST": "US/Central",
        "EST": "US/Eastern",
        "Troll": "Antarctica/Troll",
        "Goose": "America/Goose_Bay"
    }[timezone]

    user_file = Path(f'{USERS_PATH}/{userId}.txt')
    with user_file.open("w") as f:
        f.write(verboseTimeZone)
