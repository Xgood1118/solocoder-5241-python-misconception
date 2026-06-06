import json
import os
from typing import List, Dict, Optional, Type, TypeVar
from pathlib import Path

T = TypeVar('T')


class JSONStorage:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self._files = {
            "students": self.data_dir / "students.json",
            "knowledge_points": self.data_dir / "knowledge_points.json",
            "mistakes": self.data_dir / "mistakes.json",
        }
        for f in self._files.values():
            if not f.exists():
                f.write_text("[]", encoding="utf-8")

    def _read_all(self, key: str) -> List[Dict]:
        file_path = self._files[key]
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_all(self, key: str, data: List[Dict]):
        file_path = self._files[key]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_all(self, key: str, model: Type[T]) -> List[T]:
        data = self._read_all(key)
        return [model(**item) for item in data]

    def get_by_id(self, key: str, model: Type[T], item_id: str) -> Optional[T]:
        data = self._read_all(key)
        for item in data:
            if item.get("id") == item_id:
                return model(**item)
        return None

    def add(self, key: str, item) -> None:
        data = self._read_all(key)
        data.append(item.model_dump())
        self._write_all(key, data)

    def update(self, key: str, item_id: str, update_data: Dict) -> bool:
        data = self._read_all(key)
        for i, item in enumerate(data):
            if item.get("id") == item_id:
                data[i].update(update_data)
                self._write_all(key, data)
                return True
        return False

    def delete(self, key: str, item_id: str) -> bool:
        data = self._read_all(key)
        new_data = [item for item in data if item.get("id") != item_id]
        if len(new_data) != len(data):
            self._write_all(key, new_data)
            return True
        return False


storage = JSONStorage()
