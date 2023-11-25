import asyncio
import logging
import os
from typing import Dict

import discord
import wavelink
from discord import app_commands
from discord.ext import commands
from youtube_search import YoutubeSearch

from models.bot import FununaNun
from utils import seconds_to_duration
from views import SearchTrack

logger = logging.getLogger("bot")

LAVALINK_HOST = os.environ.get("LAVALINK_HOST")
LAVALINK_PORT = int(os.environ.get("LAVALINK_PORT"))
LAVALINK_PASSWORD = os.environ.get("LAVALINK_PASSWORD")


@app_commands.guild_only()
class Music(commands.GroupCog, group_name='music'):
    def __init__(self, bot: FununaNun):
        self.bot = bot
        self.announce_channels: Dict[int, int] = dict()

    async def cog_load(self):
        await self.connect_node()

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

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        logger.info(f"Node {node.id=} is ready! ({node.uri=})")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackEventPayload):
        channel = await self.bot.fetch_channel(self.announce_channels.get(payload.player.guild.id))
        if channel is None:
            return

        embed = discord.Embed(
            title="Сейчас играет",
            description=f"{payload.track.title}",
            color=discord.Color.green()
        )
        embed.add_field(
            value=f"Продолжительность: {seconds_to_duration(payload.track.length // 1000)}",
            name=f"Ссылка: {payload.track.uri}"
        )
        await channel.send(embed=embed)

    async def connect_node(self):
        logger.info("Connecting to Lavalink...")
        node = wavelink.Node(uri=f'http://{LAVALINK_HOST}:{LAVALINK_PORT}', password=LAVALINK_PASSWORD)
        await wavelink.NodePool.connect(client=self.bot, nodes=[node])
        logger.info("Connected to Lavalink!")

    @staticmethod
    async def _join(interaction: discord.Interaction) -> wavelink.Player:
        if not interaction.user.voice:
            embed = discord.Embed(title="Ты не в канале", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        if interaction.guild.voice_client and interaction.user.voice.channel != interaction.guild.voice_client.channel:
            await interaction.user.voice.channel.connect(cls=wavelink.Player)
        elif not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect(cls=wavelink.Player)
        return interaction.guild.voice_client

    @app_commands.command(
        name="play",
        description="Добавить музыку в плейлист",
    )
    @app_commands.describe(
        query="Поисковой запрос"
    )
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(ephemeral=False, thinking=True)
        tracks = await wavelink.YouTubeTrack.search(query)
        tracks = tracks[:5]
        if not tracks:
            embed = discord.Embed(title="Ничего не найдено", color=discord.Color.red())
            await interaction.followup.send(embed=embed)
            return
        voice_client = await self._join(interaction)
        voice_client.autoplay = True
        self.announce_channels[voice_client.guild.id] = interaction.channel.id
        embed = discord.Embed(
            title="Музыка по запросу",
            description=f"{query}",
            color=discord.Color.blurple()
        )
        for index, track in enumerate(tracks):
            embed.add_field(
                name=f"{index + 1}. {track.title}",
                value=f"Канал: **{track.author}**\nПродолжительность: {seconds_to_duration(track.duration // 1000)}",
                inline=False
            )
        view = SearchTrack(interaction, voice_client, tracks)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(
        name="stop",
        description="Остановить музыку",
    )
    async def stop(self, interaction: discord.Interaction):
        voice_client: wavelink.Player = interaction.guild.voice_client
        if voice_client.is_playing():
            await voice_client.stop()
            voice_client.queue.reset()
        embed = discord.Embed(title="Музыка остановлена", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name='volume',
        description='Установить громкость',
    )
    @app_commands.describe(
        volume='Уровень громкости'
    )
    async def volume(self, interaction: discord.Interaction, volume: app_commands.Range[int, 0, 1000]):
        voice_client: wavelink.Player = interaction.guild.voice_client
        if voice_client.is_playing():
            await voice_client.set_volume(volume)
            embed = discord.Embed(
                title="Громкость установлена",
                description=f"Громкость: {volume}",
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
        voice_client: wavelink.Player = interaction.guild.voice_client
        if voice_client.is_playing():
            await voice_client.pause()
        if not voice_client.queue.is_empty:
            await voice_client.play(await voice_client.queue.get_wait())
            embed = discord.Embed(title="Музыка пропущена", color=discord.Color.green())
        else:
            embed = discord.Embed(title="Музыка закончилась", color=discord.Color.red())
        await interaction.followup.send(embed=embed)
        message = await interaction.followup.send(embed=embed, wait=True)
        await asyncio.sleep(5)
        await message.delete()

    @app_commands.command(
        name='loop',
        description='Зациклить музыку',
    )
    @app_commands.rename(all_tracks="all")
    @app_commands.describe(all_tracks="Зациклить все треки")
    async def loop(self, interaction: discord.Interaction, all_tracks: bool = False):
        voice_client: wavelink.Player = interaction.guild.voice_client
        if not voice_client.queue.is_empty or voice_client.is_playing():
            embed_title = ''
            match all_tracks:
                case True:
                    embed_title = 'Повтор плейлиста отключен' if voice_client.queue.loop_all else 'Плейлист будет повторяться'
                    voice_client.queue.loop_all = not voice_client.queue.loop_all
                case False:
                    embed_title = 'Повтор трека отключен' if voice_client.queue.loop else 'Трек будет повторяться'
                    voice_client.queue.loop = not voice_client.queue.loop
            embed = discord.Embed(title=embed_title, color=discord.Color.blurple())
        else:
            embed = discord.Embed(title="Плейлист пуст", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, delete_after=5)


async def setup(bot):
    await bot.add_cog(Music(bot))
