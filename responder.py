import discord
from discord.ext import commands


class Responder(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot
        self.responders = [
            386549311837700109,
            714811357169451029,
        ]  # TODO: move to database

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id not in self.responders:
            return
        elif message.content is "":
            return
        async with message.channel.typing():
            text = f"Генерация шутки про человека {message.author.name} на основе его последнего сообщения \"{message.content}\". Язык русский, максимальная длина сообщения 2000 символов. В ответе должна быть только шутка."
            response = await self.bot.cogs["GPT"].gpt_invoke(text, "text-davinci-003")
            await message.reply(response[1][:2000])
