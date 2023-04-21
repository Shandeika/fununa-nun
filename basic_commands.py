import datetime
import re
import socket
import subprocess
import time

import discord
import psutil
from discord import app_commands
from discord.ext import commands


@app_commands.guild_only()
class BasicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="userinfo",
        description="Показывает информацию о пользователе"
    )
    @app_commands.rename(user="пользователь")
    @app_commands.guild_only()
    async def _userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        if user is None:
            user = interaction.user
        embed = discord.Embed(title="Информация о пользователе", color=discord.Color.blurple())
        embed.add_field(name="Имя", value=user.name)
        embed.add_field(name="ID", value=user.id)
        embed.add_field(name="Аккаунт создан", value=user.created_at.strftime("%d.%m.%Y %H:%M:%S"))
        embed.add_field(name="Присоединился к серверу", value=user.joined_at.strftime("%d.%m.%Y %H:%M:%S"))
        embed.add_field(name="Роли", value=", ".join([role.mention for role in user.roles]))
        embed.add_field(name="Активность", value=user.activity)
        embed.add_field(name="Статус", value=user.status)
        embed.add_field(name="Бот", value=user.bot)
        embed.add_field(name="Премиум", value=user.premium_since.strftime("%d.%m.%Y %H:%M:%S") if user.premium_since is not None else "Нет")
        embed.add_field(name="Никнейм", value=user.nick)
        embed.add_field(name="Десктоп", value=user.desktop_status)
        embed.add_field(name="Мобильный", value=user.mobile_status)
        embed.add_field(name="Веб", value=user.web_status)
        embed.set_thumbnail(url=user.avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="status",
        description="Показывает статус бота"
    )
    async def _status(self, interaction: discord.Interaction):
        def process_time(seconds):
            days = seconds // 86400
            seconds %= 86400
            hours = seconds // 3600
            seconds %= 3600
            minutes = seconds // 60
            result = ""
            if days > 0:
                result += f"{days} дней, "
            if hours > 0:
                result += f"{hours} часов, "
            if minutes > 0:
                result += f"{minutes} минут"
            return result.strip(", ")

        server_hostname = socket.gethostname()
        discord_gateway = self.bot.ws.latency * 1000
        ram_free = psutil.virtual_memory()[3] / 1024 / 1024
        ram_total = psutil.virtual_memory()[0] / 1024 / 1024
        ram_used = ram_total - ram_free
        cpu_usage = psutil.cpu_percent()
        la_1, la_5, la_15 = psutil.getloadavg()

        server_uptime = process_time(int(time.time() - psutil.boot_time()))

        # Запустить команду systemctl status fn.service и сохранить ее вывод в переменной output
        output = subprocess.check_output(['systemctl', 'status', 'fn.service'], universal_newlines=True)

        # Найти строку "Active:" в выводе и получить ее значение
        match = re.search(r'Active:\s+(.*?)\n', output)
        active_value = match.group(1)

        # Найти строку "since" в значении Active и получить ее значение
        match = re.search(r'since\s+(.*)', active_value)
        bot_uptime_dt = datetime.datetime.strptime(match.group(1).split(";")[0], '%a %Y-%m-%d %H:%M:%S %Z')
        bot_uptime = process_time(int(time.time() - bot_uptime_dt.timestamp()))

        embed_description = f"Версия: `{self.bot.VERSION}`\n" \
                            f"Пинг шлюза Discord `{discord_gateway:.2f} мс`\n" \
                            f"Время работы бота **{bot_uptime}**"
        server_label = f"Сервер: `{server_hostname}`\n" \
                       f"LA1 `{la_1:.2f}`, LA5 `{la_5:.2f}`, LA15 `{la_15:.2f}`\n" \
                       f"Загрузка CPU `{cpu_usage:.2f}%`\n" \
                       f"Загрузка RAM `{ram_used:.2f} МБ` из `{ram_total:.2f} МБ`\n" \
                       f"Свободная RAM `{ram_free:.2f} МБ`\n" \
                       f"Время работы **{server_uptime}**"

        embed = discord.Embed(title="Статус бота", description=embed_description, color=discord.Color.blurple())
        embed.add_field(name="Сервер", value=server_label, inline=False)
        await interaction.response.send_message(embed=embed)
