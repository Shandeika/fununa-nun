import socket
import time

import discord
import psutil

from bot.models import BasicCog
from utils import convert_word_from_number


class BasicCommands(BasicCog):
    @discord.application_command(name="status", description="Показывает статус бота")
    async def _status(self, interaction: discord.Interaction):
        def process_time(seconds):
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

        server_hostname = socket.gethostname()
        discord_gateway = self.bot.latency * 1000
        ram_free = psutil.virtual_memory().available / 1024 / 1024
        ram_total = psutil.virtual_memory().total / 1024 / 1024
        ram_used = ram_total - ram_free
        cpu_usage = psutil.cpu_percent()
        la_1, la_5, la_15 = psutil.getloadavg()

        server_uptime = process_time(int(time.time() - psutil.boot_time()))

        bot_uptime = "Неизвестно"

        embed_description = (
            f"Версия: `{self.bot.VERSION}`\n"
            f"Пинг шлюза Discord `{discord_gateway:.2f} мс`\n"
            f"Время работы бота **{bot_uptime}**"
        )
        server_label = (
            f"Сервер: `{server_hostname}`\n"
            f"LA1 `{la_1:.2f}`, LA5 `{la_5:.2f}`, LA15 `{la_15:.2f}`\n"
            f"Загрузка CPU `{cpu_usage:.2f}%`\n"
            f"Загрузка RAM `{ram_used:.2f} МБ` из `{ram_total:.2f} МБ`\n"
            f"Свободная RAM `{ram_free:.2f} МБ`\n"
            f"Время работы **{server_uptime}**"
        )

        embed = discord.Embed(
            title="Статус бота",
            description=embed_description,
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Сервер", value=server_label, inline=False)
        await interaction.response.send_message(embed=embed)


def setup(bot):
    bot.add_cog(BasicCommands(bot))
