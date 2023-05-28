import datetime
import json
import os
from typing import Union

import aiohttp
import discord
from discord.ext import commands


class WatchDog(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot
        self.members = json.loads(os.environ.get("WD_MEMBERS", '[]'))
        self._webhook_url = os.environ.get("WD_WEBHOOK")
        self._webhook_id = int(os.environ.get("WD_WEBHOOK_ID"))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id not in self.members:
            return
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(self._webhook_url, session=session)
            await webhook.send(
                message.content,
                username=message.author.name,
                avatar_url=message.author.avatar.url,
                tts=False,
                files=[await attachment.to_file() for attachment in message.attachments],
                embeds=message.embeds,
            )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.id not in self.members:
            return
        embed = discord.Embed(title="Изменение сообщения", colour=discord.Colour.blurple())
        embed.add_field(name="Предыдущее сообщение", value=before.content, inline=False)
        embed.add_field(name="Новое сообщение", value=after.content, inline=False)
        return await self.send_webhook(before.author.name, before.author.avatar.url, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.id not in self.members:
            return
        embed = discord.Embed(title="Удаление сообщения", colour=discord.Colour.red())
        embed.add_field(name="Удалённое сообщение", value=message.content, inline=False)
        return await self.send_webhook(message.author.name, message.author.avatar.url, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # This is called when one or more of the following things change:
        # nickname
        # roles
        # pending
        # timeout
        # guild avatar
        # flags
        if before.id not in self.members:
            return
        embed = discord.Embed(title="Изменение on_member_update", colour=discord.Colour.blurple())
        if before.nick != after.nick:
            embed = discord.Embed(title="Изменение ника", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущий ник", value=before.nick, inline=False)
            embed.add_field(name="Новый ник", value=after.nick, inline=False)
        elif before.guild_avatar != after.guild_avatar:
            embed = discord.Embed(title="Изменение аватара сервера", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущий аватар сервера", value=before.guild_avatar.url, inline=False)
            embed.add_field(name="Новый аватар сервера", value=after.guild_avatar.url, inline=False)
        elif before.status != after.status:
            embed = discord.Embed(title="Изменение статуса", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущий статус", value=before.status, inline=False)
            embed.add_field(name="Новый статус", value=after.status, inline=False)
        elif before.roles != after.roles:
            embed = discord.Embed(title="Изменение ролей", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущие роли",
                            value=", ".join([role.mention for role in before.roles if role.name != "@everyone"]),
                            inline=False)
            embed.add_field(name="Новые роли",
                            value=", ".join([role.mention for role in after.roles if role.name != "@everyone"]),
                            inline=False)
        elif before.activity != after.activity:
            embed = discord.Embed(title="Изменение активности", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущая активность", value=before.activity.name, inline=False)
            embed.add_field(name="Новая активность", value=after.activity.name, inline=False)
        elif before.pending != after.pending:
            embed = discord.Embed(title="Изменение pending", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущий pending", value=before.pending, inline=False)
            embed.add_field(name="Новый pending", value=after.pending, inline=False)
        await self.add_embed_info(embed, before)
        return await self.send_webhook(before.name, before.avatar.url, embed)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        # This is called when one or more of the following things change:
        # avatar
        # username
        # discriminator
        if before.id not in self.members:
            return
        embed = discord.Embed(title="Изменение on_user_update", colour=discord.Colour.blurple())
        if before.avatar != after.avatar:
            embed = discord.Embed(title="Изменение аватара", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущий аватар", value=before.avatar.url, inline=False)
            embed.add_field(name="Новый аватар", value=after.avatar.url, inline=False)
        elif before.name != after.name:
            embed = discord.Embed(title="Изменение имени", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущее имя", value=before.name, inline=False)
            embed.add_field(name="Новое имя", value=after.name, inline=False)
        elif before.discriminator != after.discriminator:
            embed = discord.Embed(title="Изменение дискриминатора", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущий дискриминатор", value=before.discriminator, inline=False)
            embed.add_field(name="Новый дискриминатор", value=after.discriminator, inline=False)
        await self.add_embed_info(embed, after)
        return await self.send_webhook(before.name, before.avatar.url, embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        # The following, but not limited to, examples illustrate when this event is called:
        # A member joins a voice or stage channel.
        # A member leaves a voice or stage channel.
        # A member is muted or deafened by their own accord.
        # A member is muted or deafened by a guild administrator.
        if member.id not in self.members:
            return
        embed = discord.Embed(title="Изменение on_voice_state_update", colour=discord.Colour.blurple())
        if before.channel != after.channel:
            embed = discord.Embed(title="Изменение канала", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущий канал", value=before.channel.mention if before.channel else "Нет",
                            inline=False)
            embed.add_field(name="Новый канал", value=after.channel.mention if after.channel else "Нет", inline=False)
        elif before.self_mute != after.self_mute:
            embed = discord.Embed(title="Изменение самомута", colour=discord.Colour.red())
            embed.add_field(name="Предыдущий мут", value=before.self_mute, inline=False)
            embed.add_field(name="Новый мут", value=after.self_mute, inline=False)
        elif before.mute != after.mute:
            embed = discord.Embed(title="Изменение мута", colour=discord.Colour.red())
            embed.add_field(name="Предыдущий мут", value=before.mute, inline=False)
            embed.add_field(name="Новый мут", value=after.mute, inline=False)
        elif before.self_deaf != after.self_deaf:
            embed = discord.Embed(title="Изменение самоглуха", colour=discord.Colour.red())
            embed.add_field(name="Предыдущий глух", value=before.self_deaf, inline=False)
            embed.add_field(name="Новый глух", value=after.self_deaf, inline=False)
        elif before.deaf != after.deaf:
            embed = discord.Embed(title="Изменение глуха", colour=discord.Colour.red())
            embed.add_field(name="Предыдущий глух", value=before.deaf, inline=False)
            embed.add_field(name="Новый глух", value=after.deaf, inline=False)
        elif before.self_stream != after.self_stream:
            embed = discord.Embed(title="Изменение стрима", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущий стрим", value=before.self_stream, inline=False)
            embed.add_field(name="Новый стрим", value=after.self_stream, inline=False)
        elif before.self_video != after.self_video:
            embed = discord.Embed(title="Изменение видео", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущий видео", value=before.self_video, inline=False)
            embed.add_field(name="Новый видео", value=after.self_video, inline=False)
        elif before.afk != after.afk:
            embed = discord.Embed(title="Изменение AFK", colour=discord.Colour.blurple())
            embed.add_field(name="Предыдущий AFK", value=before.afk, inline=False)
            embed.add_field(name="Новый AFK", value=after.afk, inline=False)
        await self.add_embed_info(embed, member)
        return await self.send_webhook(member.name, member.avatar.url, embed)

    @staticmethod
    async def add_embed_info(embed: discord.Embed, member: Union[discord.Member, discord.User]):
        embed.set_author(name=member.name, icon_url=member.avatar.url)
        time = datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=3), name='МСК')).strftime(
            '%d.%m.%Y %H:%M:%S')
        embed.set_footer(text=f"ID: {member.id} | {time}")

    async def send_webhook(self, username: str, avatar: str, embed: discord.Embed, view: discord.ui.View = None):
        async with aiohttp.ClientSession() as session:
            # webhook = discord.Webhook.from_url(self._webhook_url, session=session)
            webhook: discord.Webhook = await self.bot.fetch_webhook(self._webhook_id)
            await webhook.send(
                username="Watch Dog FN",
                avatar_url="https://assets.shandy-dev.ru/watchdog_fn_wh_icon.png",
                embed=embed,
                view=view if view else discord.utils.MISSING,
            )
