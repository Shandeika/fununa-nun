import asyncio
import io
from typing import Any, List

import discord.ui
import wavelink
from discord import Interaction
from discord._types import ClientT
from discord.ui import View, Button


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


class SearchTrack(View):
    def __init__(self, interaction: discord.Interaction, voice_client: wavelink.Player, tracks: List[wavelink.YouTubeTrack]):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.voice_client = voice_client
        self.tracks = tracks
        self.update_buttons()

    def update_buttons(self):
        for index, track in enumerate(self.tracks):
            self.add_item(
                SearchButton(
                    index=index,
                    player=self.voice_client,
                    track=track
                )
            )

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.red, row=1)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        self.stop()
        await interaction.delete_original_response()


class SearchButton(Button):
    def __init__(self, index: int, player: wavelink.Player, track: wavelink.YouTubeTrack):
        super().__init__(
            label=f"Трек #{index + 1}",
            custom_id=f"search_track:{index}",
            style=discord.ButtonStyle.primary,
            row=0
        )
        self.index = index
        self.player = player
        self.track = track

    async def callback(self, interaction: Interaction[ClientT]) -> Any:
        await interaction.response.defer(ephemeral=True)
        await self.player.queue.put_wait(self.track)
        embed = discord.Embed(title="Трек добавлен в очередь", color=discord.Color.green())
        message = await interaction.followup.send(embed=embed, wait=True)
        await asyncio.sleep(5)
        await message.delete()
        if not self.player.is_playing():
            await self.player.play(await self.player.queue.get_wait())

