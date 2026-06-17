from pathlib import Path
import sys
import flet as ft
from components.ui_source_zone import SourceAudioZone
from components.ui_replace_zone import ReplaceAudioZone
from utils.converter_core import process_audio_replace
from utils.config import load_config, save_config
from utils import i18n
from utils.updater import ensure_assets_async, check_for_update_sync
from utils.version import CURRENT_VERSION

is_converting = False

# ── Portrait dimensions ──
_P_WIDTH = 560
_P_HEIGHT = 650
_L_WIDTH = 900
_L_HEIGHT = 550


def main(page: ft.Page):
    page.window.width = _L_WIDTH
    page.window.height = _L_HEIGHT
    page.window.resizable = False
    page.window.maximizable = False
    page.title = "DSR"
    page.window.title_bar_hidden = True
    page.window.title_bar_buttons_hidden = True
    page.window.frameless = True
    page.window.shadow = False
    page.window.bgcolor = ft.Colors.TRANSPARENT
    page.bgcolor = ft.Colors.TRANSPARENT
    page.theme_mode = ft.ThemeMode.LIGHT

    if sys.platform == 'win32':
        icon_path = Path(__file__).parent / "assets" / "icon.ico"
        if not icon_path.exists():
            from utils.config import get_assets_dir
            icon_path = get_assets_dir() / 'icon.ico'
        if icon_path.exists():
            page.window.icon = str(icon_path)

    page.padding = 0
    page.spacing = 0

    page.theme = ft.Theme(
        color_scheme_seed=ft.Colors.PINK,
        font_family="Nunito",
    )
    page.fonts = {
        "Nunito": "https://raw.githubusercontent.com/google/fonts/main/ofl/nunito/Nunito[wght].ttf",
    }

    url_launcher = ft.UrlLauncher()

    has_update = False
    release_url = None
    update_btn_ref = None

    cfg = load_config()
    is_portrait = cfg.get('is_portrait', False)

    # ── Persistent state across rebuilds ──
    _state = {
        'source_path': None,
        'source_files': None,
        'source_index': 0,
        'replace_path': None,
        'replace_speed': 1.0,
        'replace_volume': 1.0,
        'trim_start': 0.0,
        'trim_end': 0.0,
    }

    def _capture_state(source_zone, replace_zone):
        """Capture current state before rebuilding UI."""
        _state['source_path'] = source_zone.selected_path
        _state['source_files'] = list(source_zone.audio_files) if source_zone.audio_files else None
        _state['source_index'] = source_zone.current_index
        _state['replace_path'] = replace_zone.new_file_path
        _state['replace_speed'] = replace_zone.current_speed
        _state['replace_volume'] = replace_zone.current_volume
        _state['trim_start'] = replace_zone.trim_slider.start_value
        _state['trim_end'] = replace_zone.trim_slider.end_value
        print(f"[STATE] Captured: src={_state['source_path']}, idx={_state['source_index']}, "
              f"repl={_state['replace_path']}, speed={_state['replace_speed']}, "
              f"vol={_state['replace_volume']}, trim={_state['trim_start']:.2f}-{_state['trim_end']:.2f}")

    async def open_update_url(e):
        if release_url:
            print(f"[APP] Открываем URL: {release_url}")
            await url_launcher.launch_url(release_url)

    async def check_updates():
        nonlocal has_update, release_url
        if CURRENT_VERSION == "dev":
            return
        try:
            async def _check():
                loop = __import__('asyncio').get_event_loop()
                return await loop.run_in_executor(None, check_for_update_sync)
            has_update, _, release_url = await _check()
            if has_update and update_btn_ref:
                update_btn_ref.visible = True
                update_btn_ref.update()
        except Exception as e:
            print(f"[APP] Ошибка в check_updates: {e}")

    async def rotation(e):
        """Переключает ориентацию окна между горизонтальной и вертикальной."""
        nonlocal is_portrait

        # Capture state from current UI before destroying it
        try:
            for control in page.controls:
                if isinstance(control, ft.Container) and control.content:
                    col = control.content
                    if isinstance(col, ft.Column) and len(col.controls) >= 2:
                        for child in col.controls:
                            if isinstance(child, ft.Container) and isinstance(child.content, ft.Column):
                                for zone in child.content.controls:
                                    if isinstance(zone, SourceAudioZone):
                                        _state['source_path'] = zone.selected_path
                                        _state['source_files'] = list(zone.audio_files) if zone.audio_files else None
                                        _state['source_index'] = zone.current_index
                                    elif isinstance(zone, ReplaceAudioZone):
                                        _state['replace_path'] = zone.new_file_path
                                        _state['replace_speed'] = zone.current_speed
                                        _state['replace_volume'] = zone.current_volume
                                        _state['trim_start'] = zone.trim_slider.start_value
                                        _state['trim_end'] = zone.trim_slider.end_value
        except Exception as ex:
            print(f"[STATE] Capture warning: {ex}")

        is_portrait = not is_portrait
        cfg = load_config()
        cfg['is_portrait'] = is_portrait
        save_config(cfg)

        page.window.width = _P_WIDTH if is_portrait else _L_WIDTH
        page.window.height = _P_HEIGHT if is_portrait else _L_HEIGHT

        page.clean()
        build_ui()
        page.update()

    def build_ui():
        global is_converting
        is_dev = (CURRENT_VERSION == "dev")
        print(f"[APP] build_ui: portrait={is_portrait}")

        # ── Build zones with captured state ──
        import copy
        src_files = copy.copy(_state['source_files']) if _state['source_files'] else None

        source_zone = SourceAudioZone(
            portrait_mode=is_portrait,
            selected_path=_state['source_path'],
            audio_files=src_files,
            current_index=_state['source_index'],
        )
        replace_zone = ReplaceAudioZone(
            portrait_mode=is_portrait,
            new_file_path=_state['replace_path'],
            current_speed=_state['replace_speed'],
            current_volume=_state['replace_volume'],
            trim_start=_state['trim_start'],
            trim_end=_state['trim_end'],
        )

        async def handle_window_close(e):
            await page.window.close()

        async def handle_window_minimize(e):
            page.window.minimized = True
            page.update()

        async def toggle_language(e):
            _capture_state(source_zone, replace_zone)
            new_lang = 'en' if i18n.get_lang() == 'ru' else 'ru'
            i18n.set_lang(new_lang)
            cfg = load_config()
            cfg['lang'] = new_lang
            save_config(cfg)
            page.clean()
            build_ui()
            page.update()

        dev_badge = ft.Container(
            visible=is_dev,
            content=ft.Text(
                "dev", size=12, color=ft.Colors.PINK_400,
                weight=ft.FontWeight.BOLD,
            ),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PINK_400),
            border_radius=6,
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            tooltip="Development build",
        )

        nonlocal update_btn_ref
        update_btn = ft.IconButton(
            icon=ft.Icons.UPDATE,
            icon_color=ft.Colors.RED_400,
            tooltip=i18n.t("header.update_tooltip"),
            visible=False,
            on_click=lambda e: page.run_task(open_update_url, e)
        )
        update_btn_ref = update_btn

        # ── Rotate icon: small rectangle showing the target orientation ──
        rotate_btn = ft.Container(
            content=ft.Container(
                width=16 if not is_portrait else 10,
                height=10 if not is_portrait else 16,
                border=ft.Border.all(2, ft.Colors.PURPLE_400),
                border_radius=3,
            ),
            tooltip=i18n.t("rotation.tooltip"),
            on_click=lambda e: page.run_task(rotation, e),
            padding=ft.Padding.all(4),
            alignment=ft.Alignment.CENTER,
        )

        header = ft.Container(
            content=ft.WindowDragArea(
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Text(i18n.t("app.title"), weight=ft.FontWeight.BOLD, size=18),
                                rotate_btn,
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            [
                                dev_badge,
                                update_btn,
                                ft.Container(width=6),
                                ft.IconButton(
                                    icon=ft.Icons.LANGUAGE,
                                    tooltip=i18n.t("header.language_tooltip"),
                                    icon_color=ft.Colors.BLUE_400,
                                    on_click=toggle_language
                                ),
                                ft.Container(
                                    width=3, height=24,
                                    bgcolor=ft.Colors.PURPLE_300,
                                    opacity=0.5,
                                    margin=ft.Margin.symmetric(horizontal=12)
                                ),
                                ft.Container(
                                    margin=ft.Margin.only(right=6),
                                    content=ft.Row(
                                        [
                                            ft.Container(
                                                width=18, height=18,
                                                shape=ft.BoxShape.CIRCLE,
                                                bgcolor="#FFBD2E",
                                                tooltip=i18n.t("header.minimize"),
                                                on_click=handle_window_minimize
                                            ),
                                            ft.Container(
                                                width=18, height=18,
                                                shape=ft.BoxShape.CIRCLE,
                                                bgcolor="#FF5F56",
                                                tooltip=i18n.t("header.close"),
                                                on_click=handle_window_close
                                            ),
                                        ],
                                        spacing=8
                                    )
                                )
                            ],
                            spacing=0,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=ft.BorderRadius.only(bottom_left=20, bottom_right=20),
            padding=ft.Padding.symmetric(horizontal=12),
            margin=ft.Margin.symmetric(horizontal=12),
            height=50,
        )

        async def on_replace_click(e):
            global is_converting
            if is_converting:
                return
            if not source_zone.audio_files or not source_zone.audio_files[source_zone.current_index]:
                show_snackbar(i18n.t("snackbar.error_source"))
                return
            if not replace_zone.new_file_path:
                show_snackbar(i18n.t("snackbar.error_replace"))
                return
            if source_zone.is_playing:
                await source_zone.stop_preview()
            if replace_zone.is_playing:
                await replace_zone.stop_preview()

            is_converting = True
            replace_btn_container.gradient = ft.LinearGradient(
                colors=[ft.Colors.AMBER, ft.Colors.ORANGE]
            )
            page.update()

            source_file = source_zone.audio_files[source_zone.current_index]
            try:
                success = process_audio_replace(
                    source_file_path=source_file,
                    new_file_path=replace_zone.new_file_path,
                    trim_start=replace_zone.trim_slider.start_value,
                    trim_end=replace_zone.trim_slider.end_value,
                    speed=replace_zone.current_speed,
                    volume=replace_zone.current_volume
                )
                if success:
                    replace_btn_container.gradient = ft.LinearGradient(
                        colors=[ft.Colors.GREEN_400, ft.Colors.GREEN_700]
                    )
                    page.update()
                    show_snackbar(i18n.t("snackbar.success", name=source_file.name))
                    source_zone._update_ui_state()
            except FileNotFoundError:
                show_snackbar(i18n.t("snackbar.error_ffmpeg"))
            except Exception as ex:
                show_snackbar(i18n.t("snackbar.error_convert", error=str(ex)))

            is_converting = False
            import asyncio
            await asyncio.sleep(3)
            replace_btn_container.gradient = ft.LinearGradient(
                begin=ft.Alignment.CENTER_LEFT,
                end=ft.Alignment.CENTER_RIGHT,
                colors=[ft.Colors.PINK_500, ft.Colors.LIGHT_BLUE_500]
            )
            page.update()

        def show_snackbar(text: str):
            page.show_dialog(
                ft.SnackBar(
                    content=ft.Text(text, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500),
                    bgcolor=ft.Colors.GREY_900,
                    behavior=ft.SnackBarBehavior.FLOATING,
                    duration=3000
                )
            )

        replace_btn_text = ft.Text(
            i18n.t("btn.replace"),
            weight=ft.FontWeight.BOLD, size=14, color=ft.Colors.PINK_600
        )

        replace_btn_container = ft.Container(
            width=480 if is_portrait else 650,
            height=48,
            border_radius=10,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.CENTER_LEFT,
                end=ft.Alignment.CENTER_RIGHT,
                colors=[ft.Colors.PINK_500, ft.Colors.LIGHT_BLUE_500]
            ),
            padding=1.5,
            on_click=lambda e: page.run_task(on_replace_click, e),
            content=ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=9,
                alignment=ft.Alignment.CENTER,
                content=ft.Row(
                    [replace_btn_text],
                    alignment=ft.MainAxisAlignment.CENTER
                )
            )
        )

        # ── Main layout ──
        layout_spacing = 10 if is_portrait else 14
        layout_padding = 10 if is_portrait else 15

        main_layout = ft.Container(
            content=ft.Column(
                [
                    source_zone,
                    replace_zone,
                    replace_btn_container,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=layout_spacing,
            ),
            padding=layout_padding,
            alignment=ft.Alignment.TOP_CENTER,
        )

        # ── Footer ──
        footer = ft.Container(
            content=ft.Text(
                "made by\nworld is cruel & oneover (design)",
                size=11 if not is_portrait else 10,
                color=ft.Colors.BLUE_GREY_400,
                weight=ft.FontWeight.W_400,
                text_align=ft.TextAlign.CENTER,
            ),
            alignment=ft.Alignment.CENTER,
            height=35,
            padding=ft.Padding.only(bottom=8),
        )

        # ── Shell: expand spacer pushes footer to bottom ──
        shell_content = ft.Column(
            [header, main_layout, ft.Container(expand=True), footer],
            spacing=0,
            expand=True,
        )

        shell = ft.Container(
            margin=ft.Margin.all(10) if is_portrait else ft.Margin.all(12),
            border_radius=12,
            bgcolor=ft.Colors.SURFACE,
            expand=True,
            content=shell_content,
        )
        page.add(shell)

        # ── Keyboard shortcuts ──
        def on_keyboard(e: ft.KeyboardEvent):
            """A/D and Arrow keys navigate source sounds. Space toggles preview."""
            key = e.key.upper()

            if key in ("A", "ARROW_LEFT"):
                if source_zone.audio_files:
                    page.run_task(source_zone.prev_sound, None)
            elif key in ("D", "ARROW_RIGHT"):
                if source_zone.audio_files:
                    page.run_task(source_zone.next_sound, None)
            elif key == " ":
                if source_zone.audio_files:
                    page.run_task(source_zone.toggle_preview, None)

        page.on_keyboard_event = on_keyboard

    # Loading indicator
    loading_indicator = ft.Container(
        content=ft.Column([
            ft.ProgressRing(width=32, height=32, color=ft.Colors.PINK_400),
            ft.Text(
                i18n.t("loading") if hasattr(i18n, "t") else "Загрузка...",
                size=14, color=ft.Colors.GREY_600
            )
        ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        ),
        alignment=ft.Alignment.CENTER,
        expand=True
    )
    page.add(loading_indicator)

    async def build_assets():
        sys_lang = i18n.detect_system_lang()
        i18n.set_lang(sys_lang)
        cfg = load_config()
        saved_lang = cfg.get('lang')
        if saved_lang:
            i18n.set_lang(saved_lang)
        else:
            cfg['lang'] = sys_lang
            save_config(cfg)

        nonlocal is_portrait
        is_portrait = cfg.get('is_portrait', False)
        page.window.width = _P_WIDTH if is_portrait else _L_WIDTH
        page.window.height = _P_HEIGHT if is_portrait else _L_HEIGHT

        assets_ok = await ensure_assets_async()
        if not assets_ok:
            local_assets = Path(__file__).parent / "assets" / "translations.json"
            if local_assets.exists():
                print("[INIT] Используем локальные assets (dev fallback)")
                assets_ok = True
            else:
                print("[INIT] Assets не найдены")

                async def _retry(e):
                    dlg.open = False
                    page.update()
                    await build_assets()

                async def _close(e):
                    dlg.open = False
                    page.update()
                    await page.window.close()

                dlg = ft.AlertDialog(
                    modal=True,
                    title=ft.Text(
                        "Ошибка запуска" if sys_lang == 'ru' else "Launch Error",
                        weight=ft.FontWeight.BOLD
                    ),
                    content=ft.Text(
                        "Не хватает ресурсов для запуска приложения. "
                        "Подключитесь к интернету для загрузки файлов с GitHub."
                        if sys_lang == 'ru' else
                        "Not enough resources. Please connect to the internet."
                    ),
                    actions=[
                        ft.TextButton(
                            "Повторить" if sys_lang == 'ru' else "Retry",
                            on_click=lambda e: page.run_task(_retry, e)
                        ),
                        ft.TextButton(
                            "Закрыть" if sys_lang == 'ru' else "Close",
                            on_click=lambda e: page.run_task(_close, e)
                        ),
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                page.overlay.append(dlg)
                dlg.open = True
                page.update()
                return

        page.remove(loading_indicator)
        build_ui()
        page.update()

        if CURRENT_VERSION != "dev":
            page.run_task(check_updates)

    page.run_task(build_assets)


ft.run(main)