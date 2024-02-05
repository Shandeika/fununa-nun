import asyncio

import discord
from discord import Route


async def send_temporary_message(
    interaction: discord.ApplicationContext, embed: discord.Embed, timeout: float = 5
):
    message = await interaction.followup.send(embed=embed, wait=True)
    await asyncio.sleep(timeout)
    await message.delete()


async def respond_or_followup(
    interaction: discord.ApplicationContext,
    embed: discord.Embed,
    view: discord.ui.View = None,
    ephemeral: bool = False,
    timeout: float = 10,
):
    if interaction.response.is_done():
        message = await interaction.followup.send(
            embed=embed,
            view=view if view else discord.utils.MISSING,
            ephemeral=ephemeral,
            wait=True,
        )
        await asyncio.sleep(timeout)
        await message.delete()
    else:
        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=ephemeral,
            delete_after=timeout,
        )


async def set_voice_status(channel_id: int, bot: discord.Bot, status: str = None):
    r = Route(
        "PUT",
        "/channels/{channel_id}/voice-status",
        channel_id=channel_id,
    )
    p = {"status": status}
    try:
        await bot.http.request(route=r, json=p)
    except discord.DiscordServerError:
        pass
