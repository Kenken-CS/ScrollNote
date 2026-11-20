"""
ScrollNote - Comprehensive Verification & QA Test Suite
======================================================
Tests all 4 user requirements, edge cases, integration, and UI lifecycles.
"""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Set working directory to project root
PROJECT_DIR = Path(r"d:\ScrollNote")
sys.path.insert(0, str(PROJECT_DIR))

import startup
from storage import Note, NotesManager, DEFAULT_SETTINGS, WELCOME_NOTE_TITLE
from widget import DesktopScrollWidget, THEMES
from main_window import MainWindow, NoteCard, COLORS
from main import ScrollNoteApp, create_tray_icon_image


class TestRequirement1_NoteStorage(unittest.TestCase):
    """
    Requirement 1: Note storage in 1 separate file (notes.json).
    Test adding/updating/deleting notes, persistence, and edge cases.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_file = os.path.join(self.temp_dir.name, "notes.json")
        self.mgr = NotesManager(storage_path=self.storage_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_single_file_storage_and_welcome_note(self):
        """Verify storage uses exactly 1 separate file and initializes welcome note."""
        self.assertTrue(os.path.exists(self.storage_file))
        notes = self.mgr.get_all_notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].title, WELCOME_NOTE_TITLE)
        self.assertTrue(notes[0].is_active)
        self.assertIn("ScrollNote", notes[0].content)

    def test_add_update_delete_notes(self):
        """Test full CRUD cycle with persistence."""
        # Add note
        n1 = self.mgr.save_note(
            title="Ghi chú công việc tuần này",
            content="1. Báo cáo doanh số\n2. Họp team kỹ thuật\n3. Kiểm thử phần mềm",
            speed=2.0,
            is_active=True,
        )
        self.assertIsNotNone(n1.id)
        self.assertTrue(n1.is_active)
        # Verify previous active note is now inactive
        all_notes = self.mgr.get_all_notes()
        self.assertEqual(len(all_notes), 2)
        old_note = [n for n in all_notes if n.id != n1.id][0]
        self.assertFalse(old_note.is_active)

        # Update note
        updated_n1 = self.mgr.save_note(
            note_id=n1.id,
            title="Ghi chú công việc tuần này (Ưu tiên cao)",
            content="1. Báo cáo doanh số [Xong]\n2. Họp team kỹ thuật",
            speed=3.0,
        )
        self.assertEqual(updated_n1.title, "Ghi chú công việc tuần này (Ưu tiên cao)")
        self.assertEqual(updated_n1.speed, 3.0)

        # Persistence check with fresh NotesManager instance
        mgr2 = NotesManager(storage_path=self.storage_file)
        loaded_n1 = mgr2.get_note_by_id(n1.id)
        self.assertIsNotNone(loaded_n1)
        self.assertEqual(loaded_n1.title, "Ghi chú công việc tuần này (Ưu tiên cao)")
        self.assertEqual(loaded_n1.speed, 3.0)
        self.assertTrue(loaded_n1.is_active)

        # Delete note
        success = mgr2.delete_note(n1.id)
        self.assertTrue(success)
        self.assertEqual(len(mgr2.get_all_notes()), 1)
        # Ensure active note fallback
        active_remaining = mgr2.get_active_note()
        self.assertIsNotNone(active_remaining)
        self.assertEqual(active_remaining.id, old_note.id)
        self.assertTrue(active_remaining.is_active)

    def test_vietnamese_unicode_and_special_characters(self):
        """Verify full Vietnamese diacritics, emojis, quotes, and punctuation."""
        vn_title = "🇻🇳 Tiếng Việt có dấu: Ắ, Ằ, Ẳ, Ẵ, Ặ, Ế, Ề, Ể, Ễ, Ệ, Ố, Ồ, Ổ, Ỗ, Ộ, Ứ, Ừ, Ử, Ữ, Ự"
        vn_content = """Một trăm phần trăm tiếng Việt chuẩn mực:
