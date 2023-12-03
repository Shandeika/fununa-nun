import asyncio
import logging
from typing import Dict

import discord
import wavelink
from discord.ext import commands

from models.bot import FununaNun
from models.queue_paginator import QueuePaginator
from utils import seconds_to_duration
from views import SearchTrack

logger = logging.getLogger("bot")


class Music(commands.Cog):
    def __init__(self, bot: FununaNun):
        self.bot = bot
        self.announce_channels: Dict[int, int] = dict()

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
    async def on_wavelink_node_ready(self, node: wavelink.NodeReadyEventPayload):
        logger.info(f"Node {node.node.identifier} is ready! ({node.node.uri})")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        channel = await self.bot.fetch_channel(self.announce_channels.get(payload.player.guild.id))
        if channel is None:
            return

        embed = discord.Embed(
            title="Сейчас играет",
            description=f"{payload.track.title}\nАвтор: {payload.track.author}",
            color=discord.Color.green()
        )
        embed.add_field(
            value=f"Продолжительность: {seconds_to_duration(payload.track.length // 1000)}",
            name=f"Ссылка: {payload.track.uri}"
        )
        if payload.track.artwork:
            embed.set_thumbnail(url=payload.track.artwork)
        elif payload.track.preview_url:
            embed.set_thumbnail(url=payload.track.preview_url)
        if payload.track.album and payload.track.album.name:
            embed.add_field(name="Альбом", value=f"{payload.track.album.name}\n{payload.track.album.url}")
        if payload.original and payload.original.recommended:
            embed.set_footer(text="Трек из рекомендаций")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        channel = await self.bot.fetch_channel(self.announce_channels.get(payload.player.guild.id))
        if channel is None:
            return
        if len(payload.player.queue) == 0 and not payload.player.current:
            embed = discord.Embed(
                title="Музыка закончилась",
                color=discord.Color.blurple()
            )
            await channel.send(embed=embed)

    async def _join(self, interaction: discord.Interaction) -> wavelink.Player:
        if not interaction.user.voice:
            embed = discord.Embed(title="Ты не в канале", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        if interaction.guild.voice_client and interaction.user.voice.channel != interaction.guild.voice_client.channel:
            await interaction.user.voice.channel.connect(cls=wavelink.Player)
        elif not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect(cls=wavelink.Player)
        self.announce_channels[interaction.guild.id] = interaction.channel.id
        return interaction.guild.voice_client

    @discord.application_command(
        name="play",
        description="Добавить музыку в плейлист",
    )
    @discord.option(name="query", description="Запрос", input_tupe=discord.SlashCommandOptionType.string, required=True)
    @discord.option(name="auto_play", description="Автоматически добавлять рекомендуемые треки",
                    input_tupe=discord.SlashCommandOptionType.boolean, required=False, default=True)
    @discord.option(
        name="provider",
        type=discord.SlashCommandOptionType.string,
        choices=[
            discord.OptionChoice("YouTube", "ytsearch"),
            discord.OptionChoice("Yandex Music", "ymsearch"),
        ],
        required=False,
        default="ytsearch",
    )
    async def play(
            self,
            ctx: discord.ApplicationContext,
            query: str,
            provider: str,
            auto_play: bool = True,
    ):
        await ctx.response.defer(ephemeral=False, invisible=True)
        tracks: wavelink.Search = await wavelink.Playable.search(query, source=provider)
        if isinstance(tracks, list):
            if not tracks:
                embed = discord.Embed(title="Ничего не найдено", color=discord.Color.red())
                await ctx.followup.send(embed=embed)
                return
            elif len(tracks) == 1:
                embed = discord.Embed(title="Трек добавлен в очередь", color=discord.Color.green())
                message = await ctx.followup.send(embed=embed, wait=True)
                voice_client = await self._join(ctx.interaction)
                if auto_play:
                    voice_client.autoplay = wavelink.AutoPlayMode.enabled
                else:
                    voice_client.autoplay = wavelink.AutoPlayMode.partial
                await voice_client.queue.put_wait(tracks[0])
                await asyncio.sleep(5)
                await message.delete()
                if not voice_client.playing:
                    await voice_client.play(await voice_client.queue.get_wait())
            voice_client = await self._join(ctx.interaction)
            if auto_play:
                voice_client.autoplay = wavelink.AutoPlayMode.enabled
            else:
                voice_client.autoplay = wavelink.AutoPlayMode.partial
            embed = discord.Embed(
                title=f"Музыка по запросу (поиск по {provider})",
                description=f"{query}",
                color=discord.Color.blurple()
            )
            tracks = tracks[:5]
            for index, track in enumerate(tracks):
                embed.add_field(
                    name=f"{index + 1}. {track.title}",
                    value=f"Канал: **{track.author}**\nПродолжительность: {seconds_to_duration(track.length // 1000)}",
                    inline=False
                )
            view = SearchTrack(ctx.interaction, voice_client, tracks)
            await ctx.followup.send(embed=embed, view=view)
        elif isinstance(tracks, wavelink.Playlist):
            embed = discord.Embed(
                title="Плейлист добавлен в очередь",
                description=f"Добавлено {len(tracks.tracks)} треков",
                color=discord.Color.green()
            )
            message = await ctx.followup.send(embed=embed, wait=True)
            voice_client = await self._join(ctx.interaction)
            if auto_play:
                voice_client.autoplay = wavelink.AutoPlayMode.enabled
            else:
                voice_client.autoplay = wavelink.AutoPlayMode.partial
            await voice_client.queue.put_wait(tracks)
            await asyncio.sleep(5)
            await message.delete()
            if not voice_client.playing:
                return await voice_client.play(await voice_client.queue.get_wait())

    @discord.application_command(
        name="stop",
        description="Остановить музыку",
    )
    async def stop(self, ctx: discord.ApplicationContext):
        voice_client: wavelink.Player = ctx.guild.voice_client
        voice_client.queue.clear()
        if voice_client.playing:
            await voice_client.stop(force=True)
        await voice_client.disconnect()
        embed = discord.Embed(title="Музыка остановлена", color=discord.Color.green())
        await ctx.response.send_message(embed=embed)

    @discord.application_command(
        name='volume',
        description='Установить громкость',
    )
    @discord.option(
        name='volume',
        description='Уровень громкости',
        min_value=0,
        max_value=1000,
        required=True
    )
    async def volume(self, ctx: discord.ApplicationContext, volume: int):
        voice_client: wavelink.Player = ctx.guild.voice_client
        if voice_client.current:
            await voice_client.set_volume(volume)
            embed = discord.Embed(
                title="Громкость установлена",
                description=f"Громкость: {volume}",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(title="Музыка не играет", color=discord.Color.red())
        await ctx.response.send_message(embed=embed, delete_after=5)

    @discord.application_command(
        name='skip',
        description='Пропустить музыку',
    )
    async def skip(self, ctx: discord.ApplicationContext):
        await ctx.response.defer(ephemeral=False, invisible=True)
        voice_client: wavelink.Player = ctx.guild.voice_client
        if voice_client.playing:
            await voice_client.skip(force=True)
            embed = discord.Embed(title="Музыка пропущена", color=discord.Color.green())
        else:
            embed = discord.Embed(title="Музыка закончилась", color=discord.Color.red())
        message = await ctx.followup.send(embed=embed, wait=True)
        await asyncio.sleep(5)
        await message.delete()

    @discord.application_command(
        name='loop',
        description='Зациклить музыку',
    )
    @discord.option(
        name="all",
        description="Зациклить все треки",
        required=False,
        default=False
    )
    async def loop(self, ctx: discord.ApplicationContext, all_tracks: bool = False):
        words = {
            0: "повтор выключен",
            1: "повтор трека",
            2: "повтор плейлиста"
        }
        voice_client: wavelink.Player = ctx.guild.voice_client
        if len(voice_client.queue) >= 1 and voice_client.current:
            current_mode = voice_client.queue.mode
            if all_tracks:
                new_mode = wavelink.QueueMode.normal if current_mode == wavelink.QueueMode.loop or current_mode == wavelink.QueueMode.loop_all else wavelink.QueueMode.loop_all
            else:
                new_mode = wavelink.QueueMode.normal if current_mode == wavelink.QueueMode.loop or current_mode == wavelink.QueueMode.loop_all else wavelink.QueueMode.loop
            voice_client.queue.mode = new_mode
            embed = discord.Embed(title=f"Текущий режим: {words[new_mode.value]}", color=discord.Color.blurple())
        else:
            embed = discord.Embed(title="Плейлист пуст", color=discord.Color.red())
        await ctx.response.send_message(embed=embed, delete_after=5)

    @discord.application_command(
        name='queue',
        description='Показать очередь треков',
    )
    async def queue(self, ctx: discord.ApplicationContext):
        voice_client: wavelink.Player = ctx.guild.voice_client
        paginator = QueuePaginator(player=voice_client)
        await paginator.update()
        await paginator.respond(interaction=ctx.interaction)


def setup(bot):
    bot.add_cog(Music(bot))
