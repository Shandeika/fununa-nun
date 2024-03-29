import asyncio
from typing import Dict

import discord
import wavelink
from discord.ext import commands, pages, tasks

from bot.models import FununaNun, BasicCog
from bot.models.errors import MemberNotInVoice, BotNotInVoice
from bot.views import SearchTrack, CurrentTrack
from utils import seconds_to_duration, send_temporary_message, set_voice_status


class Music(BasicCog):
    def __init__(self, bot: FununaNun):
        super().__init__(bot)
        self.announce_channels: Dict[int, int] = dict()
        self.announce_messages: Dict[int, int] = dict()
        self.announce_deleter.start()

    @tasks.loop(minutes=5)
    async def announce_deleter(self):
        """Удаляет записи из announce_channels и announce_messages, если они не используются"""
        announce_channels = self.announce_channels.copy()
        announce_messages = self.announce_messages.copy()
        for guild_id in self.announce_channels.keys():
            guild = await self.bot.fetch_guild(guild_id)
            if not guild.voice_client:
                self._logger.info(f"Deleting announce rows for {guild_id}")
                announce_channels.pop(guild_id)
                announce_messages.pop(guild_id)

        self.announce_messages = announce_messages
        self.announce_channels = announce_channels

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
            player.queue.clear()
            player.queue.history.clear()
            player.autoplay = wavelink.AutoPlayMode.disabled
            if player.playing:
                await player.stop(force=True)

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        self._logger.info(f"Player {player.guild.id} is inactive")
        player.queue.clear()
        player.queue.history.clear()
        player.autoplay = wavelink.AutoPlayMode.disabled
        await player.set_filters()
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
            self._logger.info("wavelink start: Announce channel not found")
            return

        message = await channel.fetch_message(
            self.announce_messages.get(payload.player.guild.id)
        )
        if not message:
            self._logger.info("wavelink start: Announce message not found")
            return

        view = CurrentTrack(payload.player)
        embed = await view.generate_embed()
        view.message = message
        await message.edit(embed=embed, view=view)
        await set_voice_status(
            payload.player.channel.id,
            self.bot,
            f"{payload.player.current.title} - {payload.player.current.author}"[:100],
        )

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        channel = await self.bot.fetch_channel(
            self.announce_channels.get(payload.player.guild.id)
        )
        if channel is None:
            self._logger.info("wavelink end: Announce channel not found")
            return
        message = await channel.fetch_message(
            self.announce_messages.get(payload.player.guild.id)
        )
        if not message:
            self._logger.info("wavelink end: Announce message not found")
            return
        if not len(payload.player.queue) and not payload.player.current:
            embed = discord.Embed(
                title="Музыка закончилась", color=discord.Color.blurple()
            )
            await message.edit(embed=embed, view=None)
            await set_voice_status(payload.player.channel.id, self.bot)

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
            tracks.track_extras(requester=ctx.user.id)
            await voice_client.queue.put_wait(tracks)
            embed = discord.Embed(
                title="Плейлист добавлен в очередь",
                description=f"Добавлено {len(tracks.tracks)} треков",
                color=discord.Color.green(),
            )
            await send_temporary_message(ctx, embed)
        elif len(tracks) == 1:
            tracks[0].extras = {"requester": ctx.user.id}
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
            embed = discord.Embed(
                title="Музыка скоро начнется",
                colour=discord.Color.blurple(),
            )
            message = await ctx.channel.send(embed=embed)
            self.announce_messages[ctx.guild.id] = message.id
            await voice_client.play(await voice_client.queue.get_wait())

    @discord.application_command(
        name="stop",
        description="Остановить музыку",
    )
    @discord.guild_only()
    async def stop(self, ctx: discord.ApplicationContext):
        voice_client = await self._get_voice(ctx.user, ctx.guild, join=False)
        voice_client.queue.clear()
        voice_client.queue.history.clear()
        voice_client.autoplay = wavelink.AutoPlayMode.disabled
        if voice_client.playing:
            await voice_client.stop(force=True)
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
            queue_pages = generate_queue_pages(voice_client)
            default_buttons = [
                pages.PaginatorButton(
                    "first",
                    label="<<",
                    style=discord.ButtonStyle.blurple,
                    row=0,
                ),
                pages.PaginatorButton(
                    "prev",
                    label="<",
                    style=discord.ButtonStyle.red,
                    loop_label="↪",
                    row=0,
                ),
                pages.PaginatorButton(
                    "page_indicator",
                    style=discord.ButtonStyle.gray,
                    disabled=True,
                    row=0,
                ),
                pages.PaginatorButton(
                    "next",
                    label=">",
                    style=discord.ButtonStyle.green,
                    loop_label="↩",
                    row=0,
                ),
                pages.PaginatorButton(
                    "last",
                    label=">>",
                    style=discord.ButtonStyle.blurple,
                    row=0,
                ),
                CloseButton(),
            ]
            paginator = pages.Paginator(
                pages=queue_pages,
                custom_buttons=default_buttons,
                use_default_buttons=False,
            )
            await paginator.respond(interaction=ctx.interaction)
            previous_tracks = None
            while not paginator.is_finished():
                current_tracks = voice_client.queue.copy()
                # Check if the queue or the current song has changed
                if current_tracks != previous_tracks:
                    queue_pages = generate_queue_pages(voice_client)
                    try:
                        if len(voice_client.queue) >= 1:
                            await paginator.update(
                                pages=queue_pages,
                                custom_buttons=default_buttons,
                                use_default_buttons=False,
                            )
                        else:
                            embed = discord.Embed(
                                title="Очередь пуста", color=discord.Color.red()
                            )
                            await paginator.update(
                                pages=[embed],
                                custom_buttons=default_buttons,
                                use_default_buttons=False,
                            )
                    except:
                        paginator.stop()
                    previous_tracks = current_tracks
                await asyncio.sleep(5)
        else:
            embed = discord.Embed(title="Очередь пуста", color=discord.Color.red())
            await ctx.response.send_message(embed=embed)


def generate_queue_pages(voice_client: wavelink.Player):
    queue_pages = []
    tracks = voice_client.queue
    for i in range(0, len(tracks), 5):
        page = tracks[i : i + 5]
        if voice_client.current:
            description = (
                f"**Сейчас играет**\n"
                f"Название: **{voice_client.current.title}**\n"
                f"Автор: **{voice_client.current.author}**\n"
                f"Продолжительность: **{seconds_to_duration(voice_client.current.length // 1000)}**"
            )
        else:
            description = "Сейчас ничего не играет"
        embed = discord.Embed(
            title="Очередь треков",
            description=description,
            color=discord.Color.blurple(),
        )
        embed.set_image(
            url="https://assets.shandy-dev.ru/playlist_fununa-nun_banner.webp"
        )
        embed.set_footer(text=f"Всего треков в очереди: {len(tracks)}")
        for index, track in enumerate(page):
            embed.add_field(
                name=f"Трек {voice_client.queue.index(track) + 1}",
                value=f"Название: **{track.title}**\nАвтор: **{track.author}**\nПродолжительность: **{seconds_to_duration(track.length // 1000)}**",
                inline=False,
            )
        queue_pages.append(embed)

    return queue_pages


class CloseButton(pages.PaginatorButton):
    def __init__(self):
        super().__init__(
            button_type="close", label="Закрыть", style=discord.ButtonStyle.red, row=1
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.delete_original_response()


def setup(bot):
    bot.add_cog(Music(bot))
