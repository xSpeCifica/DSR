import os
import time
from pathlib import Path
import flet as ft
from utils.audio_engine import AudioPlayerEngine
from utils.ffmpeg_core import get_audio_duration
from utils.waveform_core import generate_waveform_image
from utils.i18n import t

class ReplaceAudioZone(ft.Container):
    def __init__(
        self,
        portrait_mode: bool = False,
        new_file_path: str | None = None,
        current_speed: float = 1.0,
        current_volume: float = 1.0,
        trim_start: float = 0.0,
        trim_end: float = 0.0,
    ):
        self._portrait = portrait_mode

        # ── Dimensions based on orientation ──
        zone_width = 520 if portrait_mode else 650
        wf_width = 490 if portrait_mode else 602
        wf_height = 42
        slider_width = 160 if portrait_mode else 180

        super().__init__(width=zone_width)

        self.new_file_path = new_file_path
        self.track_duration = 0.0
        self.samplerate = 44100
        self.current_speed = current_speed
        self.current_volume = current_volume

        self.player = None
        self.is_playing = False
        self.file_picker = None

        self.waveform_width = wf_width
        self.waveform_height = wf_height
        self._slider_padding = 10 if portrait_mode else 12
        self._last_ph_update = 0.0
        self._saved_trim_start = trim_start
        self._saved_trim_end = trim_end

        self.title_text = ft.Text(
            t("replace_zone.title"),
            weight=ft.FontWeight.W_600,
            size=14,
            color=ft.Colors.BLUE_800
        )

        self.track_title = ft.Text(
            "Выберите файл...",
            weight=ft.FontWeight.BOLD,
            size=13,
            color=ft.Colors.GREY_900,
            overflow=ft.TextOverflow.ELLIPSIS
        )

        self.trim_info = ft.Text(
            "хуй",
            size=12,
            weight=ft.FontWeight.W_500,
            color=ft.Colors.LIGHT_BLUE_700
        )

        self.start_time_text = ft.Text("00:00.000", size=11, color=ft.Colors.BLUE_700)
        self.end_time_text = ft.Text("00:00.000", size=11, color=ft.Colors.BLUE_700)

        self.play_btn = ft.IconButton(
            icon=ft.Icons.PLAY_ARROW_ROUNDED,
            icon_color=ft.Colors.LIGHT_BLUE_600,
            icon_size=24,
            width=36,
            height=36,
            padding=0,
            on_click=self.toggle_preview
        )

        self.init_view = ft.Container(
            height=44,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.BLUE_400)),
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.WHITE),
            padding=ft.Padding.symmetric(horizontal=12),
            content=ft.Row([
                ft.Text(t("replace_zone.placeholder"), size=13, opacity=0.8),
                ft.ElevatedButton(
                    t("replace_zone.pick_file"),
                    on_click=self.open_file,
                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE_600),
                    color=ft.Colors.BLUE_800,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=6),
                        elevation=0
                    )
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

        self.trim_slider = ft.RangeSlider(
            min=0.0, max=1.0, start_value=0.0, end_value=1.0,
            inactive_color=ft.Colors.BLUE_100,
            active_color=ft.Colors.LIGHT_BLUE_500,
            on_change=self.handle_trim_change
        )

        self.speed_label = ft.Text("1.00x", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.LIGHT_BLUE_700)
        self.speed_slider = ft.Slider(
            width=slider_width, min=0.25, max=2.0, value=1.0,
            divisions=35,
            active_color=ft.Colors.LIGHT_BLUE_500,
            inactive_color=ft.Colors.BLUE_100,
            on_change=self.handle_speed_change
        )

        self.volume_label = ft.Text("100%", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.LIGHT_BLUE_700)
        self.volume_slider = ft.Slider(
            width=slider_width, min=0, max=200, value=100,
            divisions=20,
            active_color=ft.Colors.LIGHT_BLUE_500,
            inactive_color=ft.Colors.BLUE_100,
            on_change=self.handle_volume_change
        )

        self.waveform_image = ft.Image(
            width=self.waveform_width,
            height=self.waveform_height,
            fit="fill",
            src=""
        )

        self.waveform_overlay_left = ft.Container(
            left=0, top=0, width=0, height=self.waveform_height,
            bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.SURFACE_CONTAINER_HIGHEST)
        )
        self.waveform_overlay_right = ft.Container(
            left=self.waveform_width, top=0, width=0, height=self.waveform_height,
            bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.SURFACE_CONTAINER_HIGHEST)
        )
        self.waveform_line_start = ft.Container(
            left=0, top=0, width=2, height=self.waveform_height,
            bgcolor=ft.Colors.PINK_300,
            border_radius=1
        )
        self.waveform_line_end = ft.Container(
            left=self.waveform_width, top=0, width=2, height=self.waveform_height,
            bgcolor=ft.Colors.PINK_300,
            border_radius=1
        )
        self.waveform_playhead = ft.Container(
            left=0, top=0, width=2, height=self.waveform_height,
            bgcolor=ft.Colors.WHITE,
            visible=False,
            border_radius=1
        )

        inner_stack = ft.Stack(
            [
                ft.Container(
                    width=self.waveform_width,
                    height=self.waveform_height,
                    bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.PINK_400),
                    border_radius=8
                ),
                self.waveform_image,
                self.waveform_overlay_left,
                self.waveform_overlay_right,
                self.waveform_line_start,
                self.waveform_line_end,
                self.waveform_playhead,
                ft.GestureDetector(
                    content=ft.Container(
                        width=self.waveform_width,
                        height=self.waveform_height,
                        bgcolor=ft.Colors.TRANSPARENT
                    ),
                    on_tap_up=self.on_waveform_tap
                ),
            ],
            width=self.waveform_width,
            height=self.waveform_height,
        )

        self.waveform_stack = ft.Container(
            content=inner_stack,
            width=self.waveform_width + self._slider_padding * 2,
            padding=ft.Padding.symmetric(horizontal=self._slider_padding)
        )

        # ── Active view: portrait = compact stacked layout ──
        if portrait_mode:
            self.active_view = ft.Container(
                visible=False,
                padding=ft.Padding.symmetric(horizontal=6, vertical=5),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
                content=ft.Column([
                    ft.Row([
                        self.play_btn,
                        ft.Container(content=self.track_title, expand=True, padding=ft.Padding.only(left=4)),
                        ft.IconButton(
                            icon=ft.Icons.MORE_HORIZ,
                            icon_color=ft.Colors.BLUE_400,
                            icon_size=20,
                            tooltip="Выбрать другой файл",
                            on_click=self.open_file
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                    ft.Column([
                        self.waveform_stack,
                        ft.Container(
                            content=self.trim_slider,
                            margin=ft.Margin.symmetric(vertical=-4),
                            padding=ft.Padding.symmetric(horizontal=0),
                        ),
                    ], spacing=0),

                    ft.Row([
                        self.start_time_text,
                        self.trim_info,
                        self.end_time_text
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                    ft.Divider(height=1, thickness=1, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK)),

                    # Portrait: speed & volume stacked vertically, centered
                    ft.Row([
                        ft.Column([
                            ft.Text("Скорость:", size=10, color=ft.Colors.GREY_700),
                            self.speed_slider,
                            self.speed_label,
                        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Column([
                            ft.Text("Громкость:", size=10, color=ft.Colors.GREY_700),
                            self.volume_slider,
                            self.volume_label,
                        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ], alignment=ft.MainAxisAlignment.SPACE_AROUND)
                ], spacing=4)
            )
        else:
            self.active_view = ft.Container(
                visible=False,
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
                content=ft.Column([
                    ft.Row([
                        self.play_btn,
                        ft.Container(content=self.track_title, expand=True, padding=ft.Padding.only(left=5)),
                        ft.IconButton(
                            icon=ft.Icons.MORE_HORIZ,
                            icon_color=ft.Colors.BLUE_400,
                            icon_size=20,
                            tooltip="Выбрать другой файл",
                            on_click=self.open_file
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                    ft.Column([
                        self.waveform_stack,
                        ft.Container(
                            content=self.trim_slider,
                            margin=ft.Margin.symmetric(vertical=-4),
                            padding=ft.Padding.symmetric(horizontal=0),
                        ),
                    ], spacing=0),

                    ft.Row([
                        self.start_time_text,
                        self.trim_info,
                        self.end_time_text
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),

                    ft.Divider(height=1, thickness=1, color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK)),

                    ft.Row([
                        ft.Row([
                            ft.Text("Скорость:", size=11, color=ft.Colors.GREY_700),
                            self.speed_slider,
                            self.speed_label
                        ], spacing=10),
                        ft.Row([
                            ft.Text("Громкость:", size=11, color=ft.Colors.GREY_700),
                            self.volume_slider,
                            self.volume_label
                        ], spacing=10),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ], spacing=6)
            )

        self.content = ft.Column([
            self.title_text,
            self.init_view,
            self.active_view
        ], spacing=6)

        # Restore UI if file was passed in
        if self.new_file_path and os.path.exists(self.new_file_path):
            self._restore_file_state()

    def _restore_file_state(self):
        """Restore the UI state from a previously selected file (no dialog)."""
        self.track_title.value = os.path.basename(self.new_file_path)
        self.track_duration = get_audio_duration(self.new_file_path)

        self.trim_slider.max = self.track_duration if self.track_duration > 0 else 1.0
        self.trim_slider.start_value = self._saved_trim_start
        self.trim_slider.end_value = self._saved_trim_end if self._saved_trim_end > 0 else self.track_duration

        self.start_time_text.value = self.format_time(self.trim_slider.start_value)
        self.end_time_text.value = self.format_time(self.trim_slider.end_value)
        duration = self.trim_slider.end_value - self.trim_slider.start_value
        self.trim_info.value = (
            f"Обрезка: {self.format_time(self.trim_slider.start_value)} - "
            f"{self.format_time(self.trim_slider.end_value)} ({self.format_time(duration)})"
        )

        self.waveform_image.src = generate_waveform_image(
            self.new_file_path,
            width=self.waveform_width,
            height=self.waveform_height
        )

        # Apply overlays from saved trim values
        if self.track_duration > 0:
            start_px = int((self.trim_slider.start_value / self.track_duration) * self.waveform_width)
            end_px = int((self.trim_slider.end_value / self.track_duration) * self.waveform_width)
            self.waveform_overlay_left.width = start_px
            self.waveform_line_start.left = start_px
            self.waveform_overlay_right.left = end_px
            self.waveform_overlay_right.width = self.waveform_width - end_px
            self.waveform_line_end.left = end_px

        self.speed_slider.value = self.current_speed
        self.speed_label.value = f"{self.current_speed:.2f}x"

        vol_percent = int(self.current_volume * 100)
        self.volume_slider.value = vol_percent
        self.volume_label.value = f"{vol_percent}%"

        self.init_view.visible = False
        self.active_view.visible = True

    def format_time(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{minutes:02d}:{secs:02d}.{millis:03d}"

    async def handle_trim_change(self, e):
        start = self.trim_slider.start_value
        end = self.trim_slider.end_value
        duration = end - start

        self.trim_info.value = f"Обрезка: {self.format_time(start)} - {self.format_time(end)} ({self.format_time(duration)})"
        self.start_time_text.value = self.format_time(start)
        self.end_time_text.value = self.format_time(end)

        if self.track_duration > 0:
            start_px = int((start / self.track_duration) * self.waveform_width)
            end_px = int((end / self.track_duration) * self.waveform_width)
            self.waveform_overlay_left.width = start_px
            self.waveform_line_start.left = start_px
            self.waveform_overlay_right.left = end_px
            self.waveform_overlay_right.width = self.waveform_width - end_px
            self.waveform_line_end.left = end_px

        if self.is_playing:
            await self.stop_preview()

        self.update()

    async def handle_speed_change(self, e):
        self.current_speed = self.speed_slider.value
        self.speed_label.value = f"{self.current_speed:.2f}x"

        if self.is_playing and self.player:
            self.player.set_speed(self.current_speed)

        self.update()

    async def handle_volume_change(self, e):
        self.current_volume = self.volume_slider.value / 100.0
        self.volume_label.value = f"{int(self.volume_slider.value)}%"

        if self.is_playing and self.player:
            self.player.set_volume(self.current_volume)

        self.update()

    async def toggle_preview(self, e):
        if self.is_playing:
            await self.stop_preview()
        else:
            await self.start_preview()

    async def start_preview(self):
        if not self.new_file_path:
            return

        self.player = AudioPlayerEngine(
            filepath=self.new_file_path,
            speed=self.current_speed,
            volume=self.current_volume,
            start_sec=self.trim_slider.start_value,
            end_sec=self.trim_slider.end_value,
            on_position_changed=self.on_player_position_changed,
            on_finished=lambda: self.page.run_task(self.handle_playback_finished)
        )

        self.play_btn.icon = ft.Icons.STOP_ROUNDED
        self.is_playing = True
        self.waveform_playhead.visible = False
        self.update()

        self.player.start()

    async def stop_preview(self):
        if self.player:
            self.player.stop()
        self.play_btn.icon = ft.Icons.PLAY_ARROW_ROUNDED
        self.is_playing = False
        self.waveform_playhead.visible = False
        self.update()

    def on_player_position_changed(self, pos_sec):
        if not self.track_duration or not self.page:
            return

        now = time.time()
        if now - self._last_ph_update < 0.05:
            return
        self._last_ph_update = now

        px = int((pos_sec / self.track_duration) * self.waveform_width)
        self.page.run_task(self._update_playhead, px)

    async def _update_playhead(self, px):
        self.waveform_playhead.left = px
        self.waveform_playhead.visible = True
        self.update()

    async def handle_playback_finished(self):
        print("[UI] Заменяющий звук отыграл.")
        self.play_btn.icon = ft.Icons.PLAY_ARROW_ROUNDED
        self.is_playing = False
        self.waveform_playhead.visible = False
        self.update()

    async def on_waveform_tap(self, e):
        if not self.track_duration or not self.new_file_path:
            return
        pos = e.local_position
        if pos is None:
            return
        x = max(0, min(pos.x, self.waveform_width))
        seek_sec = (x / self.waveform_width) * self.track_duration

        if self.is_playing and self.player:
            self.player.seek(seek_sec)
            self.waveform_playhead.left = x
            self.waveform_playhead.visible = True
            self.update()

    async def open_file(self, e):
        print("[REPLACE] Открытие диалога выбора файла...")

        result = await ft.FilePicker().pick_files(
            dialog_title="Выберите заменяющий аудиофайл",
            allow_multiple=False,
            allowed_extensions=["mp3", "wav", "ogg", "flac", "wv"]
        )

        if not result:
            print("[REPLACE] Выбор файла отменен")
            return

        selected_file_path = result[0].path
        print(f"[REPLACE] Выбран файл: {selected_file_path}")

        if os.path.exists(selected_file_path):
            self.new_file_path = selected_file_path
            self.track_title.value = os.path.basename(selected_file_path)

            self.track_duration = get_audio_duration(selected_file_path)
            self.samplerate = 44100

            self.trim_slider.max = self.track_duration if self.track_duration > 0 else 1.0
            self.trim_slider.start_value = 0.0
            self.trim_slider.end_value = self.track_duration

            self.start_time_text.value = self.format_time(0.0)
            self.end_time_text.value = self.format_time(self.track_duration)
            self.trim_info.value = f"Обрезка: {self.format_time(0.0)} - {self.format_time(self.track_duration)} ({self.format_time(self.track_duration)})"

            self.waveform_image.src = generate_waveform_image(
                self.new_file_path,
                width=self.waveform_width,
                height=self.waveform_height
            )

            self.waveform_overlay_left.width = 0
            self.waveform_overlay_right.left = self.waveform_width
            self.waveform_overlay_right.width = 0
            self.waveform_line_start.left = 0
            self.waveform_line_end.left = self.waveform_width
            self.waveform_playhead.visible = False

            self.current_speed = 1.0
            self.speed_slider.value = 1.0
            self.speed_label.value = "1.00x"

            self.current_volume = 1.0
            self.volume_slider.value = 100
            self.volume_label.value = "100%"

            self.init_view.visible = False
            self.active_view.visible = True
            self.update()