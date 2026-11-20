"""
ScrollNote - Minimalist Main Application Window
===============================================
A modern, minimalist desktop notes application built with CustomTkinter and Pillow.
Supports seamless Dark Mode and Light Mode, real-time search, auto-saving,
desktop square widget synchronization, and Windows startup control.
"""

from __future__ import annotations

import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk
from PIL import Image, ImageDraw

# Add parent directory to path to ensure relative imports work
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import startup
from storage import Note, NotesManager

# ============================================================================
# Color Tokens & Palette
# ============================================================================
# Colors defined as (light_color, dark_color) tuples for CustomTkinter
COLORS = {
    # Backgrounds
    "window_bg": ("#F8FAFC", "#11111B"),
    "sidebar_bg": ("#F1F5F9", "#181825"),
    "editor_bg": ("#FFFFFF", "#1E1E2E"),
    "card_bg": ("#FFFFFF", "#1E1E2E"),
    "card_hover": ("#E2E8F0", "#313244"),
    "card_active": ("#E0E7FF", "#2A2B3D"),
    "card_border": ("#E2E8F0", "#313244"),
    "card_active_border": ("#3B82F6", "#89B4FA"),
    
    # Primary & Accent
    "primary": ("#2563EB", "#3B82F6"),
    "primary_hover": ("#1D4ED8", "#2563EB"),
    "accent_green": ("#059669", "#10B981"),
    "accent_green_hover": ("#047857", "#059669"),
    "danger": ("#DC2626", "#EF4444"),
    "danger_hover": ("#B91C1C", "#DC2626"),
    
    # Badges
    "badge_widget_bg": ("#DBEAFE", "#1E293B"),
    "badge_widget_fg": ("#1D4ED8", "#89B4FA"),
    "badge_widget_border": ("#93C5FD", "#3B82F6"),
    
    # Typography
    "text_primary": ("#0F172A", "#CDD6F4"),
    "text_secondary": ("#64748B", "#9399B2"),
    "text_muted": ("#94A3B8", "#6C7086"),
    "border_subtle": ("#E2E8F0", "#313244"),
    "input_bg": ("#F8FAFC", "#181825"),
    "input_border": ("#CBD5E1", "#45475A"),
}


