"""
ScrollNote - Storage Module
Handles Note data structures, JSON persistence, settings, and atomic file writes.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_SETTINGS: Dict[str, Any] = {
    "autostart": False,
    "default_speed": 1.5,
    "font_family": "Segoe UI",
    "font_size": 14,
    "opacity": 0.95,
    "always_on_top": True,
    "theme": "dark",
    "hotkey": "Ctrl+Alt+S",
    "widget_geometry": {"x": 100, "y": 100, "size": 280},
    "widget_visible": True,
}

WELCOME_NOTE_TITLE = "🌟 Chào mừng bạn đến với ScrollNote!"
WELCOME_NOTE_CONTENT = """Chào mừng bạn đến với ScrollNote - Tiện ích ghi chú và cuộn chữ thông minh trên màn hình!

✨ CÁC TÍNH NĂNG NỔI BẬT:
1. Cuộn văn bản tự động: Xem ghi chú, nhắc việc, lời nhắc ôn tập hoặc kịch bản chạy mượt mà ngay trên màn hình.
2. Điều chỉnh tốc độ cuộn: Dễ dàng tăng giảm tốc độ cuộn phù hợp với nhịp đọc của bạn.
3. Ghim trên màn hình: Cửa sổ ghi chú có thể ghim luôn nổi trên các ứng dụng khác (Always on Top) và chỉnh độ trong suốt.
4. Quản lý nhiều ghi chú: Tạo, sửa, xóa, tìm kiếm và chuyển đổi ghi chú đang kích hoạt tức thì.
5. Khởi động cùng Windows: Tự động mở ghi chú của bạn ngay khi bật máy tính.

💡 MẸO SỬ DỤNG NHANH:
- Nhấn đúp hoặc dùng menu để bật/tắt chế độ cuộn tự động.
- Dùng thanh trượt tốc độ để tìm tốc độ đọc thoải mái nhất.
- Bạn có thể chỉnh sửa ghi chú này hoặc tạo ghi chú mới bất kỳ lúc nào!

