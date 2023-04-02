import discord
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
        embed.add_field(name="Премиум", value=user.premium_since.strftime("%d.%m.%Y %H:%M:%S"))
        embed.add_field(name="Никнейм", value=user.nick)
        embed.add_field(name="Десктоп", value=user.desktop_status)
        embed.add_field(name="Мобильный", value=user.mobile_status)
        embed.add_field(name="Веб", value=user.web_status)
        embed.set_thumbnail(url=user.avatar.url)
        await interaction.response.send_message(embed=embed)
