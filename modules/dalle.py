import asyncio
import os
from io import BytesIO
from typing import Literal, List

import aiohttp
import discord
import openai
from PIL import Image
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

OPENAI_TOKEN = os.environ.get("OPENAI_TOKEN")


@app_commands.guild_only()
class DALLE(commands.GroupCog, group_name='dalle'):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def b64_to_image(b64_json: str, to_bytes: bool = False) -> Image:
        """
        Преобразовать строку в формате base64 в изображение
        """
        # Получить изображение из строки в формате base64
        image = Image.open(BytesIO(b64_json))
        if not to_bytes:
            return image
        else:
            return BytesIO(image.tobytes())

    @staticmethod
    async def url_to_image(url: str, to_bytes: bool = False) -> Image:
        """
        Получить изображение из URL
        """
        # Получить изображение из URL
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                bytes_response = BytesIO(await response.read())
                image = Image.open(bytes_response)
        if not to_bytes:
            return image
        else:
            return bytes_response

    @staticmethod
    async def dalle_generate(
            prompt: str,
            resolution: Literal["256x256", "512x512", "1024x1024"],
            n: int,
            response_format: Literal["url", "b64_json"] = "url",
            user: str = str()
    ) -> List[str]:
        if n < 1 or n > 10:
            raise ValueError("n must be between 1 and 10")
        # Создаем запрос к OpenAI API для генерации изображения
        dalle_request = await openai.Image.acreate(
            OPENAI_TOKEN,
            prompt=prompt,
            n=n,
            user=user,
            response_format=response_format,
            size=resolution
        )
        if response_format == "url":
            return [i.get("url") for i in dalle_request.get("data")]
        elif response_format == "b64_json":
            return [i.get("b64_json") for i in dalle_request.get("data")]

    @staticmethod
    async def dalle_variation(
            image,
            user: str,
            count: int = 1,
            resolution: Literal["256x256", "512x512", "1024x1024"] = "1024x1024"
    ) -> list:
        if count < 1 or count > 10:
            raise ValueError("Количество изображений должно быть от 1 до 10")
        images = await openai.Image.acreate_variation(image, OPENAI_TOKEN, n=count, size=resolution)
        return [i['url'] for i in images['data']]

    @app_commands.command(
        name="generate",
        description="Генерация изображения DALL·E"
    )
    @app_commands.choices(
        resolution=[
            app_commands.Choice(name="256x256", value="256x256"),
            app_commands.Choice(name="512x512", value="512x512"),
            app_commands.Choice(name="1024x1024", value="1024x1024"),
        ]
    )
    @app_commands.describe(text="Запрос для генерации изображения", resolution="Разрешение изображения")
    @app_commands.rename(text="запрос", resolution="разрешение")
    async def _image(
            self,
            interaction: discord.Interaction,
            text: str,
            resolution: Literal["256x256", "512x512", "1024x1024"] = "1024x1024"
    ):
        await interaction.response.defer(ephemeral=False, thinking=True)
        async with aiohttp.ClientSession() as session:
            # Создаем запрос к OpenAI API для генерации изображения
            dalle_request = await self.dalle_generate(
                prompt=text,
                resolution=resolution,
                n=1,
                response_format="url",
                user=str(interaction.user.id)
            )
        image = await self.url_to_image(dalle_request[0], to_bytes=True)
        print(image)
        print(type(image))
        # Отправляем изображение в чат Discord
        file = discord.File(fp=image, filename="../image.png")
        embed = discord.Embed(title="DALL·E Generate", description=text, colour=discord.Colour.blurple())
        embed.set_image(url="attachment://image.png")
        embed.set_footer(text=f"Разрешение изображения: {resolution}")
        embed.set_author(name="DALL·E")
        await interaction.followup.send(embed=embed, file=file)

    @app_commands.command(
        name="variations",
        description="Генерация вариаций изображения"
    )
    @app_commands.describe(image="Изображение для генерации вариаций")
    @app_commands.rename(image="изображение")
    async def _image_variations(self, interaction: discord.Interaction, image: discord.Attachment):
        await interaction.response.defer(ephemeral=False, thinking=True)
        if image.content_type != "image/png":
            raise ValueError(f"Неправильный тип изображения. Ожидалось image/png, получено {image.content_type}")
        elif image.width != image.height:
            raise ValueError(
                f"Неправильный размер изображения. Ожидалось квадратное изображение, получено {image.width}x{image.height}")
        elif image.size > 4 * 1024 * 1024:
            raise ValueError(
                f"Неправильный размер изображения. Ожидалось меньше 4 МБ, получено {image.size / 1024 / 1024} МБ")
        # Сохраняем картинку как файл
        file = await image.to_file()
        images = await self.dalle_variation(file.fp, str(interaction.user.id), 4, "1024x1024")
        embed = discord.Embed(title="DALL·E Variations",
                              description="Вариации изображения прикреплены к сообщению",
                              colour=discord.Colour.blurple(), )
        embed.set_thumbnail(url=image.url)

        async def download_image(session, image_url, filename):
            async with session.get(image_url) as response:
                image_bytes = await response.read()
            return discord.File(BytesIO(image_bytes), filename=filename)

        async with aiohttp.ClientSession() as session:
            tasks = []
            for i, image_url in enumerate(images):
                task = asyncio.ensure_future(download_image(session, image_url, f"image_{i}.png"))
                tasks.append(task)
            files = await asyncio.gather(*tasks)

        await interaction.followup.send(
            embed=embed,
            files=files
        )

    @app_commands.command(
        name="picture",
        description="Получение изображения и отправка (тестирование)"
    )
    async def _test_picture(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False, thinking=True)
        picture = await self.url_to_image("https://shandy-dev.ru/avatar.png", to_bytes=True)
        await interaction.followup.send(file=discord.File(fp=picture, filename="../image.png"))
