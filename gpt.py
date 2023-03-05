import json
import logging
import os
from io import BytesIO

import aiohttp
import discord
import openai_async
from PIL import Image
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()


OPENAI_TOKEN = os.environ.get("OPENAI_TOKEN")

logger = logging.getLogger("bot")


class GPT(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="gpt",
    )
    async def _gpt(self, ctx: commands.Context, *, text: str):
        async with ctx.typing():
            completion = await self.gpt_invoke(text, "text-davinci-003")
        # отправляем ответ
        try:
            text = completion.json()["choices"][0]["text"].strip()
        except KeyError:
            text = f"""Ошибка, ключ не найден
    Ответ json:
    ```json
    {json.dumps(completion.json(), sort_keys=True, indent=4)}
    ```"""
        except Exception as e:
            text = f"""Неизвестная ошибка
    Ответ json:
    ```json
    {json.dumps(completion.json(), sort_keys=True, indent=4)}
    ```
    Ошибка:
    ```py
    {e}
    ```"""
        await ctx.reply(text)

    @commands.command(name="balance")
    async def _balance(self, ctx: commands.Context):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.openai.com/dashboard/billing/credit_grants",
                                   headers={"Authorization": f"Bearer {OPENAI_TOKEN}",
                                            "Accept": "application/json"}) as response:
                data = await response.json()
        total_granted = "{:.2f}$".format(data["total_granted"])
        total_used = "{:.2f}$".format(data["total_used"])
        total_available = "{:.2f}$".format(data["total_available"])
        await ctx.send(f"Баланс: **{total_available}**, использовано **{total_used}** из **{total_granted}**")

    @commands.command(name="image")
    async def _image(self, ctx: commands.Context, *, text: str):
        async with ctx.typing():
            async with aiohttp.ClientSession() as session:
                # Создаем запрос к OpenAI API для генерации изображения
                headers = {'Authorization': f'Bearer {OPENAI_TOKEN}', "Accept": "application/json"}
                payload = {'prompt': text,
                           'n': 1,
                           "response_format": "url",
                           "user": str(ctx.author.id),
                           "size": "1024x1024",
                           }
                async with session.post('https://api.openai.com/v1/images/generations', json=payload,
                                        headers=headers) as response:
                    data = await response.json()
                    print(data)

                # Извлекаем URL-адрес изображения из ответа API
                image_url = data['data'][0]['url'].strip()

                # Получаем изображение из URL-адреса
                async with session.get(image_url) as response:
                    image_data = await response.read()

            # Создаем объект Image из полученных данных изображения
            image = Image.open(BytesIO(image_data))

        # Сохраняем изображение
        image.save("image.png")

        with open("image.png", "rb") as image:
            image_saved = image.read()

        # Отправляем изображение в чат Discord
        await ctx.send(file=discord.File(image_saved, "image.png"))

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

