import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import discord
from discord.ext import commands
from dotenv import load_dotenv
from gtts import gTTS

from gpt import GPT
from music import Music

logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s "%(funcName)s" [%(levelname)s]: %(message)s', datefmt='%d.%m.%Y-%H:%M:%S')
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

load_dotenv()

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")


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

    async def setup_hook(self) -> None:
        self.__logger.debug("Start loading modules")
        await self.add_cog(Music(bot))
        await self.add_cog(GPT(bot))
        await self.tree.sync()
        self.__logger.debug("Setup hook completed")

    async def on_ready(self):
        logger.info(f'Logged in as "{bot.user.name}" with ID {bot.user.id}')
        activity = discord.CustomActivity(name="Слушаем музыку вместе", emoji=discord.PartialEmoji(name="🎵"))
        await bot.change_presence(status=discord.Status.idle, activity=activity)


bot = FununaNun()


async def play_file(filename: str, voice: discord.VoiceClient):
    # проиграть аудио
    voice.play(discord.FFmpegPCMAudio(filename))
    # ожидать завершения проигрывания
    while voice.is_playing():
        await asyncio.sleep(1)
    # остановить проигрывание
    voice.stop()
    # отключиться от голосового канала
    return await voice.disconnect()


async def gtts_get_file(text: str):
    executor = ThreadPoolExecutor()

    def gtts_generate():
        tts = gTTS(text=text, lang='ru')
        tts.save('sound.mp3')

    return await bot.loop.run_in_executor(executor, gtts_generate)


@bot.command(name="tts")
async def _tts(ctx: commands.Context, *, text: str):
    if ctx.author.voice is None:
        await ctx.reply("Ты не в канале")
        return

    if ctx.message.reference:
        message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        text = message.content

    async with ctx.typing():
        await gtts_get_file(text)

    # подключаем бота к каналу
    voice = await ctx.author.voice.channel.connect()

    # проигрываем файл
    await play_file("sound.mp3", voice)

    # удалить файл
    try:
        os.remove("sound.mp3")
    except PermissionError:
        pass
    except Exception as e:
        print(e)

    embed = discord.Embed(title="TTS", description=text, color=discord.Color.blurple())
    await interaction.followup.send(embed=embed)

    return


bot.run(DISCORD_TOKEN)
