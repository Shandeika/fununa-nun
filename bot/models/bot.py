import logging
import os
import traceback

import discord
import wavelink
from discord import ApplicationContext, DiscordException
from discord.ext import commands

from bot.models import errors
from bot.views import TracebackShowButton
from utils import respond_or_followup

LAVALINK_HOST = os.environ.get("LAVALINK_HOST")
LAVALINK_PORT = int(os.environ.get("LAVALINK_PORT"))
LAVALINK_PASSWORD = os.environ.get("LAVALINK_PASSWORD")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s "%(funcName)s" [%(levelname)s]: %(message)s',
    datefmt="%d.%m.%Y-%H:%M:%S",
)


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
        for filename in os.listdir("./bot/modules"):
            if filename.endswith(".py"):
                self.load_extension(f"bot.modules.{filename[:-3]}")
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

    async def on_application_command_error(
        self, ctx: ApplicationContext, exception: DiscordException
    ) -> None:
        if isinstance(exception, discord.ApplicationCommandError):
            if isinstance(exception, discord.ApplicationCommandInvokeError):
                if isinstance(exception.original, errors.FununaNunException):
                    if issubclass(type(exception.original), errors.MemberNotInVoice):
                        embed = discord.Embed(
                            title="Ошибка",
                            description="Вы должны быть в голосовом канале",
                            color=discord.Color.red(),
                        )
                        return await respond_or_followup(ctx, embed, ephemeral=True)
                else:
                    embed = discord.Embed(
                        title="Ошибка при выполнении команды",
                        description="Ниже представлены детали ошибки",
                        color=discord.Color.red(),
                    )
                    embed.add_field(
                        name="Тип ошибки", value=str(type(exception.original))
                    )
                    embed.add_field(name="Текст ошибки", value=str(exception.original))
                    embed.add_field(name="Информация об ошибке", value=str(exception))
                    traceback_text = "".join(
                        traceback.format_exception(
                            type(exception.original),
                            exception.original,
                            exception.original.__traceback__,
                        )
                    )
                    return await respond_or_followup(
                        ctx,
                        embed,
                        view=TracebackShowButton(traceback_text),
                        ephemeral=True,
                    )
