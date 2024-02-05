import asyncio

import discord.ui
import wavelink

from utils import seconds_to_duration


class CurrentTrack(discord.ui.View):
    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=None)
        self.player = player
        self.setup_buttons()
        self.embed = None

    def setup_buttons(self):
        try:
            history_track_index = self.player.queue.history.index(self.player.current)
            is_previous_track_available = history_track_index > 0
        except ValueError:
            # Если текущий трек не найден в истории, предыдущий трек недоступен
            is_previous_track_available = False

        try:
            # Проверяем, есть ли следующий трек в очереди
            is_next_track_available = bool(self.player.queue[0])
        except IndexError:
            # Если следующий трек отсутствует в очереди, следующий трек недоступен
            is_next_track_available = False

        # если включен автоплей
        is_next_track_available = (
            is_next_track_available
            or self.player.autoplay == wavelink.AutoPlayMode.enabled
        )

        buttons_rows = [
            [
                PreviousTrackButton(self.player, not is_previous_track_available),
                PlayPauseButton(self.player),
                NextTrackButton(self.player, not is_next_track_available),
                VolumeUpButton(self.player),
                EqualizerPresetButton(self.player),
            ],
            [
                BackwardButton(self.player),
                ShuffleButton(self.player),
                ForwardButton(self.player),
                VolumeDownButton(self.player),
            ],
        ]

        for i, button_row in enumerate(buttons_rows):
            for button in button_row:
                button.row = i
                self.add_item(button)

    async def update_buttons(self):
        self.clear_items()
        self.setup_buttons()
        await self.message.edit(view=self)

    async def generate_embed(self):
        while not self.player.current:
            i = 0
            await asyncio.sleep(0.1)
            i += 1
            if i == 10:
                break
        embed = discord.Embed(
            title="Сейчас играет",
            description=f"{self.player.current.title}\nАвтор: {self.player.current.author}",
            color=discord.Color.green(),
        )
        if (
            hasattr(self.player.current.extras, "requester")
            and self.player.current.extras.requester
        ):
            requester = await self.player.client.fetch_user(
                self.player.current.extras.requester
            )
        elif (
            hasattr(self.player.current, "requester") and self.player.current.requester
        ):
            requester = await self.player.client.fetch_user(
                self.player.current.requester
            )
        else:
            requester = None
        if requester:
            embed.set_author(
                name=f"Запросил {requester.name}", icon_url=requester.display_avatar.url
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
        self.embed = await self.generate_embed()
        await self.message.edit(embed=self.embed, view=self)


class PreviousTrackButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player, disabled: bool):
        super().__init__(
            style=discord.ButtonStyle.primary,
            emoji="⏪",
            disabled=disabled,
        )
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        history_track_index = self.player.queue.history.index(self.player.current)
        if history_track_index > 0:
            current_track = self.player.queue.history[history_track_index]
            previous_track = self.player.queue.history[history_track_index - 1]
            self.player.queue.put_at(0, current_track)
            self.player.queue.put_at(0, previous_track)
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
            style=discord.ButtonStyle.primary,
            emoji="⏩",
            disabled=disabled,
        )
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        try:
            await self.player.skip(force=True)
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
                style=discord.ButtonStyle.primary,
                emoji="▶",
            )
        else:
            super().__init__(
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


class ShuffleButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player):
        self.player = player
        super().__init__(
            style=discord.ButtonStyle.primary,
            emoji="🔀",
        )

    async def callback(self, interaction: discord.Interaction):
        self.player.queue.shuffle()
        embed = discord.Embed(title="Очередь перемешана", color=discord.Color.green())
        return await interaction.response.send_message(
            embed=embed, ephemeral=True, delete_after=0.1
        )


class BackwardButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player):
        super().__init__(
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


class VolumeUpButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player):
        super().__init__(
            style=discord.ButtonStyle.primary,
            emoji="🔊",
        )
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        if self.player.volume >= 990:
            await self.player.set_volume(1000)
            embed = discord.Embed(
                title="Максимальная громкость установлена", color=discord.Color.red()
            )
            return await interaction.response.send_message(
                embed=embed, ephemeral=True, delete_after=0.1
            )
        await self.player.set_volume(self.player.volume + 10)
        embed = discord.Embed(
            title=f"Громкость увеличена до {self.player.volume}",
            color=discord.Color.green(),
        )
        return await interaction.response.send_message(
            embed=embed, ephemeral=True, delete_after=0.1
        )


class VolumeDownButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player):
        super().__init__(
            style=discord.ButtonStyle.primary,
            emoji="🔉",
        )
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        if self.player.volume <= 10:
            await self.player.set_volume(0)
            embed = discord.Embed(title="Звук выключен", color=discord.Color.green())
            return await interaction.response.send_message(
                embed=embed, ephemeral=True, delete_after=0.1
            )
        await self.player.set_volume(self.player.volume - 10)
        embed = discord.Embed(
            title=f"Громкость уменьшена до {self.player.volume}",
            color=discord.Color.green(),
        )
        return await interaction.response.send_message(
            embed=embed, ephemeral=True, delete_after=0.1
        )


class EqualizerPresetButton(discord.ui.Button):
    def __init__(self, player: wavelink.Player):
        super().__init__(
            style=discord.ButtonStyle.primary,
            emoji="🎶",
        )
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Выберите пресет", color=discord.Color.blurple())
        view = discord.ui.View(
            EqualizerPresetDropdown(self.player), disable_on_timeout=True
        )
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            view=view,
        )
        while not view.is_finished():
            await asyncio.sleep(0.1)
        await interaction.delete_original_response()


class EqualizerPresetDropdown(discord.ui.Select):
    def __init__(self, player: wavelink.Player):
        self.player = player
        self.equalizer_presets = [
            EqualizerPreset(
                name="Нормальный",
                emoji="🎛️",
                description="Без эффектов",
                bands_values={
                    0: 0.0,
                    1: 0.0,
                    2: 0.0,
                    3: 0.0,
                    4: 0.0,
                    5: 0.0,
                    6: 0.0,
                    7: 0.0,
                    8: 0.0,
                    9: 0.0,
                    10: 0.0,
                    11: 0.0,
                    12: 0.0,
                    13: 0.0,
                    14: 0.0,
                },
            ),
            EqualizerPreset(
                name="Bass Boost",
                emoji="🎶",
                description="Усиленные низкие частоты",
                bands_values={
                    0: 0.8,
                    1: 0.6,
                    2: 0.4,
                    3: 0.2,
                    4: 0.0,
                    5: -0.1,
                    6: -0.1,
                    7: 0.0,
                    8: 0.2,
                    9: 0.4,
                    10: 0.6,
                    11: 0.8,
                    12: 1.0,
                    13: 1.0,
                    14: 1.0,
                },
            ),
            EqualizerPreset(
                name="Кристальная ясность",
                emoji="💎",
                description="Подчеркнутые высокие частоты",
                bands_values={
                    0: 0.0,
                    1: 0.1,
                    2: 0.2,
                    3: 0.3,
                    4: 0.4,
                    5: 0.5,
                    6: 0.6,
                    7: 0.6,
                    8: 0.5,
                    9: 0.4,
                    10: 0.3,
                    11: 0.2,
                    12: 0.1,
                    13: 0.0,
                    14: -0.1,
                },
            ),
            EqualizerPreset(
                name="Эмоциональный вокал",
                emoji="🎤",
                description="Выделение эмоций в голосе",
                bands_values={
                    0: 0.2,
                    1: 0.1,
                    2: 0.0,
                    3: 0.1,
                    4: 0.2,
                    5: 0.3,
                    6: 0.4,
                    7: 0.5,
                    8: 0.6,
                    9: 0.7,
                    10: 0.8,
                    11: 0.9,
                    12: 1.0,
                    13: 0.9,
                    14: 0.8,
                },
            ),
            EqualizerPreset(
                name="Танцевальный ритм",
                emoji="💃",
                description="Для активных танцев",
                bands_values={
                    0: 0.6,
                    1: 0.5,
                    2: 0.4,
                    3: 0.3,
                    4: 0.2,
                    5: 0.1,
                    6: 0.0,
                    7: 0.0,
                    8: 0.1,
                    9: 0.2,
                    10: 0.3,
                    11: 0.4,
                    12: 0.5,
                    13: 0.6,
                    14: 0.7,
                },
            ),
            EqualizerPreset(
                name="Пустынный ветер",
                emoji="🏜️",
                description="Атмосфера пустыни",
                bands_values={
                    0: 0.2,
                    1: 0.3,
                    2: 0.4,
                    3: 0.5,
                    4: 0.6,
                    5: 0.7,
                    6: 0.8,
                    7: 0.8,
                    8: 0.7,
                    9: 0.6,
                    10: 0.5,
                    11: 0.4,
                    12: 0.3,
                    13: 0.2,
                    14: 0.1,
                },
            ),
            EqualizerPreset(
                name="Космический звук",
                emoji="🚀",
                description="Для космических путешествий",
                bands_values={
                    0: 0.4,
                    1: 0.3,
                    2: 0.2,
                    3: 0.1,
                    4: 0.0,
                    5: 0.0,
                    6: 0.1,
                    7: 0.2,
                    8: 0.3,
                    9: 0.4,
                    10: 0.5,
                    11: 0.6,
                    12: 0.7,
                    13: 0.8,
                    14: 0.9,
                },
            ),
            EqualizerPreset(
                name="Спокойные вечера",
                emoji="🌅",
                description="Для спокойного отдыха",
                bands_values={
                    0: 0.1,
                    1: 0.1,
                    2: 0.1,
                    3: 0.1,
                    4: 0.1,
                    5: 0.1,
                    6: 0.1,
                    7: 0.1,
                    8: 0.1,
                    9: 0.1,
                    10: 0.1,
                    11: 0.1,
                    12: 0.1,
                    13: 0.1,
                    14: 0.1,
                },
            ),
            EqualizerPreset(
                name="Меланхолия",
                emoji="😢",
                description="Для меланхоличных настроений",
                bands_values={
                    0: 0.3,
                    1: 0.2,
                    2: 0.1,
                    3: 0.0,
                    4: -0.1,
                    5: -0.2,
                    6: -0.25,
                    7: -0.25,
                    8: -0.2,
                    9: -0.1,
                    10: 0.0,
                    11: 0.1,
                    12: 0.2,
                    13: 0.3,
                    14: 0.4,
                },
            ),
            EqualizerPreset(
                name="Летний бриз",
                emoji="🌞",
                description="Легкий летний звук",
                bands_values={
                    0: 0.5,
                    1: 0.4,
                    2: 0.3,
                    3: 0.2,
                    4: 0.1,
                    5: 0.0,
                    6: 0.1,
                    7: 0.2,
                    8: 0.3,
                    9: 0.4,
                    10: 0.5,
                    11: 0.6,
                    12: 0.7,
                    13: 0.8,
                    14: 0.9,
                },
            ),
        ]

        super().__init__(
            placeholder="Выберите пресет",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=preset.name,
                    emoji=preset.emoji,
                    description=preset.description,
                )
                for preset in self.equalizer_presets
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        # получить выбранный пресет
        preset = self.values[0]
        # найти пресет из списка по названию
        preset = next((p for p in self.equalizer_presets if p.name == preset), None)
        filters = wavelink.Filters()
        filters.equalizer.set(bands=preset.bands_values)
        await self.player.set_filters(filters)
        embed = discord.Embed(
            title=f"Пресет {preset.name} {preset.emoji} установлен",
            color=discord.Color.green(),
        )
        self.view.stop()
        return await interaction.response.send_message(
            embed=embed, ephemeral=True, delete_after=1
        )


class EqualizerPreset:
    def __init__(self, name: str, emoji: str, description: str, bands_values: dict):
        self._name = name
        self._emoji = emoji
        self._description = description
        self._bands_values = bands_values

        for band, gain in self._bands_values.items():
            if not isinstance(band, int):
                raise ValueError(f"Band {band} must be an integer")
            elif band < 0 or band > 14:
                raise ValueError(f"Band {band} must be between 0 and 14")
            elif not isinstance(gain, float):
                raise ValueError(f"Gain {gain} must be a float")
            elif gain < -0.25 or gain > 1.0:
                raise ValueError(f"Gain {gain} must be between -0.25 and 1.0")

    @property
    def bands_values(self):
        return [
            {"band": key, "gain": value} for key, value in self._bands_values.items()
        ]

    @property
    def name(self):
        return self._name

    @property
    def emoji(self):
        return self._emoji

    @property
    def description(self):
        return self._description
