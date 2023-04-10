import discord
from discord.ext import commands


class Responder(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot
        self.responders = [
            386549311837700109,
            335464992079872000,
        ]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id not in self.responders:
            return
        async with message.channel.typing():
            text = f"Придумай шутку про {message.author.name}. Язык русский. Длина до 2000 символов. Его последнее сообщение: \"{message.content}\"."
            response = await self.bot.cogs["GPT"].gpt_invoke(text, "text-davinci-003")
            await message.reply(response[1][:2000])
