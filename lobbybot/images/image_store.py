import json
import time
import random
import requests
import os
from urllib.parse import urlparse, urlunparse
from typing import List, Optional, Tuple
from dataclasses import dataclass
from lobbybot.settings import TENOR_API_KEY
from logging import getLogger
import discord
from datetime import datetime

logger = getLogger(__name__)

@dataclass
class ImgEntry:
    """Represents an image entry in the store."""
    url: str
    submitted_by_name: str
    submitted_by_id: int
    timestamp: int

class ImgStore:
    def __init__(self, path: Optional[str] = None):
        if path is None:
            base_dir = os.path.dirname(__file__)
            path = os.path.join(base_dir, "..", "resources", "lobby_imgs.json")
        self.path = os.path.abspath(path)
        self.imgs: List[ImgEntry] = []
        self.load()

    def load(self) -> None:
        """Load images from the JSON file."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.imgs = [ImgEntry(**entry) for entry in data]
            logger.info(f"Loaded {len(self.imgs)} images from {self.path}")
        except FileNotFoundError:
            logger.info(f"no existing image store found at {self.path}")
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump([], f)
                logger.debug(f"created empty image store at {self.path}")
            except OSError as e:
                logger.error(f"error creating empty image store: {e}")
            self.imgs = []
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"error loading image store: {e}")
            self.imgs = []

    def save(self) -> None:
        """Save images to the JSON file."""
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            
            with open(self.path, "w", encoding="utf-8") as f:
                data = [
                    {
                        "url": entry.url,
                        "submitted_by_name": entry.submitted_by_name,
                        "submitted_by_id": entry.submitted_by_id,
                        "timestamp": entry.timestamp
                    }
                    for entry in self.imgs
                ]
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.imgs)} images to {self.path}")
        except OSError as e:
            logger.error(f"Error saving image store: {e}")

    def add_img(self, url: str, submitted_by_name: str, submitted_by_id: int) -> Tuple[bool, str]:
        """Add an image to the store."""
        logger.info(f"attempting to add url {url} submitted by {submitted_by_name} ({submitted_by_id})")

        cleaned_url = self._clean_url(url)
        if not cleaned_url:
            return False, "Failed to process URL."
        
        if any(img.url == cleaned_url for img in self.imgs):
            return False, "Image already in pool."
        
        if not self._validate_image(cleaned_url):
            return False, "Invalid image URL or image not accessible."
        
        entry = ImgEntry(cleaned_url, submitted_by_name, submitted_by_id, int(time.time()))
        self.imgs.append(entry)
        self.save()
        logger.info(f"Successfully added image: {cleaned_url}")
        return True, ""

    def _clean_url(self, url: str) -> Optional[str]:
        """Clean and process URL, converting Tenor URLs to direct GIF URLs."""
        try:
            # remove query / fragments (?, #)
            parsed = urlparse(url)
            cleaned_parsed = parsed._replace(query="", fragment="")
            cleaned_url = urlunparse(cleaned_parsed)

            # Handle Tenor URLs
            if parsed.netloc in {"tenor.com", "www.tenor.com"}:
                tenor_url = self._process_tenor_url(parsed)
                return tenor_url if tenor_url else cleaned_url
            
            return cleaned_url
        except Exception as e:
            logger.error(f"Error cleaning URL {url}: {e}")
            return None

    def _process_tenor_url(self, parsed_url) -> Optional[str]:
        """Convert Tenor URL to direct GIF URL using Tenor API."""
        if not TENOR_API_KEY:
            logger.warning("TENOR_API_KEY not configured")
            return None
        
        path = parsed_url.path
        if not path:
            return None
        
        # Extract GIF ID from URL path
        parts = path.split("-")
        if not parts or not parts[-1].isdigit():
            logger.warning(f"could not extract gif id from Tenor URL path: {path}")
            return None
        
        gif_id = parts[-1]
        return self._fetch_tenor_direct_url(gif_id)

    def _fetch_tenor_direct_url(self, gif_id: str) -> Optional[str]:
        """ Fetch direct GIF URL from Tenor API. """
        try:
            response = requests.get(
                "https://tenor.googleapis.com/v2/posts",
                params={
                    "key": TENOR_API_KEY,
                    "ids": gif_id,
                    "client_key": "callumbot",
                    "media_filter": "gif,mediumgif,tinygif"
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("results"):
                logger.warning(f"no results found for Tenor GIF ID: {gif_id}")
                return None
            
            formats = data["results"][0].get("media_formats", {})
            
            # Try different format preferences
            for format_key in ["gif", "mediumgif", "tinygif"]:
                if format_key in formats and "url" in formats[format_key]:
                    direct_url = formats[format_key]["url"]
                    logger.debug(f"found direct Tenor URL: {direct_url}")
                    return direct_url
            
            logger.warning(f"No suitable GIF format found for Tenor ID: {gif_id}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"error fetching tenor gif id {gif_id}: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"error parsing Tenor API response for gif: {gif_id}: {e}")
            return None

    def _validate_image(self, url: str) -> bool:
        """Validate that URL points to an accessible image."""
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            
            if response.status_code != 200:
                logger.debug(f"image verification failed {response.status_code}: {url}")
                return False
            
            content_type = response.headers.get("Content-Type", "").lower()
            if not content_type.startswith("image/"):
                logger.debug(f"image verification failed -- invalid content type '{content_type}': {url}")
                return False
            
            return True
            
        except requests.RequestException as e:
            logger.debug(f"image validation failed - request error: {url} - {e}")
            return False
    
    def get_random_img(self) -> Optional[str]:
        """ Get a random image URL from the store."""
        if not self.imgs:
            return None
        return random.choice(self.imgs).url

    def remove_img(self, url: str) -> bool:
        """ Remove an image from the store by URL. """
        original_count = len(self.imgs)
        self.imgs = [img for img in self.imgs if img.url != url]
        
        if len(self.imgs) < original_count:
            self.save()
            return True
        
        return False

# View to display all images in a gallery format
class ImgStoreView(discord.ui.View):
    def __init__(self, img_store: ImgStore):
        super().__init__(timeout=86400) # 24 hours
        self.img_store = img_store
        self.imgs = img_store.imgs
        self.index = 0

    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, row=0)
    async def left_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.imgs)
        await interaction.response.edit_message(embed=self.get_embed(interaction), view=self)
        
    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, row=0)
    async def right_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.imgs)
        await interaction.response.edit_message(embed=self.get_embed(interaction), view=self)

    def get_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(
            color=discord.Color.blue()
        )

        if not interaction.guild:
            embed.description = "This command can only be used in a server."
            return embed 

        embed.set_author(
            name=f"{interaction.guild.name}'s Gallery",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )
        
        if not self.imgs:
            embed.add_field(name="No images in gallery", value="Use `/add_img <url>` to add images.")
            return embed
        
        img = self.imgs[self.index]
        embed.description = (f"**📷 Added by <@{img.submitted_by_id}> on <t:{img.timestamp}:f>**")
        embed.set_image(url=img.url)
        embed.set_footer(text=f"{self.index+1}/{len(self.imgs)}  •  URL: {img.url}")
        
        return embed

# singleton
_img_store_instance: Optional[ImgStore] = None

def get_img_store() -> ImgStore:
    global _img_store_instance
    if _img_store_instance is None:
        _img_store_instance = ImgStore()
    return _img_store_instance

def create_img_store_gallery(interaction: discord.Interaction):
    ''' returns (embed, view) tuple for showing all images'''
    img_store = get_img_store()
    view = ImgStoreView(img_store)
    embed = view.get_embed(interaction)
    return embed, view
