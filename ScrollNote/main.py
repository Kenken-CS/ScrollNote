"""
ScrollNote - Master Application Entry Point
===========================================
Integrates:
- NotesManager from storage.py (JSON persistence, atomic writes)
- DesktopScrollWidget from widget.py (Floating square teleprompter widget)
- MainWindow from main_window.py (Minimalist editor, theme toggle, settings)
- Windows Startup integration via startup.py
- System Tray integration via pystray and Pillow
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
from pathlib import Path
from typing import Optional

# Ensure project directory is in sys.path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import customtkinter as ctk
from PIL import Image, ImageDraw

import startup
from main_window import MainWindow
from storage import Note, NotesManager
from widget import DesktopScrollWidget

try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False


def create_tray_icon_image(size: int = 64, color: str = "#3B82F6") -> Image.Image:
    """
    Generate a modern, clean tray icon image representing a scroll note.
    Uses PIL ImageDraw with antialiasing.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Base rounded card
    padding = 6
    x0, y0 = padding, padding
    x1, y1 = size - padding, size - padding
    radius = 12

    # Draw rounded rectangle note body
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=color)

    # Inner decorative text lines representing a note
    line_color = (255, 255, 255, 220)
    line_x0 = x0 + 12
    line_x1 = x1 - 12
    
    # Title line (thicker)
    draw.rounded_rectangle([line_x0, y0 + 12, line_x0 + 20, y0 + 16], radius=2, fill=(255, 255, 255, 255))
    # Body lines
    draw.rounded_rectangle([line_x0, y0 + 22, line_x1, y0 + 25], radius=2, fill=line_color)
    draw.rounded_rectangle([line_x0, y0 + 30, line_x1 - 8, y0 + 33], radius=2, fill=line_color)
    draw.rounded_rectangle([line_x0, y0 + 38, line_x1 - 16, y0 + 41], radius=2, fill=line_color)

    return img


