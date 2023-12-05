import discord


class TracebackShowButton(discord.ui.View):
    def __init__(self, traceback_text: str):
        super().__init__(timeout=None)
        self._tb = traceback_text

    @discord.ui.button(
        label="Показать traceback", style=discord.ButtonStyle.red, emoji="🛠"
    )
    async def traceback_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if len(self._tb) >= 4096:
            embed = discord.Embed(
                title="Traceback",
                description="Traceback прикреплен отдельным файлом, так как он слишком большой",
                color=discord.Color.red(),
            )
            tb_file = discord.File(
                io.BytesIO(self._tb.encode("utf-8")), filename="traceback.txt"
            )
            return await interaction.response.send_message(
                embed=embed, file=tb_file, ephemeral=True
            )
        embed = discord.Embed(
            title="Traceback",
            description=f"```\n{self._tb}\n```",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Закрыть", style=discord.ButtonStyle.red)
    async def close_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.defer(ephemeral=True)
        self.stop()
        await interaction.delete_original_response()
