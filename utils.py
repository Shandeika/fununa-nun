import asyncio
from typing import Tuple, Literal

import discord

WORDS = {
    "years": ["год", "года", "лет"],
    "months": ["месяц", "месяца", "месяцев"],
    "weeks": ["неделя", "недели", "недель"],
    "days": ["день", "дня", "дней"],
    "hours": ["час", "часа", "часов"],
    "minutes": ["минута", "минуты", "минут"],
    "seconds": ["секунда", "секунды", "секунд"],
}


def convert_word_from_number(
    word: Literal["years", "months", "weeks", "days", "hours", "minutes", "seconds"],
    number: int,
    answer_type: bool = False,
) -> str | Tuple[str, int]:
    """
    Преобразует слово от числа в нужное множественное число.

    :param word: Слово
    :param number: Число
    :param answer_type: Тип ответа. True - кортеж из строки и числа, False - строка

    :return: Кортеж из строки и числа или строка
    """
    remainder = number % 10
    if number == 1 or (number > 20 and remainder == 1):
        tr_word = WORDS[word][0]
    elif (2 <= number <= 4) or (number > 20 and 2 <= remainder <= 4):
        tr_word = WORDS[word][1]
    else:
        tr_word = WORDS[word][2]
    if answer_type:
        return (
            tr_word,
            number,
        )
    else:
        return tr_word


def seconds_to_duration(seconds: int) -> str:
    """
    Преобразует секунды в строку в формате "часы:минуты:секунды"

    :param seconds: Секунды

    :return: Строка в формате "часы:минуты:секунды"
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    duration = ""
    if hours > 0:
        duration += f"{hours}:"
    if minutes > 0 or hours > 0:
        duration += f"{minutes:02d}:"
    duration += f"{seconds:02d}"
    return duration


async def send_temporary_message(
    interaction: discord.ApplicationContext, embed: discord.Embed, timeout: float = 5
):
    message = await interaction.followup.send(embed=embed, wait=True)
    await asyncio.sleep(timeout)
    await message.delete()
