import datetime
import re
import socket
import subprocess
import time

import discord
import psutil
from discord import app_commands, utils
from discord.ext import commands

from utils import convert_word_from_number


@app_commands.guild_only()
class BasicCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="userinfo",
        description="Показывает информацию о пользователе"
    )
    @app_commands.rename(member="пользователь")
    @app_commands.guild_only()
    async def show_user_info(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user

        # member = await interaction.guild.fetch_member(member.id)
        member = interaction.guild.get_member(member.id)

        fields = [
            ("Имя", member.name),
            ("ID", member.id),
            ("Дата создания", utils.format_dt(member.created_at, style="R")),
            ("Дата вступления", utils.format_dt(member.joined_at, style="R")),
            ("Роли", ", ".join([role.mention for role in member.roles])),
            ("Активность", member.activity if bool(member.activity) else "Нет"),
            ("Статус", member.status),
            ("Бот", "Да" if member.bot else "Нет"),
            ("Бустер", utils.format_dt(member.premium_since, style="R") if member.premium_since else "Нет"),
            ("Ник", member.nick if member.nick else "Нет"),
        ]

        embed = discord.Embed(title="Информация о пользователе", color=discord.Color.blurple())

        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)

        embed.set_thumbnail(url=member.avatar.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

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
                result += f"{days} {convert_word_from_number('days', days)}, "
            if hours > 0:
                result += f"{hours} {convert_word_from_number('hours', hours)}, "
            if minutes > 0:
                result += f"{minutes} {convert_word_from_number('minutes', minutes)}, "
            return result.strip(", ")

        server_hostname = socket.gethostname()
        discord_gateway = self.bot.ws.latency * 1000
        ram_free = psutil.virtual_memory().available / 1024 / 1024
        ram_total = psutil.virtual_memory().total / 1024 / 1024
        ram_used = ram_total - ram_free
        cpu_usage = psutil.cpu_percent()
        la_1, la_5, la_15 = psutil.getloadavg()

        server_uptime = process_time(int(time.time() - psutil.boot_time()))

        try:
            # Запустить команду "systemctl status fn.service" и сохранить ее вывод в переменной output
            output = subprocess.check_output(['systemctl', 'status', 'fn.service'], universal_newlines=True)

            # Найти строку "Active:" в выводе и получить ее значение
            match = re.search(r'Active:\s+(.*?)\n', output)
            active_value = match.group(1)

            # Найти строку "since" в значении Active и получить ее значение
            match = re.search(r'since\s+(.*)', active_value)
            bot_uptime_dt = datetime.datetime.strptime(match.group(1).split(";")[0], '%a %Y-%m-%d %H:%M:%S %Z')
            bot_uptime = process_time(int(time.time() - bot_uptime_dt.timestamp()))
        except:
            bot_uptime = "Неизвестно"

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


async def setup(bot):
    await bot.add_cog(BasicCommands(bot))
