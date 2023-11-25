import asyncio
import io
from typing import List, Any

import discord.ui
from discord import ButtonStyle, Interaction
from discord._types import ClientT
from discord.ui import Button, View

from custom_dataclasses import Track
from utils import get_info_yt


class GPTQuestion(discord.ui.Modal, title="GPT Question"):
    def __init__(self, question: str, model: str, gpt_invoke):
        super().__init__()
        self.question = question
        self.model = model
        self.gpt_invoke = gpt_invoke

        self.question_item = discord.ui.TextInput(label="Ваш запрос", required=True, style=discord.TextStyle.long,
                                                  default=self.question)
        self.model_item = discord.ui.TextInput(label="Модель", required=True, style=discord.TextStyle.short,
                                               default=self.model)

        self.add_item(self.question_item)
        self.add_item(self.model_item)

    async def on_submit(self, interaction) -> None:
        await interaction.response.defer(ephemeral=False, thinking=True)
        completion = await self.gpt_invoke(self.question_item.value, self.model_item.value,
                                           user_id=str(interaction.user.id))
        embed = discord.Embed(title="GPT")
        is_large = False
        if isinstance(completion, tuple):
            question = completion[0]
            answer = completion[1]
        elif isinstance(completion, str):
            question = self.question_item.value
            answer = completion
        else:
            raise TypeError(f"Неправильный тип ответа. Ожидалось str или tuple, получено {type(completion)}")
        embed.add_field(name="Вопрос", value=question[:1000], inline=False)
        if len(answer) > 1000:
            embed.add_field(name="Ответ", value="Ответ отправлен в виде файла", inline=False)
            is_large = True
        else:
            embed.add_field(name="Ответ", value=answer[:1000], inline=False)
        embed.colour = discord.Colour.blurple()
        embed.set_footer(text=f"Модель: {self.model_item.value}")
        if is_large:
            await interaction.followup.send(embed=embed,
                                            file=discord.File(io.BytesIO(answer.encode("utf-8")), "answer.txt"))
        else:
            await interaction.followup.send(embed=embed)


class PlaylistView(View):
    def __init__(self, interaction: discord.Interaction, player):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.playlist = player.queue
        self.player = player
        self.page_size = 5
        self.total_pages = (len(self.playlist) + self.page_size - 1) // self.page_size
        self.page_number = 1
        self.update_buttons()
        self.player = player
        self.message: discord.InteractionMessage | None = None  # Добавляем атрибут message

    def update_buttons(self):
        self.clear_items()

        empty_playlist = len(self.playlist) == 0

        self.add_item(PlaylistButton(label="Назад",
                                     custom_id="prev_page",
                                     disabled=self.page_number == 1 or empty_playlist))

        self.add_item(PlaylistButton(label="Вперед",
                                     custom_id="next_page",
                                     disabled=self.page_number == self.total_pages or empty_playlist))

        self.add_item(CloseButton(self.interaction))

    async def update_embed(self):
        start_index = (self.page_number - 1) * self.page_size
        end_index = start_index + self.page_size

        embed = discord.Embed(title="Плейлист", color=discord.Color.green())

        if self.player.current and len(self.playlist) == 0:
            embed.description = (f"Сейчас играет: {self.player.current.title}\n"
                                 f"Продолжительность: {self.player.current.duration_to_time()}\n"
                                 f"Ссылка: {self.player.current.original_url}")
            embed.add_field(name="Плейлист пуст", value="Добавьте треки в плейлист")
            embed.set_footer(text=f"Страница {self.page_number}/{self.total_pages}")

        else:
            for index, track in enumerate(self.playlist[start_index:end_index]):
                try:
                    embed.add_field(
                        name=f"{index + 1}. {track.title}",
                        value=f"Продолжительность: {track.duration_to_time()}",
                        inline=False
                    )
                except Exception as e:
                    print(f"Error processing track {track.url}: {e}")

            embed.set_footer(text=f"Страница {self.page_number}/{self.total_pages}")

        if self.message:
            await self.message.edit(embed=embed, view=self)


class PlaylistButton(Button):
    def __init__(self, label: str, custom_id: str, disabled: bool = False):
        super().__init__(style=ButtonStyle.primary, label=label, custom_id=custom_id, disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False, thinking=True)

        if self.custom_id == "prev_page":
            self.view.page_number = max(1, self.view.page_number - 1)
        elif self.custom_id == "next_page":
            self.view.page_number = min(self.view.total_pages, self.view.page_number + 1)
        elif self.custom_id == "close":
            self.view.stop()
            await self.view.interaction.delete_original_response()
            return

        await self.view.update_embed()


class TracebackShowButton(View):
    def __init__(self, traceback_text: str):
        super().__init__(timeout=None)
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

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.red, emoji="❌")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        self.stop()
        await interaction.delete_original_response()


class YouTubeSearch(View):
    def __init__(self, interaction: discord.Interaction, results: List[dict], player):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.results = results
        self.player = player

    async def update_buttons(self):
        for index, result in enumerate(self.results):
            self.add_item(
                SearchButton(
                    self.interaction,
                    f"https://youtube.com{result['url_suffix']}",
                    self.player,
                    index
                )
            )

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.red, row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        self.stop()
        await interaction.delete_original_response()


class SearchButton(Button):
    def __init__(self, interaction: discord.Interaction, track_url: str, player, index: int):
        super().__init__(style=ButtonStyle.blurple, label=f"Трек #{index + 1}", emoji="🎵", row=0)
        self.interaction = interaction
        self.track_url = track_url
        self.player = player

    async def callback(self, interaction: Interaction[ClientT]) -> Any:
        await interaction.response.defer(ephemeral=False, thinking=True)
        track = await get_info_yt(self.track_url)
        self.player.add(track)
        embed = discord.Embed(title="Добавлено в очередь", description=f"{track.title}",
                              color=discord.Color.green())
        embed.add_field(name="Продолжительность", value=f"{track.duration_to_time()}")
        embed.add_field(name="Ссылка", value=f"{track.original_url}", inline=False)
        embed.set_thumbnail(url=track.image_url)
        if not interaction.guild.voice_client:
            await self.player.start_play(interaction)
        message = await interaction.followup.send(embed=embed, wait=True)
        await asyncio.sleep(5)
        await message.delete()


class CloseButton(Button):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(style=ButtonStyle.red, label="Закрыть")
        self.interaction = interaction

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.view.stop()
        await self.view.interaction.delete_original_response()
