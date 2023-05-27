import io

import discord.ui
from discord import Interaction
from discord._types import ClientT


class GPTQuestion(discord.ui.Modal, title="GPT Question"):
    def __init__(self, question: str, model: str, gpt_invoke):
        super().__init__()
        self.question = question
        self.model = model
        self.gpt_invoke = gpt_invoke

        self.question_item = discord.ui.TextInput(label="Ваш запрос", required=True, style=discord.TextStyle.long, default=self.question)
        self.model_item = discord.ui.TextInput(label="Модель", required=True, style=discord.TextStyle.short, default=self.model)

        self.add_item(self.question_item)
        self.add_item(self.model_item)

    async def on_submit(self, interaction: Interaction[ClientT], /) -> None:
        await interaction.response.defer(ephemeral=False, thinking=True)
        completion = await self.gpt_invoke(self.question_item.value, self.model_item.value, user_id=str(interaction.user.id))
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