class NoteCard(ctk.CTkFrame):
    """
    A sleek, modern clickable card for the sidebar note list.
    Displays note title, content preview, timestamp, and active desktop badge.
    """

    def __init__(
        self,
        master: Any,
        note: Note,
        is_selected: bool = False,
        on_select: Optional[Callable[[str], None]] = None,
        on_set_active: Optional[Callable[[str], None]] = None,
        on_delete: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ):
        super().__init__(
            master,
            corner_radius=10,
            border_width=2 if is_selected else 1,
            fg_color=COLORS["card_active"] if is_selected else COLORS["card_bg"],
            border_color=COLORS["card_active_border"] if is_selected else COLORS["card_border"],
            cursor="hand2",
            **kwargs,
        )
        self.note = note
        self.is_selected = is_selected
        self.on_select = on_select
        self.on_set_active = on_set_active
        self.on_delete = on_delete

        self._build_ui()
        self._bind_events()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Top row: Title and Badge / Pin
        title_text = self.note.title.strip() or "Ghi chú không tiêu đề"
        if len(title_text) > 28:
            title_text = title_text[:28] + "..."

        self.title_label = ctk.CTkLabel(
            self,
            text=title_text,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=(12, 4), pady=(10, 2))

        # Desktop Widget Badge (if active)
        if self.note.is_active:
            self.badge = ctk.CTkLabel(
                self,
                text="📌 Widget",
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=COLORS["badge_widget_bg"],
                text_color=COLORS["badge_widget_fg"],
                corner_radius=6,
                padx=6,
                pady=2,
            )
            self.badge.grid(row=0, column=1, sticky="e", padx=(0, 10), pady=(10, 2))

        # Middle row: Content Snippet Preview
        preview_text = self.note.content.strip().replace("\n", " ")
        if not preview_text:
            preview_text = "Không có nội dung..."
        elif len(preview_text) > 45:
            preview_text = preview_text[:45] + "..."

        self.preview_label = ctk.CTkLabel(
            self,
            text=preview_text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_secondary"],
            anchor="w",
        )
        self.preview_label.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 4))

        # Bottom row: Timestamp
        time_str = self._format_timestamp(self.note.updated_at)
        self.time_label = ctk.CTkLabel(
            self,
            text=time_str,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.time_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))

    def _format_timestamp(self, iso_str: str) -> str:
        """Format ISO timestamp into friendly Vietnamese date/time string."""
        try:
            dt = datetime.fromisoformat(iso_str)
            now = datetime.now()
            if dt.date() == now.date():
                return f"Hôm nay, {dt.strftime('%H:%M')}"
            elif (now.date() - dt.date()).days == 1:
                return f"Hôm qua, {dt.strftime('%H:%M')}"
            else:
                return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return iso_str[:16] if iso_str else ""

    def _bind_events(self) -> None:
        """Bind click and context menu events to all children widgets."""
        for widget in (self, self.title_label, self.preview_label, self.time_label):
            widget.bind("<Button-1>", self._on_clicked)
            widget.bind("<Button-3>", self._show_context_menu)

    def _on_clicked(self, event: Any = None) -> None:
        if self.on_select:
            self.on_select(self.note.id)

    def _show_context_menu(self, event: Any) -> None:
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        
        if not self.note.is_active:
            menu.add_command(
                label="📌 Ghim lên Widget Desktop",
                command=lambda: self.on_set_active(self.note.id) if self.on_set_active else None
            )
        else:
            menu.add_command(label="✓ Đang hiển thị trên Widget", state="disabled")
            
        menu.add_separator()
        menu.add_command(
            label="🗑 Xoá ghi chú này",
            command=lambda: self.on_delete(self.note.id) if self.on_delete else None
        )
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()


