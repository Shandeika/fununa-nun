import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import discord
from discord.ext import commands
from dotenv import load_dotenv
from gtts import gTTS

from gpt import GPT
from music import Music

logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s "%(funcName)s" [%(levelname)s]: %(message)s', datefmt='%d.%m.%Y-%H:%M:%S')
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


load_dotenv()

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"),
                   description='Relatively simple music bot example')


@bot.event
async def on_ready():
    logger.info(f'Logged in as "{bot.user.name}" with ID {bot.user.id}')
    activity = discord.CustomActivity(emoji="🎵", name="Слушаем музыку вместе")
    await bot.change_presence(status=discord.Status.idle, activity=activity)


@bot.command(name="tts")
async def _tts(ctx: commands.Context, *, text: str):
    executor = ThreadPoolExecutor()
    if ctx.message.reference:
        message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        text = message.content
    async with ctx.typing():
        def gtts_generate():
            tts = gTTS(text=text, lang='ru')
            tts.save('sound.mp3')

        await asyncio.get_running_loop().run_in_executor(executor, gtts_generate)
    if ctx.author.voice is None:
        await ctx.reply("Ты не в канале")
        return

    # подключаем бота к каналу
    channel = ctx.author.voice.channel
    voice = await channel.connect()
    # проиграть аудио
    voice.play(discord.FFmpegPCMAudio("sound.mp3"))
    # ожидать завершения проигрывания
    while voice.is_playing():
        await asyncio.sleep(1)
    # остановить проигрывание
    voice.stop()
    # отключиться от голосового канала
    await voice.disconnect()
    # удалить файл
    try:
        os.remove("sound.mp3")
    except PermissionError:
        pass
    except Exception as e:
        print(e)
    return await ctx.reply(f"Текст был воспроизведен в голосовом канале")


bot.add_cog(Music(bot))
bot.add_cog(GPT(bot))
bot.run(DISCORD_TOKEN)