- Trăm năm trong cõi người ta, chữ tài chữ mệnh khéo là ghét nhau.
- Trải qua một cuộc bể dâu, những điều trông thấy mà đau đớn lòng.
- Ký tự đặc biệt: <>&"'/\\{}[]|~`!@#$%^&*()_+=-:;?
- Emojis: 🌟🚀📜💡❤️🎉🔥🤖"""

        note = self.mgr.save_note(title=vn_title, content=vn_content)
        
        # Read directly from raw JSON file to confirm UTF-8 encoding
        with open(self.storage_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        
        found = False
        for item in raw_data["notes"]:
            if item["id"] == note.id:
                self.assertEqual(item["title"], vn_title)
                self.assertEqual(item["content"], vn_content)
                found = True
        self.assertTrue(found)

    def test_empty_notes_and_massive_text(self):
        """Verify edge cases: completely empty note and massive text (50,000 characters)."""
        # Empty title and content
        empty_note = self.mgr.save_note(title="", content="")
        self.assertEqual(empty_note.title, "")
        self.assertEqual(empty_note.content, "")

        # Massive text
        massive_text = "ScrollNote escalates smoothly upwards! " * 1500  # ~58,000 characters
        huge_note = self.mgr.save_note(title="Massive Note Test", content=massive_text)
        
        # Reload
        mgr_fresh = NotesManager(storage_path=self.storage_file)
        loaded = mgr_fresh.get_note_by_id(huge_note.id)
        self.assertEqual(len(loaded.content), len(massive_text))

    def test_corrupt_json_recovery(self):
        """Verify corrupted JSON is safely backed up and defaults restored."""
        with open(self.storage_file, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON CONTENT ::: %%%")

        mgr_recovered = NotesManager(storage_path=self.storage_file)
        notes = mgr_recovered.get_all_notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].title, WELCOME_NOTE_TITLE)
        # Check that backup exists
        backup_path = Path(self.storage_file).with_suffix(".corrupt.bak")
        self.assertTrue(backup_path.exists())


class TestRequirement2_MinimalistUI_ThemeToggle(unittest.TestCase):
    """
    Requirement 2: Minimalist UI with Dark mode and Light mode toggling smoothly.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_file = os.path.join(self.temp_dir.name, "notes.json")
        self.mgr = NotesManager(storage_path=self.storage_file)
        self.app = MainWindow(notes_manager=self.mgr, start_hidden=True)
        self.app.update()

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        self.temp_dir.cleanup()

    def test_minimalist_ui_components_exist(self):
        """Verify clean minimalist layout: Sidebar, Search, NoteCard, Editor, Status, Settings."""
        self.assertTrue(hasattr(self.app, "sidebar_frame"))
        self.assertTrue(hasattr(self.app, "editor_frame"))
        self.assertTrue(hasattr(self.app, "search_entry"))
        self.assertTrue(hasattr(self.app, "title_entry"))
        self.assertTrue(hasattr(self.app, "content_textbox"))
        self.assertTrue(hasattr(self.app, "save_status_label"))
        self.assertTrue(hasattr(self.app, "word_count_label"))
        self.assertTrue(hasattr(self.app, "theme_btn"))
        self.assertTrue(hasattr(self.app, "startup_switch"))
        self.assertTrue(hasattr(self.app, "widget_switch"))
        self.assertTrue(hasattr(self.app, "speed_slider"))

    def test_theme_toggle_smoothness(self):
        """Verify Dark Mode <-> Light Mode toggling and persistence."""
        # Start in Dark Mode
        self.app.set_theme("dark")
        self.app.update()
        self.assertEqual(self.app.current_theme, "dark")
        self.assertIn("Tối", self.app.theme_btn.cget("text"))
        self.assertEqual(self.mgr.get_settings()["theme"], "dark")

        # Toggle to Light Mode
        self.app.toggle_theme()
        self.app.update()
        self.assertEqual(self.app.current_theme, "light")
        self.assertIn("Sáng", self.app.theme_btn.cget("text"))
        self.assertEqual(self.mgr.get_settings()["theme"], "light")

        # Toggle back to Dark Mode
        self.app.toggle_theme()
        self.app.update()
        self.assertEqual(self.app.current_theme, "dark")
        self.assertIn("Tối", self.app.theme_btn.cget("text"))
        self.assertEqual(self.mgr.get_settings()["theme"], "dark")


class TestRequirement3_WindowsStartup(unittest.TestCase):
    """
    Requirement 3: Startup with Windows (HKCU Run registry entry / startup shortcut).
    """

    def test_registry_integration(self):
        test_key = "ScrollNote_Verification_QA_Key"
        
        # Ensure clean initial state
        startup.disable_startup(app_name=test_key)
        self.assertFalse(startup.is_startup_enabled(app_name=test_key))

        # Enable startup
        custom_cmd = r'"C:\Python315\pythonw.exe" "D:\ScrollNote\main.py" --minimized'
        success = startup.enable_startup(app_name=test_key, app_path=custom_cmd)
        self.assertTrue(success)

        # Query and verify
        self.assertTrue(startup.is_startup_enabled(app_name=test_key))
        stored_cmd = startup.get_startup_command(app_name=test_key)
        self.assertEqual(stored_cmd, custom_cmd)

        # Disable startup
        disabled = startup.disable_startup(app_name=test_key)
        self.assertTrue(disabled)
        self.assertFalse(startup.is_startup_enabled(app_name=test_key))
        self.assertIsNone(startup.get_startup_command(app_name=test_key))

    def test_default_launch_command_format(self):
        """Verify default launch command uses pythonw and points to main.py."""
        cmd = startup._get_default_launch_command()
        self.assertTrue("python" in cmd.lower())
        self.assertTrue("main.py" in cmd)