class ScrollNoteApp:
    """
    Coordinator class tying together the Main Window, Desktop Widget,
    Storage, Settings, and System Tray.
    """

    def __init__(
        self,
        start_minimized: bool = False,
        no_widget: bool = False,
        enable_tray: bool = True,
    ):
        self.start_minimized = start_minimized
        self.no_widget = no_widget
        self.enable_tray = enable_tray

        # 1. Initialize Storage & Settings
        self.notes_manager = NotesManager()
        self.settings = self.notes_manager.get_settings()
        
        # Determine theme and initial active note
        self.theme = self.settings.get("theme", "dark")
        self.speed = float(self.settings.get("default_speed", 1.5))
        self.widget_visible = not self.no_widget and self.settings.get("widget_visible", True)

        self.active_note = self.notes_manager.get_active_note()
        if not self.active_note:
            all_notes = self.notes_manager.get_all_notes()
            if all_notes:
                self.active_note = all_notes[0]
                self.notes_manager.set_active_note(self.active_note.id)

        # 2. Initialize Main Window (CustomTkinter)
        self.main_window = MainWindow(
            notes_manager=self.notes_manager,
            on_widget_toggle=self.on_widget_toggle,
            on_widget_speed_changed=self.on_speed_changed,
            on_widget_theme_changed=self.on_theme_changed,
            on_active_note_changed=self.on_active_note_changed,
            start_hidden=self.start_minimized,
        )

        # 3. Initialize Floating Desktop Widget
        widget_geom = self.settings.get("widget_geometry", {})
        widget_x = widget_geom.get("x")
        widget_y = widget_geom.get("y")
        widget_size = widget_geom.get("size", 280)
        widget_topmost = self.settings.get("always_on_top", True)

        note_title = self.active_note.title if self.active_note else "ScrollNote"
        note_content = self.active_note.content if self.active_note else "Không có ghi chú nào."

        self.widget = DesktopScrollWidget(
            master=self.main_window,
            note_title=note_title,
            note_content=note_content,
            speed=self.speed,
            theme=self.theme,
            size=widget_size,
            x=widget_x,
            y=widget_y,
            is_topmost=widget_topmost,
            on_open_editor=self.show_main_window,
            on_next_note=self.cycle_next_note,
            on_prev_note=self.cycle_prev_note,
            on_close=self.on_widget_closed_by_user,
            on_position_changed=self.on_widget_position_changed,
            on_speed_changed=self.on_widget_speed_changed,
            on_theme_changed=self.on_widget_theme_changed,
        )

        # Connect widget reference to main_window
        self.main_window.widget_ref = self.widget

        # Hide widget if settings or flag requested
        if not self.widget_visible:
            self.widget.hide_widget()

        # 4. Handle Window Close Behavior (Minimize / Hide to Tray)
        self.main_window.protocol("WM_DELETE_WINDOW", self.on_main_window_close)

        # 5. Initialize System Tray
        self.tray_icon: Optional[pystray.Icon] = None
        self._init_system_tray()

    # =========================================================================
    # System Tray Integration
    # =========================================================================

    def _init_system_tray(self) -> None:
        """Initialize background system tray icon with context menu."""
        if not self.enable_tray or not HAS_PYSTRAY:
            return

        tray_img = create_tray_icon_image(64, color="#3B82F6")

        menu = pystray.Menu(
            pystray.MenuItem("📝 Mở ScrollNote", self._tray_show_window, default=True),
            pystray.MenuItem("📌 Bật/Tắt Widget Desktop", self._tray_toggle_widget),
            pystray.MenuItem("⏩ Ghi chú tiếp theo", self._tray_next_note),
            pystray.MenuItem("🌓 Đổi Giao diện Tối/Sáng", self._tray_toggle_theme),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Thoát hoàn toàn", self._tray_exit_app),
        )

        self.tray_icon = pystray.Icon(
            "ScrollNote",
            tray_img,
            "ScrollNote - Ghi chú Cuộn màn hình",
            menu,
        )

        # Run tray icon in background detached daemon thread
        try:
            self.tray_icon.run_detached()
        except Exception as e:
            print(f"[ScrollNote] Warning: Could not start tray icon: {e}")

    def _tray_show_window(self, icon: Any = None, item: Any = None) -> None:
        self.main_window.after(0, self.show_main_window)

    def _tray_toggle_widget(self, icon: Any = None, item: Any = None) -> None:
        self.main_window.after(0, lambda: self.on_widget_toggle(not self.widget.is_visible()))

    def _tray_next_note(self, icon: Any = None, item: Any = None) -> None:
        self.main_window.after(0, self.cycle_next_note)

    def _tray_toggle_theme(self, icon: Any = None, item: Any = None) -> None:
        self.main_window.after(0, self.main_window.toggle_theme)

    def _tray_exit_app(self, icon: Any = None, item: Any = None) -> None:
        self.main_window.after(0, self.quit_application)

    # =========================================================================
    # Synchronization & Callbacks
    # =========================================================================

    def show_main_window(self) -> None:
        """Deiconify main window and bring to foreground."""
        self.main_window.deiconify()
        self.main_window.lift()
        self.main_window.focus_force()

        # If active note in storage differs, sync selection
        active = self.notes_manager.get_active_note()
        if active and active.id != self.main_window.selected_note_id:
            self.main_window.select_note(active.id)

    def on_main_window_close(self) -> None:
        """
        Handle user clicking 'X' on Main Window.
        Hides window to tray/desktop so the square widget continues floating.
        """
        self.main_window.save_window_state()
        
        # Withdraw editor window; widget keeps running on screen
        self.main_window.withdraw()

    def on_widget_toggle(self, visible: bool) -> None:
        """Called when widget visibility toggle changes."""
        self.widget_visible = visible
        if visible:
            self.widget.show_widget()
        else:
            self.widget.hide_widget()
        
        # Sync main window switch if needed
        if hasattr(self.main_window, "widget_switch"):
            if visible and not self.main_window.widget_switch.get():
                self.main_window.widget_switch.select()
            elif not visible and self.main_window.widget_switch.get():
                self.main_window.widget_switch.deselect()

        self.notes_manager.save_settings({"widget_visible": visible})

    def on_widget_closed_by_user(self) -> None:
        """Called when user clicks 'Close' on the desktop widget."""
        self.on_widget_toggle(False)

    def on_speed_changed(self, speed: float) -> None:
        """Called when speed slider is dragged in MainWindow."""
        speed = round(float(speed), 1)
        if self.speed == speed:
            return
        self.speed = speed
        self.widget.set_speed(speed)

    def on_widget_speed_changed(self, speed: float) -> None:
        """Called when speed buttons (- / +) are clicked on the widget."""
        speed = round(float(speed), 1)
        if self.speed == speed:
            return
        self.speed = speed
        self.main_window.update_speed_from_widget(speed)
        self.notes_manager.save_settings({"default_speed": speed})

    def on_theme_changed(self, theme: str) -> None:
        """Called when theme is toggled in MainWindow."""
        if self.theme == theme:
            return
        self.theme = theme
        self.widget.update_theme(theme)

    def on_widget_theme_changed(self, theme: str) -> None:
        """Called when theme is toggled on Desktop Widget."""
        if self.theme == theme:
            return
        self.theme = theme
        self.main_window.set_theme(theme)

    def on_active_note_changed(self, note: Note) -> None:
        """Called when a note is set active in MainWindow."""
        self.active_note = note
        self.widget.set_note_object(note)

    def on_widget_position_changed(self, x: int, y: int) -> None:
        """Persist new desktop widget coordinates."""
        current_geom = self.settings.get("widget_geometry", {})
        current_geom["x"] = x
        current_geom["y"] = y
        self.notes_manager.save_settings({"widget_geometry": current_geom})

    def cycle_next_note(self) -> None:
        """Cycle to the next note in storage and display on widget."""
        notes = self.notes_manager.get_all_notes()
        if not notes:
            return

        current_id = self.active_note.id if self.active_note else ""
        current_idx = 0
        for i, n in enumerate(notes):
            if n.id == current_id:
                current_idx = i
                break

        next_idx = (current_idx + 1) % len(notes)
        next_note = notes[next_idx]
        self.notes_manager.set_active_note(next_note.id)
        self.active_note = next_note

        # Update widget and main window
        self.widget.set_note_object(next_note)
        self.main_window.select_note(next_note.id)

    def cycle_prev_note(self) -> None:
        """Cycle to the previous note in storage and display on widget."""
        notes = self.notes_manager.get_all_notes()
        if not notes:
            return

        current_id = self.active_note.id if self.active_note else ""
        current_idx = 0
        for i, n in enumerate(notes):
            if n.id == current_id:
                current_idx = i
                break

        prev_idx = (current_idx - 1) % len(notes)
        prev_note = notes[prev_idx]
        self.notes_manager.set_active_note(prev_note.id)
        self.active_note = prev_note

        # Update widget and main window
        self.widget.set_note_object(prev_note)
        self.main_window.select_note(prev_note.id)

    def quit_application(self) -> None:
        """Clean shutdown of entire app, tray, widget, and storage."""
        try:
            self.main_window.save_window_state()
        except Exception:
            pass

        # Stop tray icon
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        # Destroy widget and main window
        try:
            self.widget.destroy()
        except Exception:
            pass

        try:
            self.main_window.quit()
            self.main_window.destroy()
        except Exception:
            pass

    def run(self) -> None:
        """Start the application mainloop."""
        self.main_window.mainloop()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ScrollNote - Floating Desktop Note & Escalator Teleprompter")
    parser.add_argument(
        "--minimized",
        "--hide-main",
        action="store_true",
        help="Start with main editor hidden, displaying only the desktop widget",
    )
    parser.add_argument(
        "--no-widget",
        action="store_true",
        help="Start without opening the desktop widget",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    app = ScrollNoteApp(
        start_minimized=args.minimized,
        no_widget=args.no_widget,
    )
    app.run()


if __name__ == "__main__":
    main()
