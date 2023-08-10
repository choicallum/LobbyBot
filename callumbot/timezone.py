from pathlib import Path

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