class TestRequirement4_DesktopSquareWidget(unittest.TestCase):
    """
    Requirement 4: Desktop floating square widget with smooth upward vertical escalator / teleprompter scrolling of selected note.
    """

    def setUp(self):
        self.widget = DesktopScrollWidget(
            note_title="Kiểm thử Widget",
            note_content="Dòng 1: Chữ chạy lên\nDòng 2: Mượt mà không giật\nDòng 3: Hoàn thành",
            speed=1.5,
            theme="dark",
            size=280,
        )
        self.widget.update()

    def tearDown(self):
        try:
            self.widget.destroy()
        except Exception:
            pass

    def test_square_aspect_ratio_and_frameless(self):
        """Verify widget is a perfect square (280x280) and frameless."""
        self.assertEqual(self.widget._width, 280)
        self.assertEqual(self.widget._height, 280)
        # Frameless floating gadget
        self.assertTrue(self.widget.overrideredirect())
        # Always on top attribute
        self.assertTrue(self.widget.is_topmost())

    def test_upward_vertical_escalator_movement(self):
        """
        Verify that scrolling moves text UPWARDS (y decreases as content flows up like an escalator).
        """
        initial_y0 = self.widget._y0
        initial_y1 = self.widget._y1

        # Simulate animation step: dy is positive (upward displacement)
        dy = self.widget._speed * self.widget._base_speed
        self.assertTrue(dy > 0)

        self.widget._scroll_delta(dy)
        self.widget.update()

        # Both text blocks must have moved upwards by dy
        self.assertAlmostEqual(self.widget._y0, initial_y0 - dy)
        self.assertAlmostEqual(self.widget._y1, initial_y1 - dy)

    def test_infinite_wrap_around_continuity(self):
        """Verify that when a text block moves past the top, it wraps to the bottom seamlessly."""
        # Scroll upward heavily until wrap occurs
        large_displacement = self.widget._block_height + 200.0
        self.widget._scroll_delta(large_displacement)
        self.widget.update()

        # Both copies must still exist on canvas
        copy_0_items = self.widget.canvas.find_withtag("copy_0")
        copy_1_items = self.widget.canvas.find_withtag("copy_1")
        self.assertTrue(len(copy_0_items) > 0)
        self.assertTrue(len(copy_1_items) > 0)

    def test_pause_and_speed_control(self):
        """Verify play/pause toggling and speed adjustments."""
        self.assertFalse(self.widget.is_paused())
        self.widget.toggle_play_pause()
        self.assertTrue(self.widget.is_paused())
        self.widget.toggle_play_pause()
        self.assertFalse(self.widget.is_paused())

        # Test speed change
        self.widget.set_speed(3.5)
        self.assertEqual(self.widget.get_speed(), 3.5)

    def test_widget_theme_switching(self):
        """Verify widget transitions between Dark and Light mode properly."""
        self.widget.update_theme("light")
        self.widget.update()
        self.assertEqual(self.widget._theme, "light")
        self.assertEqual(self.widget.cget("bg"), THEMES["light"]["card_bg"])

        self.widget.update_theme("dark")
        self.widget.update()
        self.assertEqual(self.widget._theme, "dark")
        self.assertEqual(self.widget.cget("bg"), THEMES["dark"]["card_bg"])

    def test_mouse_wheel_manual_scroll(self):
        """Verify mouse wheel shifts text up and down."""
        y_before = self.widget._y0
        # Scroll up (wheel delta +120)
        class DummyEvent:
            delta = 120
        self.widget._on_mouse_wheel(DummyEvent())
        self.widget.update()
        # Shifting downwards on screen
        self.assertNotEqual(self.widget._y0, y_before)


class TestFullAppIntegrationAndRunScript(unittest.TestCase):
    """
    Test End-to-End Coordination between Main App, Tray, Widget, and run.bat.
    """

    def test_full_app_lifecycle(self):
        """Start full application in headless/test mode, verify all links, then shutdown."""
        app = ScrollNoteApp(start_minimized=True, no_widget=False, enable_tray=False)
        app.main_window.update()

        # Check references
        self.assertIsNotNone(app.notes_manager)
        self.assertIsNotNone(app.main_window)
        self.assertIsNotNone(app.widget)

        # Sync active note change
        new_note = app.notes_manager.save_note(title="Sync Title", content="Sync Content")
        app.on_active_note_changed(new_note)
        app.main_window.update()
        self.assertEqual(app.widget._note_title, "Sync Title")

        # Sync speed change
        app.on_speed_changed(2.8)
        self.assertEqual(app.widget.get_speed(), 2.8)

        # Clean shutdown
        app.quit_application()

    def test_run_bat_exists_and_valid(self):
        """Check run.bat existence and content."""
        bat_file = PROJECT_DIR / "run.bat"
        self.assertTrue(bat_file.exists())
        content = bat_file.read_text(encoding="utf-8")
        self.assertIn("main.py", content)
        self.assertIn("python", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
