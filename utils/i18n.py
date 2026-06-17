import json
import sys
from pathlib import Path
import ctypes
from utils.config import get_assets_dir

_translations = {}
_current_lang = 'en'


def _get_translations_path() -> Path | None:
    """Ищет translations.json: сначала в AppData, потом рядом со скриптом."""

    appdata = get_assets_dir() / 'translations.json'
    if appdata.exists():
        return appdata
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent.parent
    local = base / 'assets' / 'translations.json'
    if local.exists():
        return local
    return None


def _load_translations():
    global _translations
    path = _get_translations_path()
    if path:
        with open(path, 'r', encoding='utf-8') as f:
            _translations = json.load(f)
    else:
        _translations = {}


def t(key: str, **kwargs) -> str:
    """Возвращает перевод строки на текущем языке."""
    if not _translations:
        _load_translations()
    entry = _translations.get(key, {})
    text = entry.get(_current_lang, entry.get('en', key))
    return text.format(**kwargs) if kwargs else text


def set_lang(lang: str):
    global _current_lang
    _current_lang = lang


def get_lang() -> str:
    return _current_lang


def detect_system_lang() -> str:
    """Определяет язык интерфейса Windows. Возвращает 'ru' или 'en'."""
    try:
        if sys.platform == 'win32':
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if lang_id == 0x0419:
                return 'ru'
        return 'en'
    except Exception:
        return 'en'