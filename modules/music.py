import asyncio
import dataclasses
import logging
import random

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands
from pydub import AudioSegment

yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': 'music_files/%(extractor)s-%(id)s-%(title)s.%(ext)s',
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
ytdl.cache.remove()

logger = logging.getLogger("bot")


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    def read(self) -> bytes:
        ret = self.original.read()
        audio_segment = AudioSegment(ret, sample_width=2, frame_rate=48000, channels=2)

        audio_segment = audio_segment.apply_gain(self._volume)

        ret = audio_segment.raw_data

        return ret

    @classmethod
    async def from_url(cls, url, *, loop=None):
        stream = False
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class NoMusicInQueue(Exception):
    pass


class MusicPlayer:
    def __init__(self):
        self.queue = []
        self.current = None

    @staticmethod
    async def create_from_url(url) -> YTDLSource:
        return await YTDLSource.from_url(url)

    def add(self, url):
        self.queue.append(url)

    def remove(self, index):
        return self.queue.pop(index)

    def clear(self):
        self.queue.clear()

    def shuffle(self):
        random.shuffle(self.queue)


@dataclasses.dataclass
class Track:
    title: str
    url: str
    duration: float
    image_url: str

    def duration_to_time(self):
        # Перевести секунды во время часы:минуты:секунды. Если единица времени меньше 0, то не добавлять ее
        hours = self.duration // 3600
        minutes = (self.duration % 3600) // 60
        seconds = self.duration % 60

        time_str = ""
        if hours > 0:
            time_str += f"{hours}:"
        if minutes > 0 or hours > 0:
            time_str += f"{minutes:02d}:"
        time_str += f"{seconds:02d}"

        return time_str



@app_commands.guild_only()
class Music(commands.GroupCog, group_name='music'):
    def __init__(self, bot):
        self.bot = bot
        self.player = MusicPlayer()

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

    async def play_next(self, voice_client: discord.VoiceClient, channel: discord.TextChannel):
        try:
            next_track = self.player.remove(0)
        except IndexError:
            await voice_client.disconnect()
            return
        source = await YTDLSource.from_url(next_track)
        voice_client.play(source, after=lambda e: self.bot.loop.create_task(self.play_next(voice_client, channel)))
        embed = discord.Embed(title="Сейчас играет", description=f"{source.title}", color=discord.Color.blurple())
        await channel.send(embed=embed)

    async def get_info_yt(self, url: str) -> Track:
        loop = self.bot.loop
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
        track = Track(
            title=data.get('title'),
            url=data.get('url'),
            duration=data.get('duration'),
            image_url=data.get('thumbnail')
        )
        return track

    @app_commands.command(
        name="play",
        description="Добавить музыку в плейлист",
    )
    @app_commands.describe(
        url="Ссылка на видео youtube"
    )
    async def play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=False, thinking=True)
        self.player.add(url)
        voice_client = await self._join(interaction, interaction.user.voice.channel)
        if not voice_client.is_playing():
            await self.play_next(voice_client, interaction.channel)
        track = await self.get_info_yt(url)
        embed = discord.Embed(title="Добавлено в очередь", description=f"{track.title}", color=discord.Color.green())
        embed.add_field(name="Продолжительность", value=f"{track.duration_to_time()}")
        embed.add_field(name="Ссылка", value=f"{url}", inline=False)
        embed.set_thumbnail(url=track.image_url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="stop",
        description="Остановить музыку",
    )
    async def stop(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.stop()
        embed = discord.Embed(title="Музыка остановлена", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name='volume',
        description='Установить громкость',
    )
    @app_commands.describe(
        volume='Уровень громкости'
    )
    async def volume(self, interaction: discord.Interaction, volume: int):
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.source.volume = volume / 100
            embed = discord.Embed(title="Громкость установлена", description=f"{volume}", color=discord.Color.green())
        else:
            embed = discord.Embed(title="Музыка не играет", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name='skip',
        description='Пропустить музыку',
    )
    async def skip(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.pause()
        await self.play_next(interaction.guild.voice_client, interaction.channel)
        embed = discord.Embed(title="Музыка пропущена", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
