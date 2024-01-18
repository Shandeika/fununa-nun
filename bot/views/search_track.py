from typing import List

import discord
import wavelink

from utils import send_temporary_message


class SearchTrack(discord.ui.View):
    def __init__(
        self,
        interaction: discord.Interaction,
        voice_client: wavelink.Player,
        tracks: List[wavelink.Playable],
    ):
        super().__init__(timeout=60)
        self.interaction = interaction
        self.voice_client = voice_client
        self.tracks = tracks
        self.update_buttons()

    def update_buttons(self):
        for index, track in enumerate(self.tracks):
            self.add_item(
                SearchButton(index=index, player=self.voice_client, track=track)
            )

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.red, row=1)
    async def close_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        self.stop()
        await interaction.delete_original_response()

    async def on_timeout(self) -> None:
        await self.interaction.delete_original_response()


class SearchButton(discord.ui.Button):
    def __init__(self, index: int, player: wavelink.Player, track: wavelink.Playable):
        super().__init__(
            label=f"Трек #{index + 1}",
            custom_id=f"search_track:{index}",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        self.index = index
        self.player = player
        self.track = track

    async def callback(self, interaction: discord.ApplicationContext) -> None:
        await interaction.response.defer(ephemeral=True)
        self.track.extras = {"requester": interaction.user.id}
        await self.player.queue.put_wait(self.track)
        embed = discord.Embed(
            title="Трек добавлен в очередь", color=discord.Color.green()
        )
        await send_temporary_message(interaction, embed)
        if not self.player.current:
            await self.player.play(await self.player.queue.get_wait())
