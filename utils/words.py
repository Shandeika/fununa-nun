from typing import Literal, Tuple

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
