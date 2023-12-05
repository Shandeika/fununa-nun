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
