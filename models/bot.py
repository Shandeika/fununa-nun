import logging
import os

import discord
from discord.ext import commands


class FununaNun(commands.Bot):
    def __init__(self, **options):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix="!",
            intents=intents,
            # help_command=None,
            **options
        )
        self.owner_id = 335464992079872000
        self.__logger = logging.getLogger("bot")
        self.VERSION = "0.1.0"

    async def setup_hook(self) -> None:
        self.__logger.debug("Start loading modules")
        for filename in os.listdir("./modules"):
            if filename.endswith(".py"):
                await self.load_extension(f"modules.{filename[:-3]}")
        await self.tree.sync()
        self.__logger.debug("Setup hook completed")

    async def on_ready(self):
        self.__logger.info(f'Logged in as "{self.user.name}" with ID {self.user.id}')
        activity = discord.CustomActivity(name="Слушаем музыку вместе", emoji=discord.PartialEmoji(name="🎵"))
        await self.change_presence(status=discord.Status.idle, activity=activity)
