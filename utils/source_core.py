import os
import winreg
from pathlib import Path

def find_steam_game_path() -> Path | None:
    """
    Ищет аудио-папку DDNet через реестр Steam или по стандартным путям на дисках C, D, E.
    """
    sub_path = "steamapps/common/DDraceNetwork/ddnet/data/audio"
    
    try:
        hkey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(hkey, "SteamPath")
        winreg.CloseKey(hkey)
        
        registry_path = Path(steam_path) / sub_path
        if registry_path.exists():
            print(f"[CORE] Найдено через реестр Steam: {registry_path}")
            return registry_path
    except Exception:
        pass

    program_files = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    
    check_paths = [
        Path(program_files) / "Steam" / sub_path,
        Path(r"C:/SteamLibrary") / sub_path,
        Path(r"D:/SteamLibrary") / sub_path,
        Path(r"D:/Steam") / sub_path,
        Path(r"E:/SteamLibrary") / sub_path,
        Path(r"E:/Steam") / sub_path,
    ]

    for path in check_paths:
        if path.exists():
            print(f"[CORE] Найдено по стандартному пути: {path}")
            return path

    return None

def scan_audio_files(base_path: Path, extension: str = ".wv") -> list[Path]:
    """Сканирует папку и возвращает список файлов .wv"""
    if not base_path or not base_path.exists():
        return []
    return sorted(list(base_path.glob(f"*{extension}")))