import io
import logging
import os
import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

OPENAI_TOKEN = os.environ.get("OPENAI_TOKEN")

logger = logging.getLogger("bot")


class OpenAIError(Exception):
    """OpenAI API error. Provides a error message."""

    def __init__(self, request_json: dict):
        self._json = request_json

    @property
    def message(self):
        return self._json["error"]["message"]

    @property
    def status_code(self):
        return self._json["error"]["code"]

    @property
    def param(self):
        return self._json["error"]["param"]

    @property
    def type(self):
        return self._json["error"]["type"]

    def __str__(self):
        return f"OpenAIError: {self.message}"


@app_commands.guild_only()
class GPT(commands.GroupCog, group_name='gpt'):
    def __init__(self, bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        # если ошибка OpenAI
        if isinstance(error.original, OpenAIError):
            embed = discord.Embed(title="Ошибка OpenAI", description=error.original.message, color=discord.Color.red())
        elif isinstance(error.original, aiohttp.ClientResponseError):
            embed = discord.Embed(title="Ошибка", description="Ошибка при отправке запроса", color=discord.Color.red())
        else:
            embed = discord.Embed(title="Ошибка", description=f"Неизвестная ошибка", color=discord.Color.red())
            embed.add_field(name="Тип ошибки", value=type(error.original))
            embed.add_field(name="Текст ошибки", value=str(error.original))
            embed.add_field(name="Информация об ошибке", value=str(error))
        try:
            await interaction.response.send_message(embed=embed)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="question",
        description="Генерация ответа языковой моделью GPT"
    )
    @app_commands.describe(text="Запрос для языковой модели", model="Модель, которую нужно использовать")
    @app_commands.rename(text="запрос", model="модель")
    @app_commands.choices(
        model=[
            app_commands.Choice(
                name="text-davinci-003 (Любая языковая задача с лучшим качеством, превосходит curie, babbage и ada)",
                value="text-davinci-003"),
            app_commands.Choice(name="ada (Для простых задач, самая быстрая модель в серии GPT-3)", value="ada"),
            app_commands.Choice(name="babbage (Для быстрых простых задач)", value="babbage"),
            app_commands.Choice(name="curie (Мощная и недорогая модель)", value="curie"),
            app_commands.Choice(name="davinci (Самая мощная модель GPT-3 для всех задач)", value="davinci"),
            app_commands.Choice(name="text-ada-001 (Для очень простых задач, самая быстрая и недорогая модель)",
                                value="text-ada-001"),
            app_commands.Choice(name="text-babbage-001 (Для быстрых простых задач с меньшими затратами)",
                                value="text-babbage-001"),
            app_commands.Choice(name="text-curie-001 (Мощная и недорогая модель)", value="text-curie-001"),
            app_commands.Choice(
                name="code-davinci-002 (Самая мощная модель Codex для перевода естественного языка в код)",
                value="code-davinci-002"),
            app_commands.Choice(name="code-cushman-001 (Почти такой же мощный, как Davinci Codex, но немного быстрее)",
                                value="code-cushman-001"),
            app_commands.Choice(
                name="gpt-3.5-turbo (Самая мощная модель GPT-3.5, оптимизированная для чата)",
                value="gpt-3.5-turbo"),
            app_commands.Choice(
                name="text-davinci-002 (Как text-davinci-003, но обучен контролируемой тонкой настройкой)",
                value="text-davinci-002"),
        ]

    )
    async def _gpt(self, interaction: discord.Interaction, text: str, model: str = "text-davinci-003"):
        await interaction.response.defer(ephemeral=False, thinking=True)
        completion = await self.gpt_invoke(text, model, user_id=str(interaction.user.id))
        embed = discord.Embed(title="GPT")
        is_large = False
        if isinstance(completion, tuple):
            question = completion[0]
            answer = completion[1]
        elif isinstance(completion, str):
            question = text
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
        embed.set_footer(text=f"Модель: {model}")
        if is_large:
            await interaction.followup.send(embed=embed, file=discord.File(io.BytesIO(answer), "answer.txt"))
        else:
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="balance",
        description="Показать баланс OpenAI"
    )
    async def _balance(self, interaction: discord.Interaction):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.openai.com/dashboard/billing/credit_grants",
                                   headers={"Authorization": f"Bearer {OPENAI_TOKEN}",
                                            "Accept": "application/json"}) as response:
                data = await response.json()
                if response.status != 200:
                    raise OpenAIError(data)
        total_granted = "{:.2f}$".format(data.get("total_granted"))
        total_used = "{:.2f}$".format(data.get("total_used"))
        total_available = "{:.2f}$".format(data.get("total_available"))
        embed = discord.Embed(title="Баланс OpenAI", colour=discord.Colour.blurple())
        embed.add_field(name="Доступно", value=total_available, inline=True)
        embed.add_field(name="Использовано", value=f"{total_used} из {total_granted}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="tts", description="Генерация текста языковой моделью GPT и озвучка")
    @app_commands.rename(
        text="запрос"
    )
    @app_commands.describe(
        text="Запрос, на который ответит GPT, после чего ответ будет озвучен"
    )
    async def _tts(self, interaction: discord.Interaction, text: str):
        if interaction.user.voice is None:
            return await interaction.response.send_message("Ты не в канале")

        await interaction.response.defer(ephemeral=False, thinking=True)

        gpt_text = await self.gpt_invoke(text, model="text-davinci-003", user_id=str(interaction.user.id))
        if isinstance(gpt_text, tuple):
            answer = gpt_text[1]
            question = gpt_text[0]
        elif isinstance(gpt_text, str):
            answer = gpt_text
            question = text
        else:
            raise ValueError(f"Неправильный тип ответа. Ожидалось str или tuple, получено {type(gpt_text)}")

        logger.debug(f"Вопрос: {question}")
        logger.debug(f"Ответ: {answer}")

        embed = discord.Embed(title="GPT TTS", color=discord.Color.blurple())
        embed.add_field(name="Вопрос", value=question[:1000], inline=False)
        embed.add_field(name="Ответ", value=answer[:1000], inline=False)
        await interaction.followup.send(embed=embed)

        gtts_text = f"Вопрос от {interaction.user.name}: {question}\nОтвет GPT: {answer}"
        await self.bot.gtts_get_file(gtts_text)

        # подключаем бота к каналу
        voice = await interaction.user.voice.channel.connect()

        # проигрываем файл
        await self.bot.play_file("sound.mp3", voice)

        # устанавливает знак галочки
        original_response = await interaction.original_response()
        await original_response.add_reaction("✅")

    @staticmethod
    async def gpt_invoke(text: str, model: str, user_id: str = None, tokens: int = None) -> str | tuple:
        # задаем модель и промпт
        model_engine = model

        model_tokens = {
            "text-davinci-003": 4000,
            "code-davinci-002": 8000,
            "gpt-3.5-turbo": 4096,
            "text-davinci-002": 4000,
            "code-cushman-001": 2048,
            "text-curie-001": 2048,
            "text-babbage-001": 2048,
            "text-ada-001": 2048,
            "davinci": 2048,
            "curie": 2048,
            "babbage": 2048,
            "ada": 2048,
        }

        if model not in model_tokens.keys():
            raise ValueError(f"Неправильная модель. Доступные модели: {', '.join(model_tokens.keys())}. Получено: {model}")

        # задаем макс кол-во слов
        max_tokens = model_tokens[model] - len(text)

        if tokens:
            max_tokens = tokens

        # генерируем ответ с помощью aiohttp
        async with aiohttp.ClientSession() as session:
            parameters = {
                "model": model_engine,
                "prompt": text,
                "max_tokens": max_tokens,
                "temperature": 0.2,
                "top_p": 0.1,
                "n": 1,
                "stream": False,
                "logprobs": None,
                "echo": True,
            }
            if user_id:
                parameters['user'] = str(user_id)
            headers = {
                "Authorization": f"Bearer {OPENAI_TOKEN}",
                "Content-Type": "application/json",
            }
            async with session.post('https://api.openai.com/v1/completions', headers=headers, json=parameters) as response:
                data = await response.json()
        if 'error' in data.keys():
            raise OpenAIError(data)
        text = data['choices'][0]['text']

        # Разделение текста на абзацы
        paragraphs = re.split(r"\r?\n[\r\n]+", text)

        # Удаление пустых абзацев
        paragraphs = [p for p in paragraphs if p]

        # Первый абзац дополнение
        complement = paragraphs[0]

        # Остальные абзацы текстом
        response_text = "\n\n".join(paragraphs[1:])

        # Проверка на наличие поправки
        if complement:
            return complement, response_text,
        return response_text
