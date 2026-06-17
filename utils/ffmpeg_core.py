import shutil, sys, os, io, zipfile, urllib.request, asyncio, json, subprocess, tempfile
from pathlib import Path
from utils.config import load_config
import flet as ft
import soundfile as sf

def find_ffmpeg() -> str | None:
    print("[CORE] Поиск FFmpeg...")
    ffmpeg_path = shutil.which('ffmpeg')
    ffplay_path = shutil.which('ffplay')
    if ffmpeg_path and ffplay_path:
        print(f"[CORE] Найдено в PATH: {ffmpeg_path}")
        return str(Path(ffmpeg_path).parent)

    cfg = load_config()
    saved_path = cfg.get('ffmpeg_dir', '')
    if saved_path:
        p = Path(saved_path)
        if (p / 'ffmpeg.exe').exists() and (p / 'ffplay.exe').exists():
            print(f"[CORE] Найдено в config.json: {saved_path}")
            return str(p)

    if sys.platform == 'win32':
        possible_paths = [
            Path(r'C:\ffmpeg\bin'),
            Path(r'C:\Program Files\ffmpeg\bin'),
            Path(r'C:\Program Files (x86)\ffmpeg\bin'),
            Path.home() / 'ffmpeg' / 'bin',
        ]
        for p in possible_paths:
            if (p / 'ffmpeg.exe').exists() and (p / 'ffplay.exe').exists():
                print(f"[CORE] Найдено в дефолтной папке: {p}")
                return str(p)

    print("[CORE] Найти FFmpeg не удалось.")
    return None

async def ensure_ffmpeg(status_text: ft.Text, progress_bar: ft.ProgressBar, page: ft.Page, on_progress_callback=None):
    print("[CORE ENGINE] Запущен процесс автоматической установки...")
    try:
        ffmpeg_dir = Path(r'C:\ffmpeg')
        bin_dir = ffmpeg_dir / 'bin'

        if (bin_dir / 'ffmpeg.exe').exists():
            print("[CORE ENGINE] Обнаружен существующий C:\\ffmpeg\\bin\\ffmpeg.exe. Отмена скачивания.")
            status_text.value = "FFmpeg уже установлен!"
            progress_bar.value = 1.0
            page.update()
            return str(bin_dir)

        url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
        print(f"[CORE ENGINE] Подключение к серверу: {url}")
        status_text.value = "Запуск скачивания FFmpeg..."
        progress_bar.value = 0.05
        page.update()

        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        print("[CORE ENGINE] Открытие URL-соединения...")
        with urllib.request.urlopen(req, timeout=300) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            print(f"[CORE ENGINE] Размер архива на сервере: {total_size / (1024*1024):.2f} MB")
            downloaded = 0
            chunk_size = 65536 
            data = io.BytesIO()

            print("[CORE ENGINE] Начат стриминг данных порциями (чанками)...")
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                data.write(chunk)
                downloaded += len(chunk)
                
                if total_size > 0:
                    percent = (downloaded / total_size) * 0.7 + 0.05
                    progress_bar.value = min(percent, 0.75)
                    
                    mb = downloaded / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    status_text.value = f"Скачивание FFmpeg: {mb:.1f} / {total_mb:.1f} MB"
                    
                    if on_progress_callback:
                        on_progress_callback(status_text.value, progress_bar.value)
                    else:
                        page.update()
                        
                    await asyncio.sleep(0.005)

            print(f"[CORE ENGINE] Загрузка завершена. Всего байт получено: {downloaded}")

        print("[CORE ENGINE] Начинаем распаковку zip-архива в памяти...")
        status_text.value = "Распаковка архива..."
        progress_bar.value = 0.80
        page.update()

        ffmpeg_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(data) as zf:
            print(f"[CORE ENGINE] Экстракт файлов в {ffmpeg_dir}...")
            zf.extractall(path=str(ffmpeg_dir))

        print("[CORE ENGINE] Поиск внутренней папки релиза...")
        extracted = None
        for item in ffmpeg_dir.iterdir():
            if item.is_dir() and item.name.startswith('ffmpeg-'):
                extracted = item
                print(f"[CORE ENGINE] Найдена папка релиза: {item.name}")
                break

        if extracted:
            bin_source = extracted / 'bin'
            if bin_source.exists():
                if bin_dir.exists():
                    print("[CORE ENGINE] Удаляем старую папку bin...")
                    shutil.rmtree(bin_dir)
                print("[CORE ENGINE] Переносим чистый bin наружу...")
                shutil.copytree(bin_source, bin_dir)
                print("[CORE ENGINE] Чистим мусорные папки релиза...")
                shutil.rmtree(extracted)

        progress_bar.value = 1.0
        if (bin_dir / 'ffmpeg.exe').exists():
            print("[CORE ENGINE] Успешная валидация! Файл ffmpeg.exe на месте.")
            status_text.value = "FFmpeg успешно установлен и готов к работе!"
            page.update()
            return str(bin_dir)
        else:
            print("[CORE ENGINE] КРИТИЧЕСКАЯ ОШИБКА: Файла ffmpeg.exe нет после распаковки.")
            status_text.value = "Ошибка при распаковке FFmpeg."
            page.update()
            return None

    except Exception as e:
        print(f"[CORE ENGINE] Исключение в процессе установки: {str(e)}")
        status_text.value = f"Ошибка установки FFmpeg: {str(e)}"
        progress_bar.value = 0.0
        page.update()
        return None
    
