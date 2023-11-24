from dataclasses import dataclass


@dataclass
class Track:
    title: str
    url: str
    duration: float
    image_url: str
    raw_data: dict
    original_url: str

    def duration_to_time(self):
        # Перевести секунды во время часы:минуты:секунды. Если единица времени меньше 0, то не добавлять ее
        hours = self.duration // 3600
        minutes = (self.duration % 3600) // 60
        seconds = self.duration % 60

        time_str = ""
        if hours > 0:
            time_str += f"{hours}:"
        if minutes > 0 or hours > 0:
            time_str += f"{minutes:02d}:"
        time_str += f"{seconds:02d}"

        return time_str
