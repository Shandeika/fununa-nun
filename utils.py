import asyncio
from typing import Tuple, Literal

from custom_dataclasses import Track
from ytdl import ytdl

WORDS = {
    "years": ["год", "года", "лет"],
    "months": ["месяц", "месяца", "месяцев"],
    "weeks": ["неделя", "недели", "недель"],
    "days": ["день", "дня", "дней"],
    "hours": ["час", "часа", "часов"],
    "minutes": ["минута", "минуты", "минут"],
    "seconds": ["секунда", "секунды", "секунд"]
}


async def get_info_yt(url: str) -> Track:
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    track = Track(
        title=data.get('title'),
        url=data.get('url'),
        duration=data.get('duration'),
        image_url=data.get('thumbnail'),
        raw_data=data,
        original_url=url
    )
    return track


def convert_word_from_number(
        word: Literal['years', 'months', 'weeks', 'days', 'hours', 'minutes', 'seconds'],
        number: int,
        answer_type: bool = False
) -> str | Tuple[str, int]:
    """
    Преобразует слово от числа в нужное множественное число.

    :param word: Слово
    :param number: Число
    :param answer_type: Тип ответа. True - кортеж из строки и числа, False - строка

    :return: Кортеж из строки и числа или строка
    """
    remainder = number % 10
    if remainder == 1:
        tr_word = WORDS[word][0]
    elif 2 <= remainder <= 4:
        tr_word = WORDS[word][1]
    else:
        tr_word = WORDS[word][2]
    if answer_type:
        return (tr_word, number,)
    else:
        return tr_word
