import asyncio

import discord.ui
import wavelink

from utils import seconds_to_duration


class CurrentTrack(discord.ui.View):
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=None)
        self.player = player

        self.setup_buttons()

        # history_track_index = self.player.queue.history._queue.index(
        #     self.player.current
        # )
        # is_previous_track_available = history_track_index > 0
        # is_next_track_available = self.player.queue[0]
        #
        # self.add_item(PreviousTrackButton(self.player, not is_previous_track_available))
        # # self.add_item(PreviousTrackButton(self.player, True))
        # self.add_item(PlayPauseButton(self.player))
        # self.add_item(NextTrackButton(self.player, not is_next_track_available))

        self.embed = None

    def setup_buttons(self):
        history_track_index = self.player.queue.history._queue.index(
            self.player.current
        )
        is_previous_track_available = history_track_index > 0
        is_next_track_available = self.player.queue[0]

        buttons_rows = [
            [
                PreviousTrackButton(self.player, not is_previous_track_available),
                PlayPauseButton(self.player),
                NextTrackButton(self.player, not is_next_track_available),
            ],
            [
                BackwardButton(self.player),
                StopButton(self.player),
                ForwardButton(self.player),
            ],
        ]

        for i, button_row in enumerate(buttons_rows):
            for button in button_row:
                button.row = i
                self.add_item(button)

    async def update_buttons(self):
        # history_track_index = self.player.queue.history._queue.index(
        #     self.player.current
        # )
        # is_previous_track_available = history_track_index > 0
        # is_next_track_available = history_track_index < len(
        #     self.player.queue.history._queue
        # )
        self.clear_items()
        self.setup_buttons()
        # self.add_item(PreviousTrackButton(self.player, not is_previous_track_available))
        # # self.add_item(PreviousTrackButton(self.player, True))
        # self.add_item(PlayPauseButton(self.player))
        # self.add_item(NextTrackButton(self.player, not is_next_track_available))
        await self.message.edit(view=self)

    def generate_embed(self):
        while not self.player.current:
            i = 0
            asyncio.sleep(0.1)
            i += 1
            if i == 10:
                break
        embed = discord.Embed(
            title="Сейчас играет",
            description=f"{self.player.current.title}\nАвтор: {self.player.current.author}",
            color=discord.Color.green(),
        )
        embed.add_field(
            value=f"Продолжительность: {seconds_to_duration(self.player.current.length // 1000)}",
            name=f"Ссылка: {self.player.current.uri}",
        )
        if self.player.current.artwork:
            embed.set_thumbnail(url=self.player.current.artwork)
        elif self.player.current.preview_url:
            embed.set_thumbnail(url=self.player.current.preview_url)
        if self.player.current.album and self.player.current.album.name:
            embed.add_field(
                name="Альбом",
                value=f"{self.player.current.album.name}\n{self.player.current.album.url}",
            )
        if self.player.current and self.player.current.recommended:
            embed.set_footer(text="Трек из рекомендаций")

        return embed

    async def update_embed(self):
        self.embed = self.generate_embed()
        await self.message.edit(embed=self.embed, view=self)


class PreviousTrackButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player, disabled: bool):
        super().__init__(
            # label="Предыдущий трек",
            style=discord.ButtonStyle.primary,
            emoji="⏪",
            disabled=disabled,
        )
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        # получить предыдущий трек из истории
        history_track_index = self.player.queue.history._queue.index(
            self.player.current
        )
        if history_track_index > 0:
            current_track = self.player.queue.history[history_track_index]
            previous_track = self.player.queue.history[history_track_index - 1]
            # await self.player.queue.put_wait(current_track)
            # await self.player.queue.put_wait(previous_track)
            self.player.queue._queue.appendleft(current_track)
            self.player.queue._queue.appendleft(previous_track)
            # await self.player.queue.history.delete(0)
            # await self.player.queue.history.delete(0)
            await self.player.skip()
            await self.view.update_embed()
            await self.view.update_buttons()
            embed = discord.Embed(title="Предыдущий трек", color=discord.Color.green())
            return await interaction.response.send_message(
                embed=embed, ephemeral=True, delete_after=0.1
            )
        else:
            embed = discord.Embed(
                title="Нет предыдущего трека", color=discord.Color.red()
            )
            return await interaction.response.send_message(
                embed=embed, ephemeral=True, delete_after=5
            )


class NextTrackButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player, disabled):
        super().__init__(
            # label="Следующий трек",
            style=discord.ButtonStyle.primary,
            emoji="⏩",
            disabled=disabled,
        )
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        try:
            await self.player.play(self.player.queue.get())
            await self.view.update_embed()
            await self.view.update_buttons()
            embed = discord.Embed(title="Следующий трек", color=discord.Color.green())
            return await interaction.response.send_message(
                embed=embed, ephemeral=True, delete_after=0.1
            )
        except wavelink.QueueEmpty:
            embed = discord.Embed(
                title="Нет следующего трека", color=discord.Color.green()
            )
            await self.view.update_embed()
            await self.view.update_buttons()
            return await interaction.response.send_message(
                embed=embed, ephemeral=True, delete_after=0.1
            )


class PlayPauseButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player):
        self.player = player
        if self.player.paused:
            super().__init__(
                # label="Возобновить",
                style=discord.ButtonStyle.primary,
                emoji="▶",
            )
        else:
            super().__init__(
                # label="Пауза",
                style=discord.ButtonStyle.primary,
                emoji="⏸",
            )

    async def callback(self, interaction: discord.Interaction):
        if self.player.paused:
            await self.player.pause(not self.player.paused)
            embed = discord.Embed(
                title="Музыка возобновлена", color=discord.Color.green()
            )
        else:
            await self.player.pause(not self.player.paused)
            embed = discord.Embed(
                title="Музыка приостановлена", color=discord.Color.green()
            )
        await self.view.update_buttons()
        await self.view.update_embed()
        return await interaction.response.send_message(
            embed=embed, ephemeral=True, delete_after=0.1
        )


class StopButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player):
        self.player = player
        super().__init__(
            # label="Остановить",
            style=discord.ButtonStyle.danger,
            emoji="⏹",
        )

    async def callback(self, interaction: discord.Interaction):
        self.player.queue.mode = wavelink.QueueMode.normal
        self.player.queue.clear()
        await self.player.stop()
        embed = discord.Embed(title="Музыка остановлена", color=discord.Color.green())
        return await interaction.response.send_message(
            embed=embed, ephemeral=True, delete_after=0.1
        )


class BackwardButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player):
        super().__init__(
            # label="Назад",
            style=discord.ButtonStyle.primary,
            emoji="↪",
        )
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        if not self.player.current.is_seekable:
            embed = discord.Embed(
                title="Трек не может быть перемотан", color=discord.Color.red()
            )
            return await interaction.response.send_message(
                embed=embed, ephemeral=True, delete_after=0.1
            )
        current_position = self.player.position
        if current_position > 10 * 1000:
            await self.player.seek(current_position - (10 * 1000))
        else:
            await self.player.seek(0)
        embed = discord.Embed(
            title="Трек перемотан на 10 секунд назад", color=discord.Color.green()
        )
        return await interaction.response.send_message(
            embed=embed, ephemeral=True, delete_after=0.1
        )


class ForwardButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player):
        super().__init__(
            # label="Вперед",
            style=discord.ButtonStyle.primary,
            emoji="↩",
        )
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        if not self.player.current.is_seekable:
            embed = discord.Embed(
                title="Трек не может быть перемотан", color=discord.Color.red()
            )
            return await interaction.response.send_message(
                embed=embed, ephemeral=True, delete_after=0.1
            )
        current_position = self.player.position
        await self.player.seek(current_position + (10 * 1000))
        embed = discord.Embed(
            title="Трек перемотан на 10 секунд вперед", color=discord.Color.green()
        )
        return await interaction.response.send_message(
            embed=embed, ephemeral=True, delete_after=0.1
        )
