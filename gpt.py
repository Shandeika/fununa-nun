import json
import logging
import os
from io import BytesIO

import aiohttp
import discord
import openai_async
from PIL import Image
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

    @app_commands.command(
        name="question",
        description="Генерация ответа языковой моделью GPT"
    )
    @app_commands.describe(text="Текст, который получит языковая модель")
    async def _gpt(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer(ephemeral=False, thinking=True)
        completion = await self.gpt_invoke(text, "text-davinci-003")
        embed = discord.Embed(title="GPT")
        if isinstance(completion, tuple):
            embed.add_field(name="Вопрос", value=text + completion[0], inline=False)
            embed.add_field(name="Ответ", value=completion[1], inline=False)
            embed.colour = discord.Colour.blurple()
        elif isinstance(completion, str):
            embed.add_field(name="Вопрос", value=text, inline=False)
            embed.add_field(name="Ответ", value=completion, inline=False)
            embed.colour = discord.Colour.blurple()
        else:
            embed.add_field(name="Вопрос", value=text, inline=False)
            embed.add_field(name="Ответ", value="Какая-то ошибка...", inline=False)
            embed.colour = discord.Colour.red()
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
        total_granted = "{:.2f}$".format(data["total_granted"])
        total_used = "{:.2f}$".format(data["total_used"])
        total_available = "{:.2f}$".format(data["total_available"])
        embed = discord.Embed(title="Баланс OpenAI", colour=discord.Colour.blurple())
        embed.add_field(name="Доступно", value=total_available, inline=True)
        embed.add_field(name="Использовано", value=f"{total_used} из {total_granted}", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="image",
        description="Генерация изображения языковой моделью GPT"
    )
    async def _image(self, interaction: discord.Interaction, text: str):
        await interaction.response.defer(ephemeral=False, thinking=True)
        async with aiohttp.ClientSession() as session:
            # Создаем запрос к OpenAI API для генерации изображения
            headers = {'Authorization': f'Bearer {OPENAI_TOKEN}', "Accept": "application/json"}
            payload = {'prompt': text,
                       'n': 1,
                       "response_format": "url",
                       "user": str(interaction.user.id),
                       "size": "1024x1024",
                       }
            async with session.post('https://api.openai.com/v1/images/generations', json=payload,
                                    headers=headers) as response:
                data = await response.json()

            # Проверяем, есть ли в ответе API ошибка
            if 'error' in data.keys():
                embed = discord.Embed(title="Ошибка OpenAI", description=data['error']['message'], colour=discord.Colour.red())
                return await interaction.followup.send(embed=embed)

            # Извлекаем URL-адрес изображения из ответа API
            image_url = data['data'][0]['url'].strip()

            # Получаем изображение из URL-адреса
            async with session.get(image_url) as response:
                image_data = await response.read()

            # Создаем объект Image из полученных данных изображения
            image = Image.open(BytesIO(image_data))

        # Сохраняем изображение
        image.save("image.png")

        # Отправляем изображение в чат Discord
        file = discord.File("image.png", filename="image.png")
        embed = discord.Embed(title="GPT Image", description=text, colour=discord.Colour.blurple())
        embed.set_image(url="attachment://image.png")
        await interaction.followup.send(embed=embed, file=file)

    @app_commands.command(name="tts", description="Генерация текста языковой моделью GPT и озвучка")
    @app_commands.rename(
        text="запрос"
    )
    @app_commands.describe(
        text="Запрос, на который ответит GPT, после чего ответ будет озвучен"
    )
    async def _ttsgpt(self, interaction: discord.Interaction, text: str):
        if interaction.user.voice is None:
            return await interaction.response.send_message("Ты не в канале")

        await interaction.response.defer(ephemeral=False, thinking=True)

        try:
            gpt_text = await self.gpt_invoke(text, model="text-davinci-003")
        except OpenAIError as e:
            embed = discord.Embed(title="Ошибка OpenAI API", description=f"Ошибка:\n```{e.message}```", color=discord.Color.red())
            return await interaction.followup.send(embed=embed)
        if isinstance(gpt_text, tuple):
            answer = gpt_text[1]
            addition = gpt_text[0]
            question = text + addition
        elif isinstance(gpt_text, str):
            answer = gpt_text
            question = text
        else:
            raise ValueError("Ошибка ответа")

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
        await interaction.original_response().add_reaction("✅")

    @staticmethod
    async def gpt_invoke(text: str, model: str) -> str | tuple:
        # задаем модель и промпт
        model_engine = model

        model_tokens = {
            "text-davinci-003": 4000,
            "code-davinci-002": 8000,
            "gpt-3.5-turbo": 4096,
        }

        # задаем макс кол-во слов
        max_tokens = model_tokens[model] - len(text)

        # генерируем ответ
        completion = await openai_async.complete(
            api_key=OPENAI_TOKEN,
            timeout=180,
            payload={
                "prompt": text,
                "max_tokens": max_tokens,
                "temperature": 0.2,
                "top_p": 0.1,
                "n": 1,
                "stream": False,
                "logprobs": None,
                "echo": False,
                "model": model_engine,
            }
        )
        if 'error' in completion.json().keys():
            raise OpenAIError(completion.json()['error'])
        try:
            data = completion.json()["choices"][0]["text"].strip()
        except KeyError:
            logger.error(f"Не найден ключ в словаре {completion.json().keys()}. Ошибка {completion.json()['error']}")
            return
        except Exception as e:
            logger.error(f'Неизвестная ошибка "{e}"')
            return

        # проверка на наличие поправки
        if len(data.split("\n\n", 1)) > 1:
            data_list = data.split("\n\n", 1)
            return (data_list[0], data_list[1],)
        return data