class MainWindow(ctk.CTk):
    """
    Minimalist Main Application Window for ScrollNote.
    
    Contains:
    - Left Sidebar: Note list, search bar, + New Note button.
    - Right Editor Area: Note title, multi-line editor, active widget badge/button, word count.
    - Bottom Toolbar: Theme toggle, Windows startup switch, Widget Desktop toggle, Speed slider.
    """

    def __init__(
        self,
        notes_manager: Optional[NotesManager] = None,
        widget_ref: Optional[Any] = None,
        on_widget_toggle: Optional[Callable[[bool], None]] = None,
        on_widget_speed_changed: Optional[Callable[[float], None]] = None,
        on_widget_theme_changed: Optional[Callable[[str], None]] = None,
        on_active_note_changed: Optional[Callable[[Note], None]] = None,
        on_app_exit: Optional[Callable[[], None]] = None,
        start_hidden: bool = False,
    ):
        super().__init__()

        # Dependencies
        self.notes_manager = notes_manager or NotesManager()
        self.widget_ref = widget_ref
        
        # External Callbacks
        self.on_widget_toggle = on_widget_toggle
        self.on_widget_speed_changed = on_widget_speed_changed
        self.on_widget_theme_changed = on_widget_theme_changed
        self.on_active_note_changed = on_active_note_changed
        self.on_app_exit = on_app_exit

        # Application State
        self.settings = self.notes_manager.get_settings()
        self.current_theme: str = self.settings.get("theme", "dark")
        self.current_speed: float = float(self.settings.get("default_speed", 1.5))
        self.is_widget_visible: bool = self.settings.get("widget_visible", True)
        self.selected_note_id: Optional[str] = None
        
        # Auto-save debounce timer
        self._save_timer: Optional[threading.Timer] = None
        self._is_saving: bool = False
        self._search_query: str = ""

        # Configure Window
        self.title("ScrollNote - Ghi chú Cuộn màn hình")
        self.geometry(self.settings.get("window_geometry", "1020x680"))
        self.minsize(840, 520)

        # Set initial appearance mode
        ctk.set_appearance_mode(self.current_theme)
        ctk.set_default_color_theme("blue")

        # Layout Main Grid: 2 columns (Sidebar, Editor), 2 rows (Content, Bottom Bar)
        self.grid_columnconfigure(0, weight=0, minsize=320)  # Sidebar
        self.grid_columnconfigure(1, weight=1)              # Editor
        self.grid_rowconfigure(0, weight=1)                 # Main Area
        self.grid_rowconfigure(1, weight=0)                 # Bottom Settings Bar

        # Build Sub-systems
        self._build_sidebar()
        self._build_editor()
        self._build_bottom_bar()

        # Keyboard shortcuts
        self.bind("<Control-n>", lambda e: self.create_new_note())
        self.bind("<Control-s>", lambda e: self.save_current_note(immediate=True))
        self.bind("<Control-f>", lambda e: self.search_entry.focus_set())

        # Select initial active note
        active_note = self.notes_manager.get_active_note()
        if active_note:
            self.select_note(active_note.id)
        else:
            all_notes = self.notes_manager.get_all_notes()
            if all_notes:
                self.select_note(all_notes[0].id)
            else:
                self.create_new_note()

        # Populate sidebar list
        self.refresh_notes_list()

        # Handle hide on startup if requested
        if start_hidden:
            self.withdraw()

    # =========================================================================
    # UI Builders
    # =========================================================================

    def _build_sidebar(self) -> None:
        """Build the left sidebar containing header, search, and scrollable note list."""
        self.sidebar_frame = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=COLORS["sidebar_bg"],
            border_width=1,
            border_color=COLORS["border_subtle"],
        )
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        self.sidebar_frame.grid_rowconfigure(2, weight=1)  # Notes list expands

        # 1. Top Header: Brand & New Note Button
        header_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)

        # Brand / Logo
        logo_label = ctk.CTkLabel(
            header_frame,
            text="📜 ScrollNote",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        logo_label.grid(row=0, column=0, sticky="w")

        # "+ Note Mới" Button
        self.new_note_btn = ctk.CTkButton(
            header_frame,
            text="+ Note Mới",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            corner_radius=8,
            width=100,
            height=32,
            command=self.create_new_note,
        )
        self.new_note_btn.grid(row=0, column=1, sticky="e")

        # 2. Search Bar
        search_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        search_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Tìm kiếm ghi chú... (Ctrl+F)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=34,
            corner_radius=8,
            border_width=1,
            fg_color=COLORS["input_bg"],
            border_color=COLORS["input_border"],
            text_color=COLORS["text_primary"],
        )
        self.search_entry.grid(row=0, column=0, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search_query_changed)

        # 3. Scrollable Note List
        self.notes_scroll = ctk.CTkScrollableFrame(
            self.sidebar_frame,
            corner_radius=0,
            fg_color="transparent",
        )
        self.notes_scroll.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.notes_scroll.grid_columnconfigure(0, weight=1)

        # 4. Sidebar Footer: Note Counter
        self.notes_count_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="0 ghi chú",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.notes_count_label.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 10))

    def _build_editor(self) -> None:
        """Build the right editor area with minimalist title, content, and top action bar."""
        self.editor_frame = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=COLORS["editor_bg"],
        )
        self.editor_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.editor_frame.grid_columnconfigure(0, weight=1)
        self.editor_frame.grid_rowconfigure(2, weight=1)  # Textbox expands

        # 1. Top Editor Action Bar
        top_bar = ctk.CTkFrame(self.editor_frame, fg_color="transparent", height=42)
        top_bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 8))
        top_bar.grid_columnconfigure(0, weight=1)  # Left status
        top_bar.grid_columnconfigure(1, weight=0)  # Action buttons

        # Save Status Indicator
        self.save_status_label = ctk.CTkLabel(
            top_bar,
            text="✓ Tự động lưu",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.save_status_label.grid(row=0, column=0, sticky="w")

        # Action Buttons Frame
        action_btn_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        action_btn_box.grid(row=0, column=1, sticky="e")

        # "Hiển thị trên Widget Desktop" Button
        self.set_active_btn = ctk.CTkButton(
            action_btn_box,
            text="📌 Hiển thị trên Widget Desktop",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            corner_radius=8,
            height=32,
            command=self.set_current_as_active_widget,
        )
        self.set_active_btn.pack(side="left", padx=(0, 8))

        # "Xoá Ghi chú" Button
        self.delete_btn = ctk.CTkButton(
            action_btn_box,
            text="🗑 Xoá",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent",
            hover_color=COLORS["card_hover"],
            text_color=COLORS["danger"],
            border_width=1,
            border_color=COLORS["danger"],
            corner_radius=8,
            width=65,
            height=32,
            command=self.delete_current_note,
        )
        self.delete_btn.pack(side="left")

        # 2. Note Title Entry (Minimalist borderless style)
        self.title_entry = ctk.CTkEntry(
            self.editor_frame,
            placeholder_text="Tiêu đề ghi chú...",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            height=44,
            corner_radius=0,
            border_width=0,
            fg_color="transparent",
            text_color=COLORS["text_primary"],
        )
        self.title_entry.grid(row=1, column=0, sticky="ew", padx=24, pady=(4, 6))
        self.title_entry.bind("<KeyRelease>", self._on_editor_content_changed)

        # 3. Note Content Textbox (Spacious, comfortable multi-line)
        self.content_textbox = ctk.CTkTextbox(
            self.editor_frame,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border_subtle"],
            fg_color=COLORS["input_bg"],
            text_color=COLORS["text_primary"],
            wrap="word",
            undo=True,
        )
        self.content_textbox.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 10))
        self.content_textbox.bind("<KeyRelease>", self._on_editor_content_changed)

        # 4. Word & Character Counter
        editor_footer = ctk.CTkFrame(self.editor_frame, fg_color="transparent")
        editor_footer.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 12))
        editor_footer.grid_columnconfigure(0, weight=1)

        self.word_count_label = ctk.CTkLabel(
            editor_footer,
            text="0 từ • 0 ký tự",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
            anchor="e",
        )
        self.word_count_label.grid(row=0, column=0, sticky="e")

    def _build_bottom_bar(self) -> None:
        """Build the bottom bar containing Theme toggle, Startup switch, Widget toggle, Speed slider."""
        self.bottom_bar = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color=COLORS["sidebar_bg"],
            border_width=1,
            border_color=COLORS["border_subtle"],
            height=54,
        )
        self.bottom_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.bottom_bar.grid_columnconfigure(0, weight=0)  # Theme & Startup
        self.bottom_bar.grid_columnconfigure(1, weight=1)  # Spacer
        self.bottom_bar.grid_columnconfigure(2, weight=0)  # Widget Controls

        # Left controls: Theme toggle & Windows Startup switch
        left_box = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        left_box.grid(row=0, column=0, sticky="w", padx=16, pady=8)

        # Theme Toggle Button
        theme_icon = "🌙 Tối" if self.current_theme == "dark" else "☀️ Sáng"
        self.theme_btn = ctk.CTkButton(
            left_box,
            text=f"Giao diện: {theme_icon}",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=COLORS["card_bg"],
            hover_color=COLORS["card_hover"],
            text_color=COLORS["text_primary"],
            border_width=1,
            border_color=COLORS["border_subtle"],
            corner_radius=8,
            height=32,
            width=130,
            command=self.toggle_theme,
        )
        self.theme_btn.pack(side="left", padx=(0, 14))

        # Windows Startup Switch
        is_startup = startup.is_startup_enabled()
        self.startup_switch = ctk.CTkSwitch(
            left_box,
            text="Khởi động cùng Windows",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"],
            command=self._on_startup_switch_toggled,
            onvalue=1,
            offvalue=0,
        )
        if is_startup:
            self.startup_switch.select()
        else:
            self.startup_switch.deselect()
        self.startup_switch.pack(side="left")

        # Right controls: Desktop Widget Toggle & Speed Slider
        right_box = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        right_box.grid(row=0, column=2, sticky="e", padx=16, pady=8)

        # Speed Slider & Label
        self.speed_label = ctk.CTkLabel(
            right_box,
            text=f"Tốc độ: {self.current_speed:.1f}x",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_secondary"],
        )
        self.speed_label.pack(side="left", padx=(0, 8))

        self.speed_slider = ctk.CTkSlider(
            right_box,
            from_=0.5,
            to=4.5,
            number_of_steps=40,
            width=120,
            command=self._on_speed_slider_changed,
        )
        self.speed_slider.set(self.current_speed)
        self.speed_slider.pack(side="left", padx=(0, 16))

        # Desktop Widget Toggle Switch
        self.widget_switch = ctk.CTkSwitch(
            right_box,
            text="Widget Desktop",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_primary"],
            command=self._on_widget_switch_toggled,
            onvalue=1,
            offvalue=0,
        )
        if self.is_widget_visible:
            self.widget_switch.select()
        else:
            self.widget_switch.deselect()
        self.widget_switch.pack(side="left")

    # =========================================================================
    # Note Management & List Operations
    # =========================================================================

    def refresh_notes_list(self) -> None:
        """Clear and repopulate note cards in the scrollable sidebar."""
        for widget in self.notes_scroll.winfo_children():
            widget.destroy()

        all_notes = self.notes_manager.get_all_notes()
        
        # Filter by search query if any
        if self._search_query:
            query = self._search_query.lower()
            filtered_notes = [
                n for n in all_notes
                if query in n.title.lower() or query in n.content.lower()
            ]
        else:
            filtered_notes = all_notes

        # Sort notes by updated_at descending
        filtered_notes.sort(key=lambda n: n.updated_at, reverse=True)

        for note in filtered_notes:
            is_selected = (note.id == self.selected_note_id)
            card = NoteCard(
                self.notes_scroll,
                note=note,
                is_selected=is_selected,
                on_select=self.select_note,
                on_set_active=self.set_active_note_id,
                on_delete=self.delete_note_by_id,
            )
            card.pack(fill="x", padx=4, pady=4)

        # Update note counter
        count_text = f"{len(filtered_notes)}/{len(all_notes)} ghi chú" if self._search_query else f"{len(all_notes)} ghi chú"
        self.notes_count_label.configure(text=count_text)

    def select_note(self, note_id: str) -> None:
        """Select a note by ID and load its content into the editor."""
        # Auto-save currently open note before switching
        if self.selected_note_id and self.selected_note_id != note_id:
            self.save_current_note(immediate=True)

        target_note = self.notes_manager.get_note_by_id(note_id)
        if not target_note:
            return

        self.selected_note_id = note_id

        # Update editor fields
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, target_note.title)

        self.content_textbox.delete("1.0", "end")
        self.content_textbox.insert("1.0", target_note.content)

        # Update counters and active widget status
        self._update_word_char_counts()
        self._update_active_widget_button(target_note.is_active)
        self.save_status_label.configure(text=f"✓ Đã lưu ({datetime.now().strftime('%H:%M:%S')})")

        # Refresh sidebar highlights
        self.refresh_notes_list()

    def create_new_note(self) -> None:
        """Create a new blank note and focus editor."""
        # Auto-save current
        self.save_current_note(immediate=True)

        new_note = self.notes_manager.save_note(
            title="Ghi chú mới",
            content="",
            speed=self.current_speed,
        )
        self.selected_note_id = new_note.id
        self.select_note(new_note.id)
        
        # Focus on title entry for immediate typing
        self.title_entry.focus_set()
        self.title_entry.select_range(0, "end")

    def save_current_note(self, immediate: bool = False) -> None:
        """Save the currently active note to disk and update desktop widget if active."""
        if not self.selected_note_id:
            return

        title = self.title_entry.get().strip() or "Ghi chú không tiêu đề"
        content = self.content_textbox.get("1.0", "end-1c")

        # Check existing note
        current_note = self.notes_manager.get_note_by_id(self.selected_note_id)
        if not current_note:
            return

        # Perform save
        updated_note = self.notes_manager.save_note(
            note_id=self.selected_note_id,
            title=title,
            content=content,
        )

        self.save_status_label.configure(text=f"✓ Đã lưu ({datetime.now().strftime('%H:%M:%S')})")

        # If this note is the active widget note, update desktop widget live!
        if updated_note.is_active:
            if self.widget_ref and hasattr(self.widget_ref, "set_note"):
                self.widget_ref.set_note(title=updated_note.title, content=updated_note.content)
            if self.on_active_note_changed:
                self.on_active_note_changed(updated_note)

        # Refresh sidebar list to reflect new title/snippet/timestamp
        self.refresh_notes_list()

    def delete_current_note(self) -> None:
        """Delete currently selected note with prompt."""
        if self.selected_note_id:
            self.delete_note_by_id(self.selected_note_id)

    def delete_note_by_id(self, note_id: str) -> None:
        """Delete note and select next available note."""
        all_notes = self.notes_manager.get_all_notes()
        if len(all_notes) <= 1:
            # Keep at least one note
            self.notes_manager.delete_note(note_id)
            self.create_new_note()
            return

        self.notes_manager.delete_note(note_id)
        
        # If deleted note was selected, select the first remaining note
        if self.selected_note_id == note_id:
            remaining = self.notes_manager.get_all_notes()
            if remaining:
                self.select_note(remaining[0].id)
        else:
            self.refresh_notes_list()

        # Check active note and update widget
        active_note = self.notes_manager.get_active_note()
        if active_note and self.widget_ref and hasattr(self.widget_ref, "set_note_object"):
            self.widget_ref.set_note_object(active_note)

    def set_current_as_active_widget(self) -> None:
        """Pin the currently selected note to the Desktop Square Widget."""
        if self.selected_note_id:
            self.set_active_note_id(self.selected_note_id)

    def set_active_note_id(self, note_id: str) -> None:
        """Set a note as active on Desktop Widget."""
        # Ensure content is saved first
        self.save_current_note(immediate=True)

        self.notes_manager.set_active_note(note_id)
        active_note = self.notes_manager.get_note_by_id(note_id)
        if not active_note:
            return

        # Update widget
        if self.widget_ref:
            if hasattr(self.widget_ref, "set_note_object"):
                self.widget_ref.set_note_object(active_note)
            elif hasattr(self.widget_ref, "set_note"):
                self.widget_ref.set_note(active_note.title, active_note.content)

        if self.on_active_note_changed:
            self.on_active_note_changed(active_note)

        # Update button and sidebar
        self._update_active_widget_button(True)
        self.refresh_notes_list()

    def _update_active_widget_button(self, is_active: bool) -> None:
        """Update style and text of the 'Hiển thị trên Widget Desktop' button."""
        if is_active:
            self.set_active_btn.configure(
                text="✓ Đang hiển thị trên Widget",
                fg_color=COLORS["accent_green"],
                hover_color=COLORS["accent_green_hover"],
            )
        else:
            self.set_active_btn.configure(
                text="📌 Hiển thị trên Widget Desktop",
                fg_color=COLORS["primary"],
                hover_color=COLORS["primary_hover"],
            )

    # =========================================================================
    # Realtime Editor Handlers & Debounce
    # =========================================================================

    def _on_editor_content_changed(self, event: Any = None) -> None:
        """Triggered on every keystroke in title or content."""
        self.save_status_label.configure(text="⏳ Chưa lưu...")
        self._update_word_char_counts()

        # Cancel previous debounce timer
        if self._save_timer and self._save_timer.is_alive():
            self._save_timer.cancel()

        # Debounce auto-save after 600ms
        self._save_timer = threading.Timer(0.6, self._async_save)
        self._save_timer.daemon = True
        self._save_timer.start()

    def _async_save(self) -> None:
        """Thread-safe auto-save invoker using tkinter after()."""
        try:
            self.after(0, self.save_current_note)
        except Exception:
            pass

    def _update_word_char_counts(self) -> None:
        """Calculate word count and character count for status display."""
        content = self.content_textbox.get("1.0", "end-1c")
        char_count = len(content)
        word_count = len(content.split()) if content.strip() else 0
        self.word_count_label.configure(text=f"{word_count:,} từ • {char_count:,} ký tự")

    def _on_search_query_changed(self, event: Any = None) -> None:
        """Filter notes list as user types in search entry."""
        self._search_query = self.search_entry.get().strip()
        self.refresh_notes_list()

    # =========================================================================
    # Bottom Bar Handlers (Theme, Speed, Widget, Startup)
    # =========================================================================

    def toggle_theme(self) -> None:
        """Toggle between Dark Mode and Light Mode."""
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.set_theme(new_theme)

    def set_theme(self, theme: str) -> None:
        """Apply theme across MainWindow, Settings, and Desktop Widget."""
        theme = theme.lower()
        if theme not in ("dark", "light"):
            theme = "dark"

        if self.current_theme == theme:
            return

        self.current_theme = theme
        ctk.set_appearance_mode(theme)

        # Update button text
        theme_icon = "🌙 Tối" if theme == "dark" else "☀️ Sáng"
        self.theme_btn.configure(text=f"Giao diện: {theme_icon}")

        # Update settings
        self.notes_manager.save_settings({"theme": theme})

        # Notify Desktop Widget
        if self.widget_ref and hasattr(self.widget_ref, "update_theme"):
            self.widget_ref.update_theme(theme)

        if self.on_widget_theme_changed:
            self.on_widget_theme_changed(theme)

    def _on_speed_slider_changed(self, val: float) -> None:
        """Handle real-time changes to the widget escalator speed slider."""
        speed = round(float(val), 1)
        if self.current_speed == speed:
            return

        self.current_speed = speed
        self.speed_label.configure(text=f"Tốc độ: {speed:.1f}x")

        # Update settings
        self.notes_manager.save_settings({"default_speed": speed})

        # Update Desktop Widget real-time
        if self.widget_ref and hasattr(self.widget_ref, "set_speed"):
            self.widget_ref.set_speed(speed)

        if self.on_widget_speed_changed:
            self.on_widget_speed_changed(speed)

    def update_speed_from_widget(self, speed: float) -> None:
        """Called when speed is changed directly on the Desktop Widget."""
        speed = round(float(speed), 1)
        if self.current_speed == speed:
            return

        self.current_speed = speed
        self.speed_label.configure(text=f"Tốc độ: {speed:.1f}x")
        self.speed_slider.set(speed)

    def _on_widget_switch_toggled(self) -> None:
        """Toggle visibility of the floating desktop widget."""
        is_visible = bool(self.widget_switch.get())
        self.set_widget_visibility(is_visible)

    def set_widget_visibility(self, visible: bool) -> None:
        """Show or hide the desktop square widget."""
        self.is_widget_visible = visible
        if visible:
            self.widget_switch.select()
            if self.widget_ref and hasattr(self.widget_ref, "show_widget"):
                self.widget_ref.show_widget()
        else:
            self.widget_switch.deselect()
            if self.widget_ref and hasattr(self.widget_ref, "hide_widget"):
                self.widget_ref.hide_widget()

        self.notes_manager.save_settings({"widget_visible": visible})

        if self.on_widget_toggle:
            self.on_widget_toggle(visible)

    def _on_startup_switch_toggled(self) -> None:
        """Toggle Windows autostart on boot."""
        enabled = bool(self.startup_switch.get())
        if enabled:
            success = startup.enable_startup()
            if not success:
                self.startup_switch.deselect()
        else:
            startup.disable_startup()

        self.notes_manager.save_settings({"autostart": enabled})

    def save_window_state(self) -> None:
        """Save window geometry and settings before exit or hide."""
        self.save_current_note(immediate=True)
        geometry = self.geometry()
        self.notes_manager.save_settings({
            "window_geometry": geometry,
            "theme": self.current_theme,
            "default_speed": self.current_speed,
            "widget_visible": self.is_widget_visible,
        })


if __name__ == "__main__":
    # Test standalone run of MainWindow
    app = MainWindow()
    app.mainloop()
