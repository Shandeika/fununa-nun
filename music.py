# Suppress noise about console usage from errors
import asyncio
import logging

import discord
import yt_dlp
from discord.ext import commands

yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

logger = logging.getLogger("bot")


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._query = list()
        self._radio_stations = {
            "маруся": "http://radio-holding.ru:9000/marusya_default",
        }

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):
        if before.channel is None:
            return
        if member.guild.get_member(self.bot.user.id).voice is None:
            return
        if (before.channel == member.guild.get_member(self.bot.user.id).voice.channel) and (
                (after.channel is None) or (after.channel != before.channel)) and len(
            member.guild.get_member(self.bot.user.id).voice.channel.members) == 1:
            await member.guild.change_voice_state(channel=None)

    async def _youtube_search(self, query: str):
        pass

    @commands.command()
    async def join(self, ctx):
        """Joins a voice channel"""
        if not ctx.author.voice.channel:
            print(ctx.author.voice.channel)
            await ctx.reply(embed=discord.Embed(title="Вы не в канале"))
            return

        channel = ctx.author.voice.channel

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await ctx.guild.change_voice_state(channel=channel)

    @commands.command()
    async def play(self, ctx: commands.Context, *, url: str):
        if self._query:
            await ctx.reply("Добавлено в плейлист")
            return self._query.append((url, ctx.message,))
        else:
            self._query.append((url, ctx.message,))
        for url in self._query:
            message = url[1]
            url = url[0]
            if url.startswith("https://youtube.com/watch?") or url.startswith("https://youtu.be/") or url.startswith(
                    "https://www.youtube.com/watch?"):
                player = await self._play_yt(ctx, url)
                await message.reply(f"**Сейчас играет**\n{player.title}")
            elif url.lower() in self._radio_stations.keys() or url.lower() in self._radio_stations.values():
                url = self._radio_stations.get(url, url)
                await self._play_stream(ctx, url)
                await message.reply(f"**Сейчас играет**\nРадиостанция: {url}")
            else:
                await self._play_stream(ctx, url)
                await message.reply(f"**Сейчас играет**\n{url}")
            while ctx.guild.voice_client.is_playing():
                await asyncio.sleep(1)

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""

        if ctx.voice_client is None:
            return await ctx.reply("Not connected to a voice channel.")

        ctx.voice_client.source.volume = volume / 100
        await ctx.reply(f"Громкость изменена на **{volume}%**")

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""

        await ctx.voice_client.disconnect()

    @commands.command()
    async def pause(self, ctx):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice and voice.is_playing():
            voice.pause()
            await ctx.reply("Музыка приостановлена.")
        else:
            await ctx.reply("Сейчас ничего не играет.")

    @commands.command()
    async def resume(self, ctx):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice and voice.is_paused():
            voice.resume()
            await ctx.reply("Музыка возобновлена.")
        else:
            await ctx.reply("Музыка не была приостановлена.")

    @commands.command()
    async def skip(self, ctx):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice and voice.is_playing():
            # остановка проигрывания текущего трека
            voice.stop()
        else:
            await ctx.send("Ничего не играет в данный момент.")

    @play.before_invoke
    async def ensure_voice(self, ctx):
        channel = ctx.author.voice.channel
        if not ctx.voice_client:
            await ctx.guild.change_voice_state(channel=channel)
        elif ctx.voice_client:
            await ctx.voice_client.move_to(channel)

    async def _play_yt(self, ctx: commands.Context, url: str):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if not voice:
            await ctx.author.voice.channel.connect()
            voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            voice.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
        return player

    async def _play_stream(self, ctx, url: str):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if not voice:
            await ctx.author.voice.channel.connect()
            voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        async with ctx.typing():
            source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url))
            voice.play(source, after=lambda e: print(f'Player error: {e}') if e else None)
        return source
