import flet as ft


class RotateBadge(ft.Container):
    """Бейдж-индикатор текущей ориентации окна."""

    def __init__(self, portrait_mode: bool = False):
        super().__init__()
        self._portrait = portrait_mode

        self.padding = ft.Padding.symmetric(horizontal=8, vertical=6)
        self.border_radius = 20

        icon = ft.Icons.SCREEN_LOCK_PORTRAIT if portrait_mode else ft.Icons.SCREEN_LOCK_LANDSCAPE
        label = "Portrait" if portrait_mode else "Landscape"
        color = ft.Colors.PURPLE_400 if portrait_mode else ft.Colors.TEAL_400

        self.content = ft.Row(
            [
                ft.Icon(icon, size=16, color=color),
                ft.Text(label, size=11, weight=ft.FontWeight.BOLD, color=color),
            ],
            spacing=4
        )
        self.bgcolor = ft.Colors.with_opacity(0.12, color)
        self.tooltip = "Current orientation" if portrait_mode else "Current orientation"
