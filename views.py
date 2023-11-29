import asyncio
import io
from typing import Any, List

import discord.ui
import wavelink
from discord.ui import View, Button


class TracebackShowButton(View):
    def __init__(self, traceback_text: str):
        super().__init__(timeout=None)
        self._tb = traceback_text

    @discord.ui.button(label="Показать traceback", style=discord.ButtonStyle.red, emoji="🛠")
    async def traceback_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if len(self._tb) >= 4096:
            embed = discord.Embed(title="Traceback",
                                  description="Traceback прикреплен отдельным файлом, так как он слишком большой",
                                  color=discord.Color.red())
            tb_file = discord.File(io.BytesIO(self._tb.encode("utf-8")), filename="traceback.txt")
            return await interaction.response.send_message(embed=embed, file=tb_file, ephemeral=True)
        embed = discord.Embed(title="Traceback", description=f"```\n{self._tb}\n```", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.red, emoji="❌")
    async def close_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.stop()
        await interaction.delete_original_response()


class SearchTrack(View):
    def __init__(self, interaction: discord.Interaction, voice_client: wavelink.Player, tracks: List[wavelink.Playable]):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.voice_client = voice_client
        self.tracks = tracks
        self.update_buttons()

    def update_buttons(self):
        for index, track in enumerate(self.tracks):
            self.add_item(
                SearchButton(
                    index=index,
                    player=self.voice_client,
                    track=track
                )
            )

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.red, row=1)
    async def close_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.stop()
        await interaction.delete_original_response()


class SearchButton(Button):
    def __init__(self, index: int, player: wavelink.Player, track: wavelink.Playable):
        super().__init__(
            label=f"Трек #{index + 1}",
            custom_id=f"search_track:{index}",
            style=discord.ButtonStyle.primary,
            row=0
        )
        self.index = index
        self.player = player
        self.track = track

    async def callback(self, interaction: discord.ApplicationContext) -> Any:
        await interaction.response.defer(ephemeral=True)
        await self.player.queue.put_wait(self.track)
        embed = discord.Embed(title="Трек добавлен в очередь", color=discord.Color.green())
        message = await interaction.followup.send(embed=embed, wait=True)
        await asyncio.sleep(5)
        await message.delete()
        if not self.player.current:
            await self.player.play(await self.player.queue.get_wait())

