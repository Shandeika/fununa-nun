from .words import convert_word_from_number


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


def seconds_to_time_string(seconds: int) -> str:
    """
    Преобразует секунды в строку формата "n дней n часов n минут"

    :param seconds: Секунды
    :return: Строка в формате "n дней n часов n минут"
    """
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    result = ""
    if days > 0:
        result += f"{days} {convert_word_from_number('days', days)} "
    if hours > 0:
        result += f"{hours} {convert_word_from_number('hours', hours)} "
    if minutes > 0:
        result += f"{minutes} {convert_word_from_number('minutes', minutes)} "
    return result
