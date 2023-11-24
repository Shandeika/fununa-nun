import asyncio
import logging
import random
from typing import List

import discord
from discord import app_commands
from discord.ext import commands
from pydub import AudioSegment
from youtube_search import YoutubeSearch

from custom_dataclasses import Track
from utils import get_info_yt
from views import PlaylistView, YouTubeSearch
from ytdl import ytdl, ffmpeg_options

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
    async def from_track_obj(cls, track: Track, loop=None):
        stream = False
        loop = loop or asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: ytdl.download([track.original_url]))

        filename = track.raw_data['url'] if stream else ytdl.prepare_filename(track.raw_data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=track.raw_data)


class NoMusicInQueue(Exception):
    pass


class MusicPlayer:
    def __init__(self, join_func, play_func):
        self._join_fun = join_func
        self._play_fun = play_func
        self.queue: List[Track] = []
        self.current = None

    def add(self, track: Track):
        self.queue.append(track)
        return track

    def remove(self, index):
        return self.queue.pop(index)

    def clear(self):
        self.queue.clear()

    def shuffle(self):
        random.shuffle(self.queue)

    async def start_play(self, interaction: discord.Interaction):
        await self._join_fun(interaction, interaction.user.voice.channel)
        await self._play_fun(interaction.guild.voice_client, interaction.channel)


@app_commands.guild_only()
class Music(commands.GroupCog, group_name='music'):
    def __init__(self, bot):
        self.bot = bot
        self.player = MusicPlayer(self._join, self.play_next)

    @commands.Cog.listener()
    async def on_voice_state_update(self,
                                    member: discord.Member,
                                    before: discord.VoiceState,
                                    after: discord.VoiceState):
        """Если в канале никого не осталось кроме бота, выйти из канала"""
        bot_user = member.guild.get_member(self.bot.user.id)
        # если до этого не было канала или бота нет в голосовом канале
        if before.channel is None or bot_user.voice is None:
            return
        user_voice_channel = bot_user.voice.channel
        # (если прошлый канал это канал бота) и (если текущий канал другой или None) и (количество участников в
        # канале == 1), то выйти
        if (before.channel == user_voice_channel
                and (after.channel is None or after.channel != before.channel)
                and len(user_voice_channel.members) == 1):
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
            embed = discord.Embed(title="Музыка закончилась", color=discord.Color.blurple())
            return await channel.send(embed=embed)
        source = await YTDLSource.from_track_obj(next_track, self.bot.loop)
        voice_client.play(source, after=lambda e: self.bot.loop.create_task(self.play_next(voice_client, channel)))
        embed = discord.Embed(title="Сейчас играет", description=f"{source.title}", color=discord.Color.blurple())
        await channel.send(embed=embed)

    @app_commands.command(
        name="play",
        description="Добавить музыку в плейлист",
    )
    @app_commands.describe(
        url="Ссылка на видео youtube"
    )
    async def play(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=False, thinking=True)
        track = await get_info_yt(url)
        self.player.add(track)
        voice_client = await self._join(interaction, interaction.user.voice.channel)
        if not voice_client.is_playing():
            await self.play_next(voice_client, interaction.channel)
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
        description='Установить усиление звука',
    )
    @app_commands.describe(
        gain='Усиление громкости'
    )
    async def gain(self, interaction: discord.Interaction, gain: app_commands.Range[int, -100, 100]):
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.source.volume = gain
            embed = discord.Embed(
                title="Усиление установлено",
                description=f"{'+' if gain > 0 else str()}{gain} ДБ",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(title="Музыка не играет", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, delete_after=5)

    @app_commands.command(
        name='skip',
        description='Пропустить музыку',
    )
    async def skip(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False, thinking=True)
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.pause()
        await self.play_next(interaction.guild.voice_client, interaction.channel)
        embed = discord.Embed(title="Музыка пропущена", color=discord.Color.green())
        message = await interaction.followup.send(embed=embed, wait=True)
        await asyncio.sleep(5)
        await message.delete()

    @app_commands.command(
        name='playlist',
        description='Показать плейлист',
    )
    async def playlist(self, interaction: discord.Interaction):
        playlist = self.player.queue
        view = PlaylistView(interaction, playlist)
        embed = discord.Embed(title="Плейлист", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()
        await view.update_embed()

    @app_commands.command(
        name='youtube',
        description='Поиск видео в youtube',
    )
    @app_commands.describe(
        query='Поисковой запрос'
    )
    async def youtube(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(ephemeral=False, thinking=True)
        results = YoutubeSearch(query, max_results=5).to_dict()
        view = YouTubeSearch(interaction, results, self.player)
        await view.update_buttons()
        embed = discord.Embed(title="YouTube", color=discord.Color.green())
        for index, result in enumerate(results):
            embed.add_field(
                name=f"{index + 1}. {result['title']}",
                value=f"Канал: **{result['channel']}**\n"
                      f"Продолжительность: {result['duration']}\n"
                      f"Просмотры: {result['views']}",
                inline=False)
        await interaction.followup.send(embed=embed, view=view)


