import datetime
import re
import socket
import subprocess
import time

import discord
import psutil
from discord import app_commands, utils
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
        # Получение пользователя сервера по ID
        user = await interaction.guild.fetch_member(user.id)
        # Получение значений и преобразование
        user_name = user.name
        user_id = user.id
        user_created_at = utils.format_dt(user.created_at, style="R")
        user_joined_at = utils.format_dt(user.joined_at, style="R")
        user_roles = ", ".join([role.mention for role in user.roles])
        user_activity = user.activity if user.activity is not None else "Нет"
        user_status = user.status
        user_bot = "Да" if user.bot else "Нет"
        user_premium_since = utils.format_dt(user.premium_since, style="R") if user.premium_since is not None else "Нет"
        user_nick = user.nick if user.nick is not None else "Нет"
        user_desktop_status = user.desktop_status
        user_mobile_status = user.mobile_status
        user_web_status = user.web_status
        user_avatar_url = user.avatar.url
        # Формирование embed
        embed = discord.Embed(title="Информация о пользователе", color=discord.Color.blurple())
        embed.add_field(name="Имя", value=user_name, inline=False)
        embed.add_field(name="ID", value=user_id, inline=False)
        embed.add_field(name="Дата создания", value=user_created_at, inline=True)
        embed.add_field(name="Дата вступления", value=user_joined_at, inline=True)
        embed.add_field(name="Роли", value=user_roles, inline=False)
        embed.add_field(name="Активность", value=user_activity, inline=False)
        embed.add_field(name="Статус", value=user_status, inline=False)
        embed.add_field(name="Бот", value=user_bot, inline=False)
        embed.add_field(name="Премиум", value=user_premium_since, inline=False)
        embed.add_field(name="Ник", value=user_nick, inline=False)
        embed.add_field(name="Статус на десктопе", value=user_desktop_status, inline=True)
        embed.add_field(name="Статус на мобильном", value=user_mobile_status, inline=True)
        embed.add_field(name="Статус на вебе", value=user_web_status, inline=True)
        embed.set_thumbnail(url=user_avatar_url)
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
