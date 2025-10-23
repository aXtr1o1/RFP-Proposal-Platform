import os

class CacheManager:
    """Tracks in-memory buffers and temp files for cleanup."""

    def __init__(self):
        self.memory_buffers = {}
        self.temp_files = []

    def add_buffer(self, key: str, data: bytes):
        self.memory_buffers[key] = data

    def get_buffer(self, key: str):
        return self.memory_buffers.get(key)

    def add_temp_file(self, path: str):
        if path not in self.temp_files:
            self.temp_files.append(path)

    def cleanup(self):
        for path in self.temp_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        self.temp_files.clear()
        self.memory_buffers.clear()
