import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import discord
from discord import app_commands
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
        logger.info(f'Logged in as "{self.user.name}" with ID {self.user.id}')
        activity = discord.CustomActivity(name="Слушаем музыку вместе", emoji=discord.PartialEmoji(name="🎵"))
        await bot.change_presence(status=discord.Status.idle, activity=activity)

    async def play_file(self, filename: str, voice: discord.VoiceClient):
        # проиграть аудио
        voice.play(discord.FFmpegPCMAudio(filename))
        # ожидать завершения проигрывания
        while voice.is_playing():
            await asyncio.sleep(1)
        # остановить проигрывание
        voice.stop()
        # отключиться от голосового канала
        return await voice.disconnect()

    async def gtts_get_file(self, text: str):
        executor = ThreadPoolExecutor()

        def gtts_generate():
            tts = gTTS(text=text, lang='ru')
            tts.save('sound.mp3')

        return await bot.loop.run_in_executor(executor, gtts_generate)


bot = FununaNun()





@bot.tree.command(
    name="tts",
    description="Озвучит введенную фразу в голосовом канале"
)
@app_commands.rename(
    text="текст"
)
@app_commands.describe(
    text="Текст, который нужно озвучить"
)
async def _tts(interaction: discord.Interaction, text: str):
    if interaction.user.voice is None:
        embed = discord.Embed(title="Ошибка", description="Ты не в канале", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
        return
    await interaction.response.defer(ephemeral=False, thinking=True)

    await bot.gtts_get_file(text)

    # подключаем бота к каналу
    voice = await interaction.user.voice.channel.connect()

    # проигрываем файл
    await bot.play_file("sound.mp3", voice)

    embed = discord.Embed(title="TTS", description=text, color=discord.Color.blurple())
    await interaction.followup.send(embed=embed)

    return


bot.run(DISCORD_TOKEN)
