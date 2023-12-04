import logging
import os

import discord
import wavelink
from discord.ext import commands

LAVALINK_HOST = os.environ.get("LAVALINK_HOST")
LAVALINK_PORT = int(os.environ.get("LAVALINK_PORT"))
LAVALINK_PASSWORD = os.environ.get("LAVALINK_PASSWORD")


class FununaNun(commands.Bot):
    def __init__(self, **options):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix="!",
            intents=intents,
            # help_command=None,
            **options,
        )
        self.owner_id = 335464992079872000
        self.__logger = logging.getLogger("bot")
        self.VERSION = "0.1.0"

    async def on_connect(self):
        self.__logger.debug("Start loading modules")
        for filename in os.listdir("./modules"):
            if filename.endswith(".py"):
                self.load_extension(f"modules.{filename[:-3]}")
        self.__logger.debug("Setup hook completed")
        await self.sync_commands()
        await self.connect_node()

    async def connect_node(self):
        self.__logger.info("Connecting to Lavalink...")
        node = wavelink.Node(
            uri=f"http://{LAVALINK_HOST}:{LAVALINK_PORT}", password=LAVALINK_PASSWORD
        )
        await wavelink.Pool.connect(nodes=[node], client=self)
        self.__logger.info("Connected to Lavalink!")

    async def on_ready(self):
        self.__logger.info(f'Logged in as "{self.user.name}" with ID {self.user.id}')
        activity = discord.CustomActivity(name="Слушаем музыку вместе")
        await self.change_presence(status=discord.Status.idle, activity=activity)
