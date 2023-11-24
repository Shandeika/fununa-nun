import asyncio
import json

from custom_dataclasses import Track
from ytdl import ytdl


async def get_info_yt(url: str) -> Track:
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    track = Track(
        title=data.get('title'),
        url=data.get('url'),
        duration=data.get('duration'),
        image_url=data.get('thumbnail'),
        raw_data=data,
        original_url=url
    )
    return track
