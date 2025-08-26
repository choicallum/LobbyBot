import json
import time
import random
import requests
import os
from typing import List, Optional, Tuple

class ImgEntry:
    def __init__(self, url: str, submitted_by: str, timestamp: float):
        self.url = url
        self.submitted_by = submitted_by
        self.timestamp = timestamp

class ImgStore:
    def __init__(self, path=None):
        if path is None:
            base_dir = os.path.dirname(__file__)
            path = os.path.join(base_dir, "..", "resources", "lobby_imgs.json")
        self.path = os.path.abspath(path)
        self.imgs: List[ImgEntry] = []
        self.load()

    def load(self):
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
                self.imgs = [ImgEntry(**entry) for entry in data]
        except FileNotFoundError:
            self.imgs = []

    def save(self):
        with open(self.path, "w") as f:
            json.dump([entry.__dict__ for entry in self.imgs], f, indent=2)

    def add_img(self, url: str, submitted_by: str) -> Tuple[bool, str]:
        url = url.strip()
        if any(g.url == url for g in self.imgs):
            return False, "Image already in pool."
        if self.validate_image(url):
            entry = ImgEntry(url, submitted_by, time.time())
            self.imgs.append(entry)
            self.save()
            return True, ""
        return False, "Invalid image url."

    def validate_image(self, url: str) -> bool:
        try:
            r = requests.head(url, timeout=5)
            content_type = r.headers.get("Content-Type", "")
            return r.status_code == 200 and content_type.lower().startswith("image/")
        except requests.RequestException:
            return False
    
    def get_random_img(self) -> Optional[str]:
        candidates = [g.url for g in self.imgs]
        return random.choice(candidates) if candidates else None

    def remove_img(self, url: str):
        self.imgs = [g for g in self.imgs if g.url != url]
        self.save()

# singleton
_img_store_instance = None

def get_img_store():
    global _img_store_instance
    if _img_store_instance is None:
        _img_store_instance = ImgStore()
    return _img_store_instance
