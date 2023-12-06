import logging

from discord.ext import commands

from .bot import FununaNun


class BasicCog(commands.Cog):
    def __init__(self, bot: FununaNun):
        self.bot = bot
        self._logger = logging.getLogger(f"modules.{self.__class__.__name__.lower()}")
