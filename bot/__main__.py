import os

from .models import FununaNun

bot = FununaNun()
bot.run(os.environ.get("DISCORD_TOKEN"))