def get_audio_duration(file_path: str | Path) -> float:
    """
    Универсально определяет длительность любого аудиофайла
    Возвращает длительность в секундах (float). В случае полной неудачи вернет 180.0
    """
    clean_path = str(Path(file_path).resolve())
    
    try:
        info = sf.info(clean_path)
        print(f"[CORE] Длительность определена через soundfile: {info.duration} сек.")
        return float(info.duration)
    except Exception:
        print(f"[CORE] soundfile не справился с {Path(clean_path).name}. Пробуем ffprobe...")


    try:
        ffmpeg_dir = find_ffmpeg()
        if ffmpeg_dir:
            ffprobe_cmd = str(Path(ffmpeg_dir) / 'ffprobe.exe')
        else:
            ffprobe_cmd = 'ffprobe'

        cmd = [
            ffprobe_cmd, '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json', clean_path
        ]

        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=10, 
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        probe_data = json.loads(result.stdout)
        duration = float(probe_data['format']['duration'])
        print(f"[CORE] Длительность определена через ffprobe: {duration} сек.")
        return duration

    except Exception as e:
        print(f"[CORE] Не удалось определить длительность файла {Path(clean_path).name}: {e}")
        return 180.0 
    
def decode_to_temporary_wav(file_path: str | Path) -> str:
    clean_path = str(Path(file_path).resolve())
    
    if clean_path.lower().endswith('.wav'):
        return clean_path
        
    try:
        sf.info(clean_path)
        return clean_path
    except Exception:
        print(f"[CORE_DEBUG] soundfile ожидаемо не взял {Path(clean_path).name}. Начинаем конвертацию...")

    try:
        ffmpeg_dir = find_ffmpeg()
        if ffmpeg_dir:
            ffmpeg_binary = str(Path(ffmpeg_dir) / 'ffmpeg.exe')
            print(f"[CORE_DEBUG] Используем FFmpeg по пути: {ffmpeg_binary}")
        else:
            ffmpeg_binary = 'ffmpeg'
            print(f"[CORE_DEBUG] Папка FFmpeg не найдена в конфигах/дефолтах. Пробуем глобальный 'ffmpeg'...")
        

        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tf:
            temp_wav = tf.name
        

        cmd = [ffmpeg_binary, '-y', '-i', clean_path, '-ar', '48000', '-ac', '1', temp_wav]
        print(f"[CORE_DEBUG] Команда запуска: {cmd}")
        
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=15, 
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        print(f"[CORE_DEBUG] FFmpeg вернул код: {result.returncode}")
        
        if result.returncode == 0 and Path(temp_wav).exists():
            print(f"[CORE_DEBUG] Успех! Создан файл: {temp_wav} (Размер: {Path(temp_wav).stat().st_size} байт)")
            return temp_wav
        else:
            print(f"[CORE_DEBUG] КРИТ: FFmpeg завершился с ошибкой!")
            print(f"[CORE_DEBUG] СТДОУТ: {result.stdout}")
            print(f"[CORE_DEBUG] СТДЕРР: {result.stderr}")
            return clean_path
            
    except Exception as e:
        print(f"[CORE_DEBUG] Исключение внутри decode_to_temporary_wav: {e}")
        import traceback
        traceback.print_exc()
        return clean_path