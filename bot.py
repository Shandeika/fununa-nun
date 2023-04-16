import asyncio
import datetime
import io
import logging
import os
import re
import socket
import subprocess
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

import aiohttp
import discord
import psutil as psutil
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from gtts import gTTS

from basic_commands import BasicCommands
from dalle import DALLE
from gpt import GPT
from music import Music
from responder import Responder

logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s "%(funcName)s" [%(levelname)s]: %(message)s', datefmt='%d.%m.%Y-%H:%M:%S')
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

load_dotenv()

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

VERSION = "0.0.1"


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
        await self.add_cog(BasicCommands(bot))
        await self.add_cog(Responder(bot))
        await self.add_cog(DALLE(bot))
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


class TracebackShowButton(discord.ui.View):
    def __init__(self, traceback_text: str):
        super().__init__()
        self._tb = traceback_text

    @discord.ui.button(label="Показать traceback", style=discord.ButtonStyle.red, emoji="🛠")
    async def traceback_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self._tb) >= 4096:
            embed = discord.Embed(title="Traceback",
                                  description="Traceback прикреплен отдельным файлом, так как он слишком большой",
                                  color=discord.Color.red())
            tb_file = discord.File(io.BytesIO(self._tb.encode("utf-8")), filename="traceback.txt")
            return await interaction.response.send_message(embed=embed, file=tb_file, ephemeral=True)
        embed = discord.Embed(title="Traceback", description=f"```\n{self._tb}\n```", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.error
async def app_commands_error_handler(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error.original, discord.Forbidden):
        embed = discord.Embed(title="Ошибка", description="Нет прав сделать это", color=discord.Color.red())
    elif isinstance(error.original, aiohttp.ClientResponseError):
        embed = discord.Embed(title="Ошибка", description="Ошибка при отправке запроса", color=discord.Color.red())
    else:
        embed = discord.Embed(title="Ошибка", description=f"Неизвестная ошибка", color=discord.Color.red())
        embed.add_field(name="Тип ошибки", value=type(error.original))
        embed.add_field(name="Текст ошибки", value=str(error.original))
        embed.add_field(name="Информация об ошибке", value=str(error))
    traceback_text = "".join(
        traceback.format_exception(type(error.original), error.original, error.original.__traceback__))
    try:
        await interaction.response.send_message(embed=embed, view=TracebackShowButton(traceback_text))
    except discord.InteractionResponded:
        await interaction.followup.send(embed=embed, view=TracebackShowButton(traceback_text))


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


@bot.tree.command(
    name="status",
    description="Показывает статус бота"
)
async def _status(interaction: discord.Interaction):
    def process_time(seconds):
        days = seconds // 86400
        seconds %= 86400
        hours = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        result = ""
        if days > 0:
            result += f"{days} дней, "
        if hours > 0:
            result += f"{hours} часов, "
        if minutes > 0:
            result += f"{minutes} минут"
        return result.strip(", ")

    server_hostname = socket.gethostname()
    discord_gateway = bot.ws.latency * 1000
    ram_free = psutil.virtual_memory()[3] / 1024 / 1024
    ram_total = psutil.virtual_memory()[0] / 1024 / 1024
    ram_used = ram_total - ram_free
    cpu_usage = psutil.cpu_percent()
    la_1, la_5, la_15 = psutil.getloadavg()

    server_uptime = process_time(int(time.time() - psutil.boot_time()))

    # Запустить команду systemctl status fn.service и сохранить ее вывод в переменной output
    output = subprocess.check_output(['systemctl', 'status', 'fn.service'], universal_newlines=True)

    # Найти строку "Active:" в выводе и получить ее значение
    match = re.search(r'Active:\s+(.*?)\n', output)
    active_value = match.group(1)

    # Найти строку "since" в значении Active и получить ее значение
    match = re.search(r'since\s+(.*)', active_value)
    bot_uptime_dt = datetime.datetime.strptime(match.group(1).split(";")[0], '%a %Y-%m-%d %H:%M:%S %Z')
    bot_uptime = process_time(int(time.time() - bot_uptime_dt.timestamp()))

    embed_description = f"Версия: `{VERSION}`\n" \
                        f"Пинг шлюза Discord `{discord_gateway:.2f} мс`\n" \
                        f"Время работы бота **{bot_uptime}**"
    server_label = f"Сервер: `{server_hostname}`\n" \
                   f"LA1 `{la_1:.2f}`, LA5 `{la_5:.2f}`, LA15 `{la_15:.2f}`\n" \
                   f"Загрузка CPU `{cpu_usage:.2f}%`\n" \
                   f"Загрузка RAM `{ram_used:.2f} МБ` из `{ram_total:.2f} МБ`\n" \
                   f"Свободная RAM `{ram_free:.2f} МБ`\n" \
                   f"Время работы **{server_uptime}**"

    embed = discord.Embed(title="Статус бота", description=embed_description, color=discord.Color.blurple())
    embed.add_field(name="Сервер", value=server_label, inline=False)
    await interaction.response.send_message(embed=embed)


bot.run(DISCORD_TOKEN)
