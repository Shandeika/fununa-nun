def bytes_to_words(bytes_: int) -> str:
    """
    Преобразует количество байт в строку вида "1.01 ГБ" или "1.01 МБ" или "1.01 КБ" или "1.01 Б"
    :param bytes_: Количество байт
    :return: Строка вида "1.01 ГБ" или "1.01 МБ" или "1.01 КБ" или "1.01 Б"
    """
    units = [("ГБ", 2**30), ("МБ", 2**20), ("КБ", 2**10), ("Б", 1)]

    for unit_name, unit_value in units:
        if bytes_ >= unit_value:
            return f"{bytes_ / unit_value:.2f} {unit_name}"

    return f"{bytes_} Б"
