import asyncio
from pathlib import Path
import flet as ft
from utils.source_core import find_steam_game_path, scan_audio_files
from utils.audio_engine import AudioPlayerEngine
from utils.ffmpeg_core import get_audio_duration
from utils.i18n import t


class SourceAudioZone(ft.Container):
    def __init__(
        self,
        portrait_mode: bool = False,
        selected_path: Path | None = None,
        audio_files: list[Path] | None = None,
        current_index: int = 0,
    ):
        self._portrait = portrait_mode

        # ── Dimensions ──
        zone_width = 520 if portrait_mode else 650
        options_height = 160 if portrait_mode else 250
        search_width = 280 if portrait_mode else 300

        super().__init__(width=zone_width)

        self.selected_path = selected_path
        self.audio_files: list[Path] = list(audio_files) if audio_files else []
        self.current_index = current_index

        self.player = None
        self.is_playing = False
        self._player_lock = asyncio.Lock()

        self.title_text = ft.Text(
            t("source_zone.title"),
            size=14,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.PINK_400
        )

        self.search_input = ft.TextField(
            hint_text=t("source_zone.search_hint"),
            height=38,
            text_size=14,
            border_radius=8,
            border_color=ft.Colors.PINK_700,
            focused_border_color=ft.Colors.PINK_400,
            on_change=self.handle_search_change
        )

        self.options_column = ft.Column(
            scroll=ft.ScrollMode.ADAPTIVE,
            height=options_height,
            spacing=3
        )

        self.dropdown_label = ft.Text(
            t("source_zone.dropdown_hint"),
            size=13,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        # ── Popup menu: single PopupMenuItem with search + list inside ──
        self.file_picker_menu = ft.PopupMenuButton(
            content=ft.Container(
                content=ft.Row([
                    self.dropdown_label,
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, color=ft.Colors.PINK_400, size=20)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                height=36,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.PINK_400)),
                border_radius=8,
                padding=ft.Padding.symmetric(horizontal=10),
                bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.WHITE),
            ),
            menu_position=ft.PopupMenuPosition.UNDER,
            expand=True,
            items=[
                ft.PopupMenuItem(
                    content=ft.Column([
                        ft.Container(
                            content=self.search_input,
                            padding=ft.Padding.only(top=6, left=6, right=6, bottom=2),
                            width=search_width
                        ),
                        ft.Divider(height=1, thickness=1, color=ft.Colors.with_opacity(0.1, ft.Colors.PINK_100)),
                        ft.Container(
                            content=self.options_column,
                            padding=ft.Padding.only(left=6, right=6, bottom=6)
                        )
                    ], spacing=3)
                )
            ]
        )

        self.duration_text = ft.Text(
            "00:00.000",
            size=12,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.PINK_700,
        )

        self.play_btn = ft.IconButton(
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            icon_color=ft.Colors.PINK_400,
            icon_size=24,
            width=36,
            height=36,
            padding=0,
            on_click=self.toggle_preview
        )

        self.counter_text = ft.Text(
            "0 / 0",
            size=12,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.PINK_700,
        )

        self.nav_row = ft.Row([
            ft.IconButton(
                icon=ft.Icons.KEYBOARD_ARROW_LEFT_ROUNDED,
                icon_color=ft.Colors.PINK_300,
                icon_size=20,
                width=28,
                height=28,
                padding=0,
                on_click=self.prev_sound
            ),
            self.counter_text,
            ft.IconButton(
                icon=ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED,
                icon_color=ft.Colors.PINK_300,
                icon_size=20,
                width=28,
                height=28,
                padding=0,
                on_click=self.next_sound
            ),
        ], spacing=2, alignment=ft.MainAxisAlignment.CENTER)

        # ── Init view ──
        self.init_view = ft.Container(
            height=46,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.PINK_500)),
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.WHITE),
            padding=ft.Padding.symmetric(horizontal=12),
            content=ft.Row([
                ft.Text(t("source_zone.placeholder"), size=13, opacity=0.8),
                ft.Row([
                    ft.TextButton(
                        t("source_zone.steam_btn"),
                        on_click=self.handle_steam,
                        style=ft.ButtonStyle(color=ft.Colors.PINK_200)
                    ),
                    ft.ElevatedButton(
                        t("source_zone.pick_folder"),
                        on_click=self.handle_picker,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PINK_600),
                        color=ft.Colors.PINK_100,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=6),
                            elevation=0
                        )
                    )
                ], spacing=6)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

        # ── Active view: portrait = compact column layout ──
        if portrait_mode:
            self.active_view = ft.Container(
                visible=False,
                bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
                padding=ft.Padding.symmetric(horizontal=6, vertical=5),
                border_radius=10,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                content=ft.Column([
                    ft.Row([
                        self.play_btn,
                        ft.Container(content=self.file_picker_menu, expand=True),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
                    ft.Row([
                        ft.Container(
                            content=self.duration_text,
                            padding=ft.Padding.symmetric(horizontal=4)
                        ),
                        ft.Container(content=self.nav_row, padding=ft.Padding.only(left=4))
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=3)
            )
        else:
            self.active_view = ft.Container(
                visible=False,
                bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
                padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                border_radius=10,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                content=ft.Row([
                    self.play_btn,
                    self.file_picker_menu,
                    ft.Container(content=self.duration_text, padding=ft.Padding.symmetric(horizontal=10)),
                    ft.VerticalDivider(width=1, thickness=1, color=ft.Colors.with_opacity(0.15, ft.Colors.PINK_100)),
                    ft.Container(content=self.nav_row, padding=ft.Padding.only(left=5))
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
            )

        self.content = ft.Column([
            self.title_text,
            self.init_view,
            self.active_view
        ], spacing=6)

        # Restore UI state if data was passed in
        if self.audio_files:
            self.rebuild_options_list("")
            self._update_ui_state()

    def format_time(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{minutes:02d}:{secs:02d}.{millis:03d}"

    def rebuild_options_list(self, search_text: str = ""):
        search_text = search_text.lower()
        items = []

        for idx, file in enumerate(self.audio_files):
            if search_text and search_text not in file.name.lower():
                continue

            is_selected = (idx == self.current_index)

            items.append(
                ft.Container(
                    content=ft.Text(
                        file.name,
                        size=13,
                        color=ft.Colors.WHITE if is_selected else ft.Colors.GREY_900,
                        weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
                        overflow=ft.TextOverflow.ELLIPSIS
                    ),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                    border_radius=6,
                    bgcolor=ft.Colors.PINK_600 if is_selected else ft.Colors.TRANSPARENT,
                    alignment=ft.Alignment.CENTER_LEFT,
                    on_click=lambda e, index=idx: self.page.run_task(self._handle_item_click, index)
                )
            )

        self.options_column.controls = items

    async def _handle_item_click(self, index: int):
        """Handle file selection: close menu + select file."""
        try:
            self.file_picker_menu.close()
        except Exception:
            pass
        await self.handle_file_selected(index)

    async def handle_search_change(self, e):
        self.rebuild_options_list(e.control.value)
        self.file_picker_menu.update()

    async def handle_file_selected(self, index: int):
        async with self._player_lock:
            if self.is_playing:
                await self._stop_preview_locked()

            self.current_index = index
            self._update_ui_state()
            self.update()
            await self._start_preview_locked()

    def _update_ui_state(self):
        if self.audio_files:
            current_file = self.audio_files[self.current_index]

            self.dropdown_label.value = current_file.name
            self.counter_text.value = f"{self.current_index + 1}/{len(self.audio_files)}"

            duration = get_audio_duration(current_file)
            self.duration_text.value = self.format_time(duration)

            self.rebuild_options_list(self.search_input.value or "")

            self.init_view.visible = False
            self.active_view.visible = True
        else:
            self.dropdown_label.value = t("source_zone.dropdown_hint")
            self.counter_text.value = "0/0"
            self.duration_text.value = "00:00.000"
            self.options_column.controls = []
            self.init_view.visible = True
            self.active_view.visible = False

    async def handle_steam(self, e):
        print("[SOURCE] Запуск автопоиска...")
        detected_path = find_steam_game_path()

        if detected_path:
            self.selected_path = detected_path
            self.audio_files = scan_audio_files(detected_path, extension=".wv")
            self.current_index = 0
            self._update_ui_state()
        else:
            print("[SOURCE] Папка не найдена автоматически.")
            e.control.text = t("source_zone.not_found")
            e.control.color = ft.Colors.RED_400
            self.update()
            await asyncio.sleep(2)
            e.control.text = t("source_zone.steam_btn")
            e.control.color = ft.Colors.PINK_200

        self.update()

    async def handle_picker(self, e):
        folder_path = await ft.FilePicker().get_directory_path(
            dialog_title=t("dialog.pick_source")
        )

        if folder_path:
            self.selected_path = Path(folder_path)
            self.audio_files = scan_audio_files(self.selected_path, extension=".wv")
            self.current_index = 0
            self._update_ui_state()
            self.update()

    async def next_sound(self, e):
        async with self._player_lock:
            if self.audio_files:
                if self.is_playing:
                    await self._stop_preview_locked()
                self.current_index = (self.current_index + 1) % len(self.audio_files)
                self._update_ui_state()
                self.update()

    async def prev_sound(self, e):
        async with self._player_lock:
            if self.audio_files:
                if self.is_playing:
                    await self._stop_preview_locked()
                self.current_index = (self.current_index - 1) % len(self.audio_files)
                self._update_ui_state()
                self.update()

    async def toggle_preview(self, e):
        async with self._player_lock:
            if self.is_playing:
                await self._stop_preview_locked()
            else:
                await self._start_preview_locked()

    async def _start_preview_locked(self):
        """Must be called with _player_lock held."""
        if not self.audio_files:
            return
        # Stop any existing player first
        if self.player:
            self.player.stop()
            self.player = None

        target_file = self.audio_files[self.current_index]
        self.player = AudioPlayerEngine(
            filepath=str(target_file),
            speed=1.0,
            start_sec=0.0,
            end_sec=None,
            on_finished=lambda: self.page.run_task(self.handle_playback_finished)
        )
        self.play_btn.icon = ft.Icons.STOP_ROUNDED
        self.is_playing = True
        self.update()
        self.player.start()

    async def _stop_preview_locked(self):
        """Must be called with _player_lock held."""
        if self.player:
            self.player.stop()
            self.player = None
        self.play_btn.icon = ft.Icons.PLAY_ARROW_ROUNDED
        self.is_playing = False
        self.update()

    async def start_preview(self):
        async with self._player_lock:
            await self._start_preview_locked()

    async def stop_preview(self):
        async with self._player_lock:
            await self._stop_preview_locked()

    async def handle_playback_finished(self):
        self.play_btn.icon = ft.Icons.PLAY_ARROW_ROUNDED
        self.is_playing = False
        self.update()