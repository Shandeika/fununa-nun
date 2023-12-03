import discord
import wavelink
from discord.ext import pages as pg
from discord.ext.pages import PageGroup, Page, PaginatorButton

from utils import seconds_to_duration


class QueuePaginator(pg.Paginator):
    def __init__(self, player: wavelink.Player, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.player = player

    async def update(
        self,
        pages: None
        | (
            list[PageGroup]
            | list[Page]
            | list[str]
            | list[list[discord.Embed] | discord.Embed]
        ) = None,
        show_disabled: bool | None = None,
        show_indicator: bool | None = None,
        show_menu: bool | None = None,
        author_check: bool | None = None,
        menu_placeholder: str | None = None,
        disable_on_timeout: bool | None = None,
        use_default_buttons: bool | None = None,
        default_button_row: int | None = None,
        loop_pages: bool | None = None,
        custom_view: discord.ui.View | None = None,
        timeout: float | None = None,
        custom_buttons: list[PaginatorButton] | None = None,
        trigger_on_display: bool | None = None,
        interaction: discord.Interaction | None = None,
    ):
        if len(self.player.queue) >= 1:
            queue_pages = []
            tracks = self.player.queue
            for i in range(0, len(tracks), 5):
                page = tracks[i:i + 5]
                embed = discord.Embed(
                    title="Очередь треков",
                    description=f"**Сейчас играет**\n"
                                f"Название: **{self.player.current.title}**\n"
                                f"Автор: **{self.player.current.author}**\n"
                                f"Продолжительность: **{seconds_to_duration(self.player.current.length // 1000)}**",
                    color=discord.Color.blurple()
                )
                embed.set_image(url="https://assets.shandy-dev.ru/playlist_fununa-nun_banner.webp")
                embed.set_footer(text=f"Всего треков в очереди: {len(tracks)}")
                for index, track in enumerate(page):
                    embed.add_field(
                        name=f"Трек {self.player._queue.index(track) + 1}",
                        value=f"Название: **{track.title}**\nАвтор: **{track.author}**\nПродолжительность: **{seconds_to_duration(track.length // 1000)}**",
                        inline=False
                    )
                queue_pages.append(embed)
            self.pages = queue_pages
        else:
            embed = discord.Embed(title="Очередь пуста", color=discord.Color.red())
            if self.player.current:
                embed.description = f"**Сейчас играет**\n" \
                                    f"Название: **{self.player.current.title}**\n" \
                                    f"Автор: **{self.player.current.author}**\n" \
                                    f"Продолжительность: **{seconds_to_duration(self.player.current.length // 1000)}**"
            self.pages = [embed]
        await super().update(
            pages=pages,
            show_disabled=show_disabled,
            show_indicator=show_indicator,
            show_menu=show_menu,
            author_check=author_check,
            menu_placeholder=menu_placeholder,
            disable_on_timeout=disable_on_timeout,
            use_default_buttons=use_default_buttons,
            default_button_row=default_button_row,
            loop_pages=loop_pages,
            custom_view=custom_view,
            timeout=timeout,
            custom_buttons=custom_buttons,
            trigger_on_display=trigger_on_display,
            interaction=interaction
        )
