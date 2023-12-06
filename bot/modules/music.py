from typing import Dict

import discord
import wavelink
from discord.ext import commands, pages

from bot.models import FununaNun, BasicCog
from bot.models.errors import MemberNotInVoice, BotNotInVoice
from bot.views import SearchTrack
from utils import seconds_to_duration, send_temporary_message


class Music(BasicCog):
    def __init__(self, bot: FununaNun):
        super().__init__(bot)
        self.announce_channels: Dict[int, int] = dict()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Если в канале никого не осталось кроме бота, выйти из канала"""
        bot_user = member.guild.get_member(self.bot.user.id)
        # если до этого не было канала или бота нет в голосовом канале
        if before.channel is None or bot_user.voice is None:
            return
        user_voice_channel = bot_user.voice.channel
        # (если прошлый канал это канал бота) и (если текущий канал другой или None) и (количество участников в
        # канале == 1), то выйти
        if (
            before.channel == user_voice_channel
            and (after.channel is None or after.channel != before.channel)
            and len(user_voice_channel.members) == 1
        ):
            player: wavelink.Player = member.guild.voice_client
            if player:
                player.queue.clear()
                if player.playing:
                    await player.stop(force=True)
                await player.disconnect()

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.NodeReadyEventPayload):
        self._logger.info(f"Node {node.node.identifier} is ready! ({node.node.uri})")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        channel = await self.bot.fetch_channel(
            self.announce_channels.get(payload.player.guild.id)
        )
        if channel is None:
            return

        embed = discord.Embed(
            title="Сейчас играет",
            description=f"{payload.track.title}\nАвтор: {payload.track.author}",
            color=discord.Color.green(),
        )
        embed.add_field(
            value=f"Продолжительность: {seconds_to_duration(payload.track.length // 1000)}",
            name=f"Ссылка: {payload.track.uri}",
        )
        if payload.track.artwork:
            embed.set_thumbnail(url=payload.track.artwork)
        elif payload.track.preview_url:
            embed.set_thumbnail(url=payload.track.preview_url)
        if payload.track.album and payload.track.album.name:
            embed.add_field(
                name="Альбом",
                value=f"{payload.track.album.name}\n{payload.track.album.url}",
            )
        if payload.original and payload.original.recommended:
            embed.set_footer(text="Трек из рекомендаций")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        channel = await self.bot.fetch_channel(
            self.announce_channels.get(payload.player.guild.id)
        )
        if channel is None:
            return
        if len(payload.player.queue) == 0 and not payload.player.current:
            embed = discord.Embed(
                title="Музыка закончилась", color=discord.Color.blurple()
            )
            await channel.send(embed=embed)

    async def _get_voice(
        self,
        member: discord.Member,
        guild: discord.Guild,
        join: bool = True,
        announce_channel: discord.TextChannel = None,
    ) -> wavelink.Player:
        """Возвращает плеер голосового канала, или ошибку, если пользователь не в канале и join = False

        :param interaction: Взаимодействие
        :param join: Входить ли в канал пользователя, по умолчанию True

        :raise modules.errors.NotInVoiceChannel: Если пользователь не в канале
        :return: wavelink.Player
        """
        voice = member.voice
        bot_voice = guild.voice_client
        if (
            not announce_channel
            and voice.channel.type == discord.ChannelType.stage_voice
        ):
            announce_channel = [
                channel
                for channel in guild.channels
                if channel.type == discord.ChannelType.text
            ][0]
        elif not announce_channel:
            announce_channel = voice.channel.id

        if not voice:
            raise MemberNotInVoice("The user is not in a voice channel")

        if not bot_voice:
            if join:
                await voice.channel.connect(cls=wavelink.Player)
                self.announce_channels[guild.id] = announce_channel.id
                return guild.voice_client
            else:
                raise BotNotInVoice(
                    "The bot is not in a voice channel and 'join' is set to False"
                )

        if voice.channel != bot_voice.channel:
            if join:
                await voice.channel.connect(cls=wavelink.Player)
                self.announce_channels[guild.id] = announce_channel.id
                return guild.voice_client
            else:
                raise MemberNotInVoice(
                    "The user and the bot are in different voice channels and 'join' is set to False"
                )

        return bot_voice

    @discord.application_command(
        name="play",
        description="Добавить музыку в плейлист",
    )
    @discord.option(
        name="query",
        description="Запрос",
        input_tupe=discord.SlashCommandOptionType.string,
        required=True,
    )
    @discord.option(
        name="auto_play",
        description="Автоматически добавлять рекомендуемые треки",
        input_tupe=discord.SlashCommandOptionType.boolean,
        required=False,
        default=True,
    )
    @discord.option(
        name="provider",
        type=discord.SlashCommandOptionType.string,
        choices=[
            discord.OptionChoice("YouTube", "ytsearch"),
            discord.OptionChoice("Yandex Music", "ymsearch"),
        ],
        required=False,
        default="ymsearch",
    )
    @discord.guild_only()
    async def play(
        self,
        ctx: discord.ApplicationContext,
        query: str,
        provider: str,
        auto_play: bool = True,
    ):
        await ctx.response.defer(ephemeral=False, invisible=True)

        tracks = await wavelink.Playable.search(query, source=provider)

        if not tracks:
            embed = discord.Embed(title="Ничего не найдено", color=discord.Color.red())
            await send_temporary_message(interaction=ctx, embed=embed)
            return

        voice_client = await self._get_voice(
            ctx.user, ctx.guild, announce_channel=ctx.channel
        )
        voice_client.autoplay = (
            wavelink.AutoPlayMode.enabled
            if auto_play
            else wavelink.AutoPlayMode.partial
        )

        if isinstance(tracks, wavelink.Playlist):
            await voice_client.queue.put_wait(tracks)
            embed = discord.Embed(
                title="Плейлист добавлен в очередь",
                description=f"Добавлено {len(tracks.tracks)} треков",
                color=discord.Color.green(),
            )
            await send_temporary_message(ctx, embed)
        elif len(tracks) == 1:
            await voice_client.queue.put_wait(tracks[0])
            embed = discord.Embed(
                title="Трек добавлен в очередь",
                description=f"Добавлен **{tracks[0].title}**",
                color=discord.Color.green(),
            )
            await send_temporary_message(ctx, embed)
        else:
            embed = discord.Embed(
                title=f"Музыка по запросу (поиск по {provider})",
                description=f"{query}",
                color=discord.Color.blurple(),
            )
            tracks = tracks[:5]
            for index, track in enumerate(tracks):
                embed.add_field(
                    name=f"{index + 1}. {track.title}",
                    value=f"Канал: **{track.author}**\nПродолжительность: {seconds_to_duration(track.length // 1000)}",
                    inline=False,
                )

            view = SearchTrack(ctx.interaction, voice_client, tracks)
            await ctx.followup.send(
                embed=embed,
                view=view,
            )

        if not voice_client.playing:
            await voice_client.play(await voice_client.queue.get_wait())

    @discord.application_command(
        name="stop",
        description="Остановить музыку",
    )
    @discord.guild_only()
    async def stop(self, ctx: discord.ApplicationContext):
        voice_client = await self._get_voice(ctx.user, ctx.guild, join=False)
        voice_client.queue.clear()
        if voice_client.playing:
            await voice_client.stop(force=True)
        await voice_client.disconnect()
        embed = discord.Embed(title="Музыка остановлена", color=discord.Color.green())
        await ctx.response.send_message(embed=embed)

    @discord.application_command(
        name="volume",
        description="Установить громкость",
    )
    @discord.option(
        name="volume",
        description="Уровень громкости",
        min_value=0,
        max_value=1000,
        required=True,
    )
    @discord.guild_only()
    async def volume(self, ctx: discord.ApplicationContext, volume: int):
        voice_client = await self._get_voice(ctx.user, ctx.guild, join=False)
        if voice_client.current:
            await voice_client.set_volume(volume)
            embed = discord.Embed(
                title="Громкость установлена",
                description=f"Громкость: {volume}",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(title="Музыка не играет", color=discord.Color.red())
        await ctx.response.send_message(embed=embed, delete_after=5)

    @discord.application_command(
        name="skip",
        description="Пропустить музыку",
    )
    @discord.guild_only()
    async def skip(self, ctx: discord.ApplicationContext):
        await ctx.response.defer(ephemeral=False, invisible=True)
        voice_client = await self._get_voice(ctx.user, ctx.guild, join=False)
        if voice_client.playing:
            await voice_client.skip(force=True)
            embed = discord.Embed(title="Музыка пропущена", color=discord.Color.green())
        else:
            embed = discord.Embed(title="Музыка закончилась", color=discord.Color.red())
        await send_temporary_message(ctx, embed)

    @discord.application_command(
        name="loop",
        description="Зациклить музыку",
    )
    @discord.option(
        name="all", description="Зациклить все треки", required=False, default=False
    )
    @discord.guild_only()
    async def loop(self, ctx: discord.ApplicationContext, all_tracks: bool = False):
        words = {0: "повтор выключен", 1: "повтор трека", 2: "повтор плейлиста"}
        voice_client = await self._get_voice(ctx.user, ctx.guild, join=False)
        if len(voice_client.queue) >= 1 and voice_client.current:
            current_mode = voice_client.queue.mode
            if all_tracks:
                new_mode = (
                    wavelink.QueueMode.normal
                    if current_mode == wavelink.QueueMode.loop
                    or current_mode == wavelink.QueueMode.loop_all
                    else wavelink.QueueMode.loop_all
                )
            else:
                new_mode = (
                    wavelink.QueueMode.normal
                    if current_mode == wavelink.QueueMode.loop
                    or current_mode == wavelink.QueueMode.loop_all
                    else wavelink.QueueMode.loop
                )
            voice_client.queue.mode = new_mode
            embed = discord.Embed(
                title=f"Текущий режим: {words[new_mode.value]}",
                color=discord.Color.blurple(),
            )
        else:
            embed = discord.Embed(title="Плейлист пуст", color=discord.Color.red())
        await ctx.response.send_message(embed=embed, delete_after=5)

    @discord.application_command(
        name="queue",
        description="Показать очередь треков",
    )
    @discord.guild_only()
    async def queue(self, ctx: discord.ApplicationContext):
        voice_client = await self._get_voice(ctx.user, ctx.guild, join=False)
        if len(voice_client.queue) >= 1:
            queue_pages = []
            tracks = voice_client.queue
            for i in range(0, len(tracks), 5):
                page = tracks[i : i + 5]
                embed = discord.Embed(
                    title="Очередь треков",
                    description=f"**Сейчас играет**\n"
                    f"Название: **{voice_client.current.title}**\n"
                    f"Автор: **{voice_client.current.author}**\n"
                    f"Продолжительность: **{seconds_to_duration(voice_client.current.length // 1000)}**",
                    color=discord.Color.blurple(),
                )
                embed.set_image(
                    url="https://assets.shandy-dev.ru/playlist_fununa-nun_banner.webp"
                )
                embed.set_footer(text=f"Всего треков в очереди: {len(tracks)}")
                for index, track in enumerate(page):
                    embed.add_field(
                        name=f"Трек {voice_client.queue._queue.index(track) + 1}",
                        value=f"Название: **{track.title}**\nАвтор: **{track.author}**\nПродолжительность: **{seconds_to_duration(track.length // 1000)}**",
                        inline=False,
                    )
                queue_pages.append(embed)
            paginator = pages.Paginator(pages=queue_pages)
            await paginator.respond(interaction=ctx.interaction)
        else:
            embed = discord.Embed(title="Очередь пуста", color=discord.Color.red())
            await ctx.response.send_message(embed=embed)


def setup(bot):
    bot.add_cog(Music(bot))
