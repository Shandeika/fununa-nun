import asyncio
import logging
import os
import traceback

import aiohttp
import discord
from dotenv import load_dotenv

from models.bot import FununaNun
from views import TracebackShowButton

logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s "%(funcName)s" [%(levelname)s]: %(message)s',
    datefmt="%d.%m.%Y-%H:%M:%S",
)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

load_dotenv()

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

bot = FununaNun()


@bot.event
async def on_application_command_error(
    ctx: discord.ApplicationContext, error: discord.DiscordException
):
    if isinstance(error, discord.HTTPException):
        if isinstance(error, discord.Forbidden):
            embed = discord.Embed(
                title="Ошибка",
                description="Нет прав сделать это",
                color=discord.Color.red(),
            )
            return await ctx.followup.send(embed=embed)
    elif isinstance(error, aiohttp.ClientResponseError):
        embed = discord.Embed(
            title="Ошибка",
            description="Ошибка при отправке запроса",
            color=discord.Color.red(),
        )
        return await ctx.followup.send(embed=embed)
    elif isinstance(error, discord.ApplicationCommandError):
        if isinstance(error, discord.ApplicationCommandInvokeError):
            embed = discord.Embed(
                title="Ошибка при выполнении команды",
                description="Ниже представлены детали ошибки",
                color=discord.Color.red(),
            )
            embed.add_field(name="Тип ошибки", value=str(type(error.original)))
            embed.add_field(name="Текст ошибки", value=str(error.original))
            embed.add_field(name="Информация об ошибке", value=str(error))
            traceback_text = "".join(
                traceback.format_exception(
                    type(error.original), error.original, error.original.__traceback__
                )
            )
            try:
                return await ctx.response.send_message(
                    embed=embed, view=TracebackShowButton(traceback_text)
                )
            except discord.InteractionResponded:
                return await ctx.followup.send(
                    embed=embed, view=TracebackShowButton(traceback_text)
                )


@bot.event
async def on_voice_state_update(
    member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
):
    # Если пользователя замутили на сервере отправить сообщение в канал
    if before.mute is False and after.mute is True:
        embed = discord.Embed(
            title="Нарушена конституция!",
            description=f"{member.mention} был замучен, что нарушает 1 пункт 29 статьи конституции РФ, который "
            f'гласит: "Каждому гарантируется свобода мысли и слова."',
            colour=discord.Colour.red(),
        )
        embed.set_footer(text="Подробнее: http://www.kremlin.ru/acts/constitution/item")
        channel = await member.guild.fetch_channel(1050024055295721516)
        message = await channel.send(embed=embed)
        # ждать пока пользователя не размутят и удалить сообщение
        user_voice_status = member.guild.get_member(member.id).voice
        while user_voice_status.mute:
            await asyncio.sleep(10)
            user_voice_status = member.guild.get_member(member.id).voice
        try:
            await message.delete()
        except discord.NotFound:
            pass


bot.run(DISCORD_TOKEN)
