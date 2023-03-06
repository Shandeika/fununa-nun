# Suppress noise about console usage from errors
import asyncio
import logging
import random
from concurrent.futures import ThreadPoolExecutor

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands

yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

logger = logging.getLogger("bot")


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        # определить, стрим ли это
        if "youtube.com" in url or "youtu.be" in url:
            stream = False
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Player:
    def __init__(self):
        self._queue = list()
        self._current = None
        self._voice = None

    @property
    def queue(self):
        return self._queue

    @property
    def current(self):
        return self._current

    @property
    def voice(self):
        return self._voice

    @voice.setter
    def voice(self, value):
        self._voice = value

    def add(self, item):
        self._queue.append(item)

    def next(self):
        if len(self._queue) == 0:
            self._current = None
            return self._current
        self._current = self._queue.pop(0)
        return self._current

    def clear(self):
        self._queue.clear()
        self._current = None
        self._voice = None

    def is_empty(self):
        return len(self._queue) == 0

    async def play(self):
        while True:
            if self._current is None:
                self._current = self.next()
            if self._current is None:
                return
            self._voice.play(self._current, after=lambda e: self.next())
            while self._voice.is_playing():
                await asyncio.sleep(1)
            if self.is_empty():
                return

    async def stop(self):
        self._voice.stop()
        self.clear()

    async def pause(self):
        self._voice.pause()

    async def resume(self):
        self._voice.resume()

    async def skip(self):
        self._voice.stop()
        self._current = None

    async def shuffle(self):
        random.shuffle(self._queue)


@app_commands.guild_only()
class Music(commands.GroupCog, group_name='music'):
    def __init__(self, bot):
        self.bot = bot
        self._query = list()
        self._radio_stations = {
            "маруся": "http://radio-holding.ru:9000/marusya_default",
        }
        self._players = dict()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        if before.channel is None:
            return
        if member.guild.get_member(self.bot.user.id).voice is None:
            return
        if (before.channel == member.guild.get_member(self.bot.user.id).voice.channel) and (
                (after.channel is None) or (after.channel != before.channel)) and len(
            member.guild.get_member(self.bot.user.id).voice.channel.members) == 1:
            await member.guild.change_voice_state(channel=None)

    async def _youtube_search(self, query: str):
        pass

    async def _join(self, interaction, voice_channel):
        """Joins a voice channel"""
        if not voice_channel:
            embed = discord.Embed(title="Ты не в канале", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(voice_channel)
        else:
            await voice_channel.connect()
        return interaction.guild.voice_client

    @app_commands.command(
        name="play",
        description="Добавить музыку в плейлист",
    )
    @app_commands.describe(
        url="Ссылка на видео youtube"
    )
    async def play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=False, thinking=True)
        # создание экзекутора
        executor = ThreadPoolExecutor()
        # проверка на наличие бота в канале
        if interaction.guild.voice_client is None:
            voice = await self._join(interaction, interaction.user.voice.channel)
        # проверка наличия плеера
        if interaction.guild.id not in self._players:
            self._players[interaction.guild.id] = Player()
        # проверка на наличие песни в очереди
        if self._players[interaction.guild.id].is_empty():
            self._players[interaction.guild.id].voice = interaction.guild.voice_client
        # добавление песни в очередь
        self._players[interaction.guild.id].add(await YTDLSource.from_url(url, loop=self.bot.loop))
        # запуск плеера
        if not interaction.guild.voice_client.is_playing():
            # запустить плеер и не дожидаться выполнения
            asyncio.run_coroutine_threadsafe(self._players[interaction.guild.id].play(), self.bot.loop)
        # отправка сообщения
        embed = discord.Embed(title="Добавлено в очередь", description=f"{url}", color=discord.Color.green())
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="skip",
        description="Пропустить текущую песню"
    )
    async def skip(self, interaction: discord.Interaction):
        if interaction.guild.id not in self._players.keys():
            embed = discord.Embed(title="Плеер не запущен", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await self._players[interaction.guild.id].skip()
            embed = discord.Embed(title="Пропущено", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="stop",
        description="Остановить плеер"
    )
    async def stop(self, interaction: discord.Interaction):
        if interaction.guild.id not in self._players.keys():
            embed = discord.Embed(title="Плеер не запущен", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await self._players[interaction.guild.id].stop()
            embed = discord.Embed(title="Остановлено", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="pause",
        description="Поставить на паузу"
    )
    async def pause(self, interaction: discord.Interaction):
        if interaction.guild.id not in self._players.keys():
            embed = discord.Embed(title="Плеер не запущен", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await self._players[interaction.guild.id].pause()
            embed = discord.Embed(title="Поставлено на паузу", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="resume",
        description="Продолжить воспроизведение"
    )
    async def resume(self, interaction: discord.Interaction):
        if interaction.guild.id not in self._players.keys():
            embed = discord.Embed(title="Плеер не запущен", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await self._players[interaction.guild.id].resume()
            embed = discord.Embed(title="Продолжено", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="clear",
        description="Очистить очередь"
    )
    async def clear(self, interaction: discord.Interaction):
        if interaction.guild.id not in self._players.keys():
            embed = discord.Embed(title="Плеер не запущен", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            self._players[interaction.guild.id].clear()
            embed = discord.Embed(title="Очередь очищена", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="queue",
        description="Показать очередь"
    )
    async def queue(self, interaction: discord.Interaction):
        if interaction.guild.id not in self._players.keys():
            embed = discord.Embed(title="Плеер не запущен", color=discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # пагинация
            paginator = commands.Paginator(prefix="", suffix="")
            # получение очереди
            queue = self._players[interaction.guild.id].queue
            # добавление очереди в пагинацию
            for i, song in enumerate(queue):
                paginator.add_line(f"{i + 1}. {song.title}")
            # отправка сообщений
            for page in paginator.pages:
                embed = discord.Embed(title="Очередь", description=page, color=discord.Color.green())
                await interaction.response.send_message(embed=embed, ephemeral=True)
