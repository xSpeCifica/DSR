import threading
import time
import soundfile as sf
import sounddevice as sd
import numpy as np
import subprocess
import tempfile
from pathlib import Path


class AudioPlayerEngine:
    def __init__(self, filepath, speed=1.0, start_sec=0.0, end_sec=None, volume=1.0, on_position_changed=None, on_finished=None):
        self.filepath = filepath
        self.speed = speed
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.volume = max(0.0, min(2.0, volume))

        self.on_position_changed = on_position_changed
        self.on_finished = on_finished

        self.is_playing = False
        self.is_paused = False
        self.position = 0
        self.data = None
        self.samplerate = 44100
        self._lock = threading.Lock()
        self._thread = None
        self._stream = None

    def load(self):
        print(f"\n[ENGINE] Загрузка файла плеером...")
        try:
            from utils.ffmpeg_core import decode_to_temporary_wav

            target_path = decode_to_temporary_wav(self.filepath)

            self.data, self.samplerate = sf.read(target_path, dtype='float32')
            if len(self.data.shape) == 1:
                self.data = self.data.reshape(-1, 1)

            self.position = int(self.start_sec * self.samplerate)
            self.position = max(0, min(self.position, len(self.data) - 1))

            if target_path != str(Path(self.filepath).resolve()):
                Path(target_path).unlink(missing_ok=True)
                print(f"[ENGINE] Временный WAV удален из кэша, данные зафиксированы в RAM.")

            print(f"[ENGINE] Файл успешно загружен в буфер плеера. Длина сэмплов: {len(self.data)}")
            return True

        except Exception as e:
            print(f"[ENGINE] Критическая ошибка загрузки трека в плеер: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _play_loop(self):
        if not self.load():
            if self.on_finished:
                self.on_finished()
            return

        self.is_playing = True
        self.is_paused = False

        try:
            channels = self.data.shape[1]
            end_sample = int(self.end_sec * self.samplerate) if self.end_sec else len(self.data)

            def callback(outdata, frames, time_info, status):
                with self._lock:
                    if not self.is_playing:
                        raise sd.CallbackStop()

                    if self.is_paused:
                        outdata[:] = 0
                        return

                    if self.speed == 1.0:
                        indices = np.arange(self.position, self.position + frames)
                    else:
                        indices = np.linspace(self.position, self.position + frames * self.speed, frames, endpoint=False)

                    indices = indices.astype(np.int32)
                    valid = (indices >= 0) & (indices < len(self.data)) & (indices < end_sample)

                    outdata[:] = 0
                    if np.any(valid):
                        valid_indices = indices[valid]
                        outdata[:len(valid_indices)] = self.data[valid_indices] * self.volume

                    self.position = int(indices[-1]) + 1 if len(indices) > 0 else self.position

                    if self.position >= end_sample or self.position >= len(self.data):
                        self.is_playing = False
                        raise sd.CallbackStop()

                    if self.on_position_changed:
                        pos_sec = self.position / self.samplerate
                        self.on_position_changed(pos_sec)

            with sd.OutputStream(
                samplerate=self.samplerate,
                channels=channels,
                dtype='float32',
                callback=callback,
                blocksize=1024
            ) as stream:
                self._stream = stream
                while self.is_playing:
                    time.sleep(0.02)

        except Exception as e:
            print(f"Ошибка в потоке плеера: {e}")
        finally:
            self.is_playing = False
            self._stream = None
            if self.on_finished:
                self.on_finished()

    def start(self):
        with self._lock:
            if self.is_playing:
                return
            self.is_playing = True
            self._thread = threading.Thread(target=self._play_loop, daemon=True)
            self._thread.start()

    def pause(self):
        with self._lock:
            self.is_paused = not self.is_paused
        return self.is_paused

    def stop(self, timeout: float = 0.5):
        """Stop playback immediately and wait for the thread to finish."""
        with self._lock:
            was_playing = self.is_playing
            self.is_playing = False

        # Force-close the audio stream to immediately stop callback
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        # Wait for the thread to actually finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        self._thread = None

    def set_speed(self, speed):
        with self._lock:
            self.speed = max(0.25, min(2.0, speed))

    def set_volume(self, volume):
        with self._lock:
            self.volume = max(0.0, min(2.0, volume))

    def seek(self, sec: float):
        with self._lock:
            if self.data is not None and self.samplerate > 0:
                self.position = int(sec * self.samplerate)
                self.position = max(0, min(self.position, len(self.data) - 1))