Chúc bạn có những trải nghiệm làm việc và học tập hiệu quả với ScrollNote! 🚀
"""


@dataclass
class Note:
    """Represents a single note item."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Ghi chú mới"
    content: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = False
    speed: float = 1.5
    color: str = "#FFF8E1"
    font_size: int = 14
    opacity: float = 0.95

    def to_dict(self) -> Dict[str, Any]:
        """Convert Note instance to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Note:
        """Create Note instance from dictionary, handling missing or extra keys."""
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        # Ensure correct types
        if "speed" in filtered:
            try:
                filtered["speed"] = float(filtered["speed"])
            except (ValueError, TypeError):
                filtered["speed"] = 40.0
        if "is_active" in filtered:
            filtered["is_active"] = bool(filtered["is_active"])
        if "font_size" in filtered:
            try:
                filtered["font_size"] = int(filtered["font_size"])
            except (ValueError, TypeError):
                filtered["font_size"] = 14
        if "opacity" in filtered:
            try:
                filtered["opacity"] = float(filtered["opacity"])
            except (ValueError, TypeError):
                filtered["opacity"] = 0.95
        return cls(**filtered)


class NotesManager:
    """
    Manages loading, saving, querying, and updating notes and settings.
    Guarantees atomic file persistence to prevent corruption.
    """

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            # Default to d:\ScrollNote\notes.json or local dir notes.json
            base_dir = Path(__file__).resolve().parent
            self.storage_path = Path("d:/ScrollNote/notes.json")
            if not self.storage_path.parent.exists():
                try:
                    self.storage_path.parent.mkdir(parents=True, exist_ok=True)
                except Exception:
                    self.storage_path = base_dir / "notes.json"
        else:
            self.storage_path = Path(storage_path)

        self._notes: List[Note] = []
        self._settings: Dict[str, Any] = dict(DEFAULT_SETTINGS)

        self._ensure_storage_dir()
        self.load()

    def _ensure_storage_dir(self) -> None:
        """Ensure the directory holding notes.json exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _create_default_data(self) -> None:
        """Populate with a warm default welcome note and default settings."""
        welcome_note = Note(
            id=str(uuid.uuid4()),
            title=WELCOME_NOTE_TITLE,
            content=WELCOME_NOTE_CONTENT.strip(),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            is_active=True,
            speed=1.5,
            color="#FFF9C4",
            font_size=14,
            opacity=0.95,
        )
        self._notes = [welcome_note]
        self._settings = dict(DEFAULT_SETTINGS)

    def load(self) -> None:
        """Load notes and settings from disk. If not found or empty, init defaults."""
        if not self.storage_path.exists() or self.storage_path.stat().st_size == 0:
            self._create_default_data()
            self._save_to_disk()
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_notes = data.get("notes", [])
            self._notes = [Note.from_dict(n) for n in raw_notes]

            raw_settings = data.get("settings", {})
            self._settings = dict(DEFAULT_SETTINGS)
            self._settings.update(raw_settings)

            # If no notes exist in file, populate default
            if not self._notes:
                self._create_default_data()
                self._save_to_disk()
            else:
                # Ensure at least one note is active if none is active
                if not any(n.is_active for n in self._notes):
                    self._notes[0].is_active = True
                    self._save_to_disk()

        except Exception as e:
            # In case of JSON corruption, back up corrupted file and recreate defaults
            try:
                backup_path = self.storage_path.with_suffix(".corrupt.bak")
                if self.storage_path.exists():
                    shutil.copy2(self.storage_path, backup_path)
            except Exception:
                pass
            self._create_default_data()
            self._save_to_disk()

    def _save_to_disk(self) -> None:
        """
        Atomically write notes and settings to disk using a temporary file
        and atomic rename/replace.
        """
        self._ensure_storage_dir()
        payload = {
            "notes": [n.to_dict() for n in self._notes],
            "settings": self._settings,
            "version": "1.0",
        }

        dir_path = self.storage_path.parent
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(dir_path),
            delete=False,
            prefix="notes_tmp_",
            suffix=".json",
        )
        try:
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()

            # Atomically replace target file
            os.replace(temp_file.name, str(self.storage_path))
        except Exception as e:
            if os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                except Exception:
                    pass
            raise IOError(f"Failed to atomically write notes to {self.storage_path}: {e}")

    # ==================== Note Methods ====================

    def get_all_notes(self) -> List[Note]:
        """Return a copy of all notes."""
        return list(self._notes)

    def get_note_by_id(self, note_id: str) -> Optional[Note]:
        """Find a note by its ID."""
        for note in self._notes:
            if note.id == note_id:
                return note
        return None

    def get_active_note(self) -> Optional[Note]:
        """Return the currently active note for widget display, or None."""
        for note in self._notes:
            if note.is_active:
                return note
        if self._notes:
            # Fallback: activate first note
            self._notes[0].is_active = True
            self._save_to_disk()
            return self._notes[0]
        return None

    def set_active_note(self, note_id: str) -> bool:
        """
        Set a specific note as active for desktop display,
        deactivating all other notes.
        """
        target_found = False
        for note in self._notes:
            if note.id == note_id:
                note.is_active = True
                target_found = True
            else:
                note.is_active = False

        if target_found:
            self._save_to_disk()
            return True
        return False

    def save_note(
        self,
        title: str,
        content: str,
        note_id: Optional[str] = None,
        speed: Optional[float] = None,
        is_active: Optional[bool] = None,
        color: Optional[str] = None,
        font_size: Optional[int] = None,
        opacity: Optional[float] = None,
        **kwargs: Any,
    ) -> Note:
        """
        Save a note. If note_id exists, update it. Otherwise, create a new note.
        If is_active is True, other notes are automatically deactivated.
        """
        now = datetime.now().isoformat()
        target_note: Optional[Note] = None

        if note_id:
            target_note = self.get_note_by_id(note_id)

        if target_note is not None:
            # Update existing note
            target_note.title = title
            target_note.content = content
            target_note.updated_at = now
            if speed is not None:
                target_note.speed = float(speed)
            if color is not None:
                target_note.color = color
            if font_size is not None:
                target_note.font_size = int(font_size)
            if opacity is not None:
                target_note.opacity = float(opacity)

            if is_active is not None:
                if is_active:
                    for n in self._notes:
                        n.is_active = (n.id == target_note.id)
                else:
                    target_note.is_active = False
                    # Ensure at least one is active if list not empty
                    if not any(n.is_active for n in self._notes):
                        self._notes[0].is_active = True
        else:
            # Create new note
            new_id = note_id or str(uuid.uuid4())
            new_speed = float(speed) if speed is not None else float(self._settings.get("default_speed", 40.0))
            new_color = color or "#FFF8E1"
            new_font_size = int(font_size) if font_size is not None else int(self._settings.get("font_size", 14))
            new_opacity = float(opacity) if opacity is not None else float(self._settings.get("opacity", 0.95))

            # If this is the only note or is_active requested
            should_be_active = bool(is_active) if is_active is not None else (len(self._notes) == 0)

            if should_be_active:
                for n in self._notes:
                    n.is_active = False

            target_note = Note(
                id=new_id,
                title=title,
                content=content,
                created_at=now,
                updated_at=now,
                is_active=should_be_active,
                speed=new_speed,
                color=new_color,
                font_size=new_font_size,
                opacity=new_opacity,
            )
            self._notes.append(target_note)

        self._save_to_disk()
        return target_note

    def delete_note(self, note_id: str) -> bool:
        """
        Delete a note by ID.
        If the deleted note was active, activates the first remaining note.
        """
        target_index = -1
        for i, note in enumerate(self._notes):
            if note.id == note_id:
                target_index = i
                break

        if target_index == -1:
            return False

        removed_note = self._notes.pop(target_index)

        # If deleted note was active, activate first remaining note
        if removed_note.is_active and self._notes:
            self._notes[0].is_active = True

        self._save_to_disk()
        return True

    # ==================== Settings Methods ====================

    def get_settings(self) -> Dict[str, Any]:
        """Return a copy of current application settings."""
        return dict(self._settings)

    def save_settings(self, settings_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge new settings with existing settings and persist to disk.
        Returns the updated settings dictionary.
        """
        self._settings.update(settings_dict)
        self._save_to_disk()
        return dict(self._settings)
