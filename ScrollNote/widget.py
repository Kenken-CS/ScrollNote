"""
ScrollNote - Desktop Floating Square Widget
==========================================
A modern, minimalist floating square desktop widget (gadget) for Windows.
Displays notes with a vertical escalator / teleprompter / marquee upward scrolling effect.

Features:
- Perfectly square floating window (default 280x280 pixels, customizable).
- Smooth continuous upward text scrolling (teleprompter style) with seamless infinite wrap-around.
- Modern rounded card aesthetic in both Dark Mode and Light Mode.
- Hover overlay controls: Pin (Always on Top), Prev/Next note, Play/Pause toggle,
  Speed controls (- / +), Theme toggle, Open Editor, and Close / Hide.
- Drag-and-drop repositioning anywhere on the screen.
- Right-click context menu with complete control suite.
- Mouse-wheel support for quick manual scrolling.
- Clean integration API for MainWindow, NotesManager, and background runners.
"""

import math
import sys
import tkinter as tk
from typing import Any, Callable, Dict, Optional, Tuple, Union


# Cohesive, modern color tokens for Dark & Light modes
THEMES: Dict[str, Dict[str, str]] = {
    "dark": {
        "bg": "#181825",            # Deep slate / Mantle base
        "card_bg": "#1e1e2e",       # Card background (Catppuccin Mocha)
        "border": "#313244",        # Subtle outer border
        "border_active": "#89b4fa", # Accent border
        "title": "#89b4fa",         # Pastel blue accent for note title
        "body": "#cdd6f4",          # Crisp, readable white/light-gray text
        "divider": "#45475a",       # Divider line between title and content
        "muted": "#6c7086",         # Secondary text / loop marker
        "handle": "#585b70",        # Subtle top drag handle
        "pill_bg": "#11111b",       # Floating controls pill background
        "pill_border": "#45475a",   # Controls pill border
        "btn_normal": "#cdd6f4",    # Button text normal
        "btn_hover": "#89b4fa",     # Button text hover
        "btn_active": "#f5c2e7",    # Button text active/pinned
        "btn_bg_hover": "#313244",  # Button background hover
        "menu_bg": "#1e1e2e",
        "menu_fg": "#cdd6f4",
        "menu_active_bg": "#313244",
        "menu_active_fg": "#89b4fa",
    },
    "light": {
        "bg": "#f8f9fa",            # Crisp clean off-white
        "card_bg": "#ffffff",       # Pure white card background
        "border": "#e2e8f0",        # Slate 200 border
        "border_active": "#2563eb", # Accent royal blue border
        "title": "#0f172a",         # Deep slate 900 bold title
        "body": "#334155",          # Slate 700 readable body text
        "divider": "#e2e8f0",       # Divider line
        "muted": "#94a3b8",         # Secondary text / loop marker
        "handle": "#cbd5e1",        # Subtle top drag handle
        "pill_bg": "#ffffff",       # Floating controls pill background
        "pill_border": "#cbd5e1",   # Controls pill border
        "btn_normal": "#1e293b",    # Button text normal
        "btn_hover": "#2563eb",     # Button text hover
        "btn_active": "#2563eb",    # Button text active/pinned
        "btn_bg_hover": "#f1f5f9",  # Button background hover
        "menu_bg": "#ffffff",
        "menu_fg": "#1e293b",
        "menu_active_bg": "#f1f5f9",
        "menu_active_fg": "#2563eb",
    },
}


class DesktopScrollWidget(tk.Toplevel):
    """
    Floating square desktop widget with vertical upward text scrolling.
    
    Can run standalone or as a child to a CTk / Tk master window.
    """

    def __init__(
        self,
        master: Optional[tk.Misc] = None,
        title: str = "ScrollNote Widget",
        note_title: str = "",
        note_content: str = "",
        speed: float = 1.5,
        theme: str = "dark",
        size: int = 280,
        x: Optional[int] = None,
        y: Optional[int] = None,
        is_topmost: bool = True,
        pause_on_hover: bool = True,
        on_open_editor: Optional[Callable[[], None]] = None,
        on_next_note: Optional[Callable[[], None]] = None,
        on_prev_note: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
        on_speed_changed: Optional[Callable[[float], None]] = None,
        on_theme_changed: Optional[Callable[[str], None]] = None,
        on_pause_toggled: Optional[Callable[[bool], None]] = None,
    ):
        # Ensure hidden master root if none is passed
        self._hidden_root: Optional[tk.Tk] = None
        if master is None:
            if tk._default_root is None:
                self._hidden_root = tk.Tk()
                self._hidden_root.withdraw()
                master = self._hidden_root
            else:
                master = tk._default_root

        super().__init__(master)

        # Window settings
        self._size = max(200, size)
        self._width = self._size
        self._height = self._size
        self._theme = theme if theme in THEMES else "dark"
        self._is_topmost = is_topmost
        self._pause_on_hover = pause_on_hover
        self._is_paused = False
        self._hover_paused = False
        self._is_hovered = False
        self._is_visible = True
        self._is_running = True

        # Speed and frame rate configuration
        # Base speed: 0.5 px per frame. At 50 FPS (20ms interval), 1.0x = 25 px/sec
        self._base_speed = 0.5
        self._speed = max(0.2, min(6.0, float(speed)))
        self._frame_interval_ms = 20  # ~50 FPS for buttery smooth escalator movement
        self._timer_id: Optional[str] = None

        # Content state
        self._note_title = note_title or "ScrollNote"
        self._note_content = (
            note_content
            or "Chào mừng bạn đến với ScrollNote!\nGhi chú chữ chạy dọc theo ô vuông desktop.\n\nNhấn chuột phải để tuỳ chỉnh hoặc mở ứng dụng chính."
        )

        # Callbacks
        self._on_open_editor = on_open_editor
        self._on_next_note = on_next_note
        self._on_prev_note = on_prev_note
        self._on_close = on_close
        self._on_position_changed = on_position_changed
        self._on_speed_changed = on_speed_changed
        self._on_theme_changed = on_theme_changed
        self._on_pause_toggled = on_pause_toggled

        # Drag tracking
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._is_dragging = False
        self.last_x = 100
        self.last_y = 100

        # Animation wrap tracking
        self._block_height = 100.0
        self._cycle_height = float(self._height)
        self._y0 = 36.0
        self._y1 = self._y0 + self._cycle_height

        # Configure window frame (frameless floating widget)
        self.title(title)
        self.overrideredirect(True)
        self.attributes("-topmost", self._is_topmost)
        self.resizable(False, False)

        # Initial screen position (default bottom-right or requested)
        self._init_window_geometry(x, y)

        # Setup Canvas
        colors = THEMES[self._theme]
        self.configure(bg=colors["card_bg"])
        self.canvas = tk.Canvas(
            self,
            width=self._width,
            height=self._height,
            bg=colors["card_bg"],
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Setup Overlay Buttons registration
        self._buttons: Dict[str, Dict[str, Any]] = {}
        self._active_hover_btn: Optional[str] = None

        # Build UI Elements
        self._build_static_decorations()
        self._rebuild_note_copies()
        self._build_overlay_controls()
        self._build_context_menu()

        # Bindings
        self._bind_events()

        # Start animation loop
        self._start_animation()

    # =========================================================================
    # Window Geometry & Position
    # =========================================================================

    def _init_window_geometry(self, x: Optional[int], y: Optional[int]) -> None:
        """Positions the window at specified coords or default bottom-right screen."""
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        if x is None or y is None:
            # Position near bottom-right with margin, e.g. above taskbar
            pos_x = max(20, screen_w - self._width - 40)
            pos_y = max(40, screen_h - self._height - 90)
        else:
            pos_x = x
            pos_y = y

        self.last_x = pos_x
        self.last_y = pos_y
        self.geometry(f"{self._width}x{self._height}+{pos_x}+{pos_y}")

    # =========================================================================
    # Visual Layout & Content Rendering
    # =========================================================================

    def _build_static_decorations(self) -> None:
        """Builds border card, subtle drag handle indicator."""
        colors = THEMES[self._theme]
        # Outer 1px modern card border
        self.canvas.create_rectangle(
            0,
            0,
            self._width - 1,
            self._height - 1,
            outline=colors["border"],
            width=1,
            tags=("border",),
        )
        # Subtle top drag handle (32px wide pill at top center)
        cx = self._width // 2
        self.canvas.create_line(
            cx - 16,
            6,
            cx + 16,
            6,
            fill=colors["handle"],
            width=3,
            capstyle="round",
            tags=("handle",),
        )

    def _rebuild_note_copies(self) -> None:
        """Renders the note content into two seamless wrapping copies."""
        self.canvas.delete("note_content")
        colors = THEMES[self._theme]
        padding_x = 18
        max_wrap_width = self._width - (padding_x * 2)

        # Temporary measure of one note block
        y_cursor = 0.0

        # Title text
        t_id = self.canvas.create_text(
            padding_x,
            y_cursor,
            text=self._note_title,
            font=("Segoe UI", 12, "bold"),
            fill=colors["title"],
            width=max_wrap_width,
            anchor="nw",
            tags=("measure_temp",),
        )
        t_bbox = self.canvas.bbox(t_id) or (padding_x, 0, max_wrap_width, 24)
        y_cursor = t_bbox[3] + 6

        # Subtle divider line
        self.canvas.create_line(
            padding_x,
            y_cursor,
            self._width - padding_x,
            y_cursor,
            fill=colors["divider"],
            width=1,
            tags=("measure_temp",),
        )
        y_cursor += 10

        # Body text
        b_id = self.canvas.create_text(
            padding_x,
            y_cursor,
            text=self._note_content,
            font=("Segoe UI", 10),
            fill=colors["body"],
            width=max_wrap_width,
            anchor="nw",
            tags=("measure_temp",),
        )
        b_bbox = self.canvas.bbox(b_id) or (padding_x, y_cursor, max_wrap_width, y_cursor + 40)
        y_cursor = b_bbox[3] + 16

        # Loop end marker
        m_id = self.canvas.create_text(
            self._width // 2,
            y_cursor,
            text="── ✦ ──",
            font=("Segoe UI", 9),
            fill=colors["muted"],
            anchor="n",
            tags=("measure_temp",),
        )
        m_bbox = self.canvas.bbox(m_id) or (0, y_cursor, self._width, y_cursor + 16)
        y_cursor = m_bbox[3] + 12

        # Record measured block height
        self._block_height = max(50.0, float(y_cursor))
        self.canvas.delete("measure_temp")

        # Cycle distance: guarantee spacing >= window height so wrap is 100% seamless
        gap = 46.0
        self._cycle_height = max(self._block_height + gap, float(self._height))

        # Build Copy 0
        self._draw_single_copy(tag="copy_0", y_offset=self._y0, colors=colors)

        # Build Copy 1
        self._y1 = self._y0 + self._cycle_height
        self._draw_single_copy(tag="copy_1", y_offset=self._y1, colors=colors)

        # Ensure borders and overlay always stay above text
        self.canvas.tag_raise("border")
        self.canvas.tag_raise("handle")
        self.canvas.tag_raise("overlay")

    def _draw_single_copy(self, tag: str, y_offset: float, colors: Dict[str, str]) -> None:
        """Draws one instance of the note block at the specified vertical offset."""
        padding_x = 18
        max_wrap_width = self._width - (padding_x * 2)

        # 1. Title
        t_id = self.canvas.create_text(
            padding_x,
            y_offset,
            text=self._note_title,
            font=("Segoe UI", 12, "bold"),
            fill=colors["title"],
            width=max_wrap_width,
            anchor="nw",
            tags=(tag, "note_content", "title_text"),
        )
        t_bbox = self.canvas.bbox(t_id) or (padding_x, y_offset, max_wrap_width, y_offset + 24)
        y_cur = t_bbox[3] + 6

        # 2. Divider
        self.canvas.create_line(
            padding_x,
            y_cur,
            self._width - padding_x,
            y_cur,
            fill=colors["divider"],
            width=1,
            tags=(tag, "note_content", "divider_line"),
        )
        y_cur += 10

        # 3. Content
        b_id = self.canvas.create_text(
            padding_x,
            y_cur,
            text=self._note_content,
            font=("Segoe UI", 10),
            fill=colors["body"],
            width=max_wrap_width,
            anchor="nw",
            tags=(tag, "note_content", "body_text"),
        )
        b_bbox = self.canvas.bbox(b_id) or (padding_x, y_cur, max_wrap_width, y_cur + 40)
        y_cur = b_bbox[3] + 16

        # 4. Loop marker
        self.canvas.create_text(
            self._width // 2,
            y_cur,
            text="── ✦ ──",
            font=("Segoe UI", 9),
            fill=colors["muted"],
            anchor="n",
            tags=(tag, "note_content", "loop_marker"),
        )

    # =========================================================================
    # Overlay Controls
    # =========================================================================

    def _build_overlay_controls(self) -> None:
        """Constructs sleek top & bottom floating pill control bars."""
        self.canvas.delete("overlay")
        self._buttons.clear()
        colors = THEMES[self._theme]

        # ---------------- Top Overlay Bar (y: 10 to 38) ----------------
        top_y1, top_y2 = 10, 38
        top_x1, top_x2 = 12, self._width - 12
        # Pill Background
        self.canvas.create_rectangle(
            top_x1,
            top_y1,
            top_x2,
            top_y2,
            fill=colors["pill_bg"],
            outline=colors["pill_border"],
            width=1,
            tags=("overlay", "overlay_bg", "top_pill"),
        )

        # Buttons in Top Bar: Pin, Prev, Play/Pause, Next, Editor, Close
        btn_defs = [
            ("btn_pin", "📌" if self._is_topmost else "📍", self.toggle_always_on_top),
            ("btn_prev", "◀", self._trigger_prev_note),
            ("btn_play", "▶" if self._is_paused else "⏸", self.toggle_play_pause),
            ("btn_next", "▶", self._trigger_next_note),
            ("btn_editor", "✏", self._trigger_open_editor),
            ("btn_close", "✕", self.hide_widget),
        ]

        num_btns = len(btn_defs)
        slot_w = (top_x2 - top_x1) / num_btns
        center_y = (top_y1 + top_y2) // 2

        for idx, (btn_name, icon_text, action) in enumerate(btn_defs):
            bx1 = top_x1 + idx * slot_w
            bx2 = bx1 + slot_w
            bcx = (bx1 + bx2) / 2

            # Hover highlight box
            h_id = self.canvas.create_rectangle(
                bx1 + 2,
                top_y1 + 2,
                bx2 - 2,
                top_y2 - 2,
                fill=colors["pill_bg"],
                outline="",
                tags=("overlay", f"h_{btn_name}"),
            )

            # Icon text
            fg_color = (
                colors["btn_active"]
                if btn_name == "btn_pin" and self._is_topmost
                else colors["btn_normal"]
            )
            t_id = self.canvas.create_text(
                bcx,
                center_y,
                text=icon_text,
                font=("Segoe UI", 10, "bold"),
                fill=fg_color,
                tags=("overlay", f"t_{btn_name}"),
            )

            self._buttons[btn_name] = {
                "bbox": (bx1, top_y1, bx2, top_y2),
                "action": action,
                "hover_id": h_id,
                "text_id": t_id,
                "icon": icon_text,
            }

        # ---------------- Bottom Overlay Bar (y: height-36 to height-10) ----------------
        bot_y1, bot_y2 = self._height - 36, self._height - 10
        bot_x1, bot_x2 = 16, self._width - 16

        # Pill Background
        self.canvas.create_rectangle(
            bot_x1,
            bot_y1,
            bot_x2,
            bot_y2,
            fill=colors["pill_bg"],
            outline=colors["pill_border"],
            width=1,
            tags=("overlay", "overlay_bg", "bot_pill"),
        )

        bot_cy = (bot_y1 + bot_y2) // 2

        # 1. Slower button (-)
        s_down_x1, s_down_x2 = bot_x1 + 4, bot_x1 + 46
        h_down = self.canvas.create_rectangle(
            s_down_x1,
            bot_y1 + 2,
            s_down_x2,
            bot_y2 - 2,
            fill=colors["pill_bg"],
            outline="",
            tags=("overlay", "h_btn_speed_down"),
        )
        t_down = self.canvas.create_text(
            (s_down_x1 + s_down_x2) / 2,
            bot_cy,
            text="🐢 −",
            font=("Segoe UI", 9, "bold"),
            fill=colors["btn_normal"],
            tags=("overlay", "t_btn_speed_down"),
        )
        self._buttons["btn_speed_down"] = {
            "bbox": (s_down_x1, bot_y1, s_down_x2, bot_y2),
            "action": self._speed_down,
            "hover_id": h_down,
            "text_id": t_down,
        }

        # 2. Speed Display Badge (Center)
        speed_lbl_x = (bot_x1 + bot_x2) / 2 - 14
        self.canvas.create_text(
            speed_lbl_x,
            bot_cy,
            text=f"{self._speed:.1f}x",
            font=("Segoe UI", 9, "bold"),
            fill=colors["btn_hover"],
            tags=("overlay", "speed_badge"),
        )

        # 3. Faster button (+)
        s_up_x1, s_up_x2 = speed_lbl_x + 22, speed_lbl_x + 64
        h_up = self.canvas.create_rectangle(
            s_up_x1,
            bot_y1 + 2,
            s_up_x2,
            bot_y2 - 2,
            fill=colors["pill_bg"],
            outline="",
            tags=("overlay", "h_btn_speed_up"),
        )
        t_up = self.canvas.create_text(
            (s_up_x1 + s_up_x2) / 2,
            bot_cy,
            text="+ 🐇",
            font=("Segoe UI", 9, "bold"),
            fill=colors["btn_normal"],
            tags=("overlay", "t_btn_speed_up"),
        )
        self._buttons["btn_speed_up"] = {
            "bbox": (s_up_x1, bot_y1, s_up_x2, bot_y2),
            "action": self._speed_up,
            "hover_id": h_up,
            "text_id": t_up,
        }

        # 4. Theme Toggle button (Right)
        theme_icon = "☀️" if self._theme == "dark" else "🌙"
        theme_x1, theme_x2 = bot_x2 - 40, bot_x2 - 4
        h_theme = self.canvas.create_rectangle(
            theme_x1,
            bot_y1 + 2,
            theme_x2,
            bot_y2 - 2,
            fill=colors["pill_bg"],
            outline="",
            tags=("overlay", "h_btn_theme"),
        )
        t_theme = self.canvas.create_text(
            (theme_x1 + theme_x2) / 2,
            bot_cy,
            text=theme_icon,
            font=("Segoe UI", 9),
            fill=colors["btn_normal"],
            tags=("overlay", "t_btn_theme"),
        )
        self._buttons["btn_theme"] = {
            "bbox": (theme_x1, bot_y1, theme_x2, bot_y2),
            "action": self._toggle_theme,
            "hover_id": h_theme,
            "text_id": t_theme,
        }

        # Initially hidden until hover
        if not self._is_hovered:
            self.canvas.itemconfigure("overlay", state="hidden")
        else:
            self.canvas.itemconfigure("overlay", state="normal")
            self.canvas.tag_raise("overlay")

    def _update_button_visuals(self) -> None:
        """Refreshes button states like Play/Pause icon, Speed label, Pin state."""
        colors = THEMES[self._theme]

        # Update play/pause icon
        if "btn_play" in self._buttons:
            icon = "▶" if self._is_paused else "⏸"
            self.canvas.itemconfigure("t_btn_play", text=icon)

        # Update pin icon & color
        if "btn_pin" in self._buttons:
            icon = "📌" if self._is_topmost else "📍"
            fg = colors["btn_active"] if self._is_topmost else colors["btn_normal"]
            self.canvas.itemconfigure("t_btn_pin", text=icon, fill=fg)

        # Update speed label
        self.canvas.itemconfigure("speed_badge", text=f"{self._speed:.1f}x")

        # Update theme icon
        if "btn_theme" in self._buttons:
            theme_icon = "☀️" if self._theme == "dark" else "🌙"
            self.canvas.itemconfigure("t_btn_theme", text=theme_icon)

    # =========================================================================
    # Context Menu
    # =========================================================================

    def _build_context_menu(self) -> None:
        """Creates rich right-click context menu."""
        colors = THEMES[self._theme]
        self._context_menu = tk.Menu(
            self,
            tearoff=0,
            bg=colors["menu_bg"],
            fg=colors["menu_fg"],
            activebackground=colors["menu_active_bg"],
            activeforeground=colors["menu_active_fg"],
            font=("Segoe UI", 9),
        )

        # 1. Play / Pause
        self._pause_label_var = "⏸ Tạm dừng cuộn" if not self._is_paused else "▶ Tiếp tục cuộn"
        self._context_menu.add_command(
            label=self._pause_label_var,
            command=self.toggle_play_pause,
        )

        self._context_menu.add_separator()

        # 2. Speed Submenu
        speed_menu = tk.Menu(
            self._context_menu,
            tearoff=0,
            bg=colors["menu_bg"],
            fg=colors["menu_fg"],
            activebackground=colors["menu_active_bg"],
            activeforeground=colors["menu_active_fg"],
            font=("Segoe UI", 9),
        )
        for spd_label, spd_val in [
            ("0.5x (Rất chậm)", 0.5),
            ("1.0x (Chậm)", 1.0),
            ("1.5x (Vừa phải)", 1.5),
            ("2.0x (Nhanh)", 2.0),
            ("3.0x (Rất nhanh)", 3.0),
        ]:
            speed_menu.add_command(
                label=spd_label,
                command=lambda v=spd_val: self.set_speed(v),
            )
        self._context_menu.add_cascade(label="Tốc độ cuộn chữ", menu=speed_menu)

        # 3. Always on top
        self._context_menu.add_command(
            label=f"{'✓ ' if self._is_topmost else '   '}Ghim trên cùng (Always on top)",
            command=self.toggle_always_on_top,
        )

        # 4. Pause on hover toggle
        self._context_menu.add_command(
            label=f"{'✓ ' if self._pause_on_hover else '   '}Tạm dừng khi di chuột",
            command=self._toggle_pause_on_hover,
        )

        # 5. Theme toggle
        other_theme = "Sáng" if self._theme == "dark" else "Tối"
        self._context_menu.add_command(
            label=f"Chuyển sang giao diện {other_theme}",
            command=self._toggle_theme,
        )

        self._context_menu.add_separator()

        # 6. Navigation
        self._context_menu.add_command(
            label="Ghi chú tiếp theo (Next Note)",
            command=self._trigger_next_note,
        )
        self._context_menu.add_command(
            label="Ghi chú trước đó (Prev Note)",
            command=self._trigger_prev_note,
        )

        self._context_menu.add_separator()

        # 7. Open Editor
        self._context_menu.add_command(
            label="Mở trình quản lý ghi chú (Editor)",
            command=self._trigger_open_editor,
        )

        # 8. Close / Hide
        self._context_menu.add_command(
            label="Ẩn widget này",
            command=self.hide_widget,
        )

    def _show_context_menu(self, event: tk.Event) -> None:
        """Rebuilds dynamic menu checkmarks and pops up at pointer."""
        self._build_context_menu()
        try:
            self._context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._context_menu.grab_release()

    # =========================================================================
    # Animation Loop (Teleprompter / Escalator)
    # =========================================================================

    def _start_animation(self) -> None:
        """Starts the periodic smooth animation loop."""
        self._is_running = True
        self._schedule_next_frame()

    def _schedule_next_frame(self) -> None:
        """Schedules next frame tick if running and visible."""
        if not self._is_running or not self._is_visible:
            return
        self._timer_id = self.after(self._frame_interval_ms, self._animation_step)

    def _animation_step(self) -> None:
        """Executes one frame of smooth upward vertical escalator scrolling."""
        if not self._is_running or not self._is_visible:
            return

        should_scroll = not self._is_paused and not (
            self._pause_on_hover and self._is_hovered
        )

        if should_scroll:
            dy = self._speed * self._base_speed
            self._scroll_delta(dy)

        self._schedule_next_frame()

    def _scroll_delta(self, dy: float) -> None:
        """
        Shifts the content vertically by dy pixels upward (or downward if dy < 0)
        and guarantees mathematically seamless wrapping.
        """
        self._y0 -= dy
        self._y1 -= dy

        self.canvas.move("copy_0", 0, -dy)
        self.canvas.move("copy_1", 0, -dy)

        if dy > 0:
            # Upward wrap for Copy 0
            if self._y0 + self._block_height <= 0:
                jump = (self._y1 + self._cycle_height) - self._y0
                self.canvas.move("copy_0", 0, jump)
                self._y0 = self._y1 + self._cycle_height

            # Upward wrap for Copy 1
            if self._y1 + self._block_height <= 0:
                jump = (self._y0 + self._cycle_height) - self._y1
                self.canvas.move("copy_1", 0, jump)
                self._y1 = self._y0 + self._cycle_height
        elif dy < 0:
            # Downward wrap for Copy 0 (e.g. mouse wheel reverse)
            if self._y0 >= self._height:
                jump = (self._y1 - self._cycle_height) - self._y0
                self.canvas.move("copy_0", 0, jump)
                self._y0 = self._y1 - self._cycle_height

            # Downward wrap for Copy 1
            if self._y1 >= self._height:
                jump = (self._y0 - self._cycle_height) - self._y1
                self.canvas.move("copy_1", 0, jump)
                self._y1 = self._y0 - self._cycle_height

    # =========================================================================
    # Event Handlers (Mouse, Drag, Wheel, Hover)
    # =========================================================================

    def _bind_events(self) -> None:
        """Binds mouse interactions and keyboard shortcuts."""
        self.canvas.bind("<Enter>", self._on_mouse_enter)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        self.canvas.bind("<Motion>", self._on_mouse_motion)
        self.canvas.bind("<Button-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_button_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)
        self.canvas.bind("<Button-3>", self._show_context_menu)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)

        # Keyboard shortcuts when widget is focused
        self.bind("<space>", lambda e: self.toggle_play_pause())
        self.bind("<Right>", lambda e: self._trigger_next_note())
        self.bind("<Left>", lambda e: self._trigger_prev_note())
        self.bind("<Up>", lambda e: self._speed_up())
        self.bind("<Down>", lambda e: self._speed_down())
        self.bind("<Escape>", lambda e: self.hide_widget())

    def _on_mouse_enter(self, event: tk.Event) -> None:
        """Reveals overlay controls and pauses escalator if pause_on_hover is enabled."""
        self._is_hovered = True
        self.canvas.itemconfigure("overlay", state="normal")
        self.canvas.tag_raise("overlay")
        self._update_button_visuals()

    def _on_mouse_leave(self, event: tk.Event) -> None:
        """Hides overlay controls and resumes scrolling."""
        self._is_hovered = False
        self._clear_hover_highlights()
        self.canvas.itemconfigure("overlay", state="hidden")

    def _on_mouse_motion(self, event: tk.Event) -> None:
        """Highlights buttons when hovered."""
        colors = THEMES[self._theme]
        found_btn: Optional[str] = None

        for btn_name, btn_info in self._buttons.items():
            bx1, by1, bx2, by2 = btn_info["bbox"]
            if bx1 <= event.x <= bx2 and by1 <= event.y <= by2:
                found_btn = btn_name
                break

        if found_btn != self._active_hover_btn:
            self._clear_hover_highlights()
            self._active_hover_btn = found_btn
            if found_btn and found_btn in self._buttons:
                h_id = self._buttons[found_btn].get("hover_id")
                if h_id:
                    self.canvas.itemconfigure(h_id, fill=colors["btn_bg_hover"])

    def _clear_hover_highlights(self) -> None:
        """Clears all button hover states."""
        colors = THEMES[self._theme]
        for btn_info in self._buttons.values():
            h_id = btn_info.get("hover_id")
            if h_id:
                self.canvas.itemconfigure(h_id, fill=colors["pill_bg"])
        self._active_hover_btn = None

    def _on_button_press(self, event: tk.Event) -> None:
        """Handles button clicks or initiates dragging."""
        self.focus_force()

        # Check if click hits an active overlay button
        if self._is_hovered:
            for btn_name, btn_info in self._buttons.items():
                bx1, by1, bx2, by2 = btn_info["bbox"]
                if bx1 <= event.x <= bx2 and by1 <= event.y <= by2:
                    action = btn_info.get("action")
                    if action:
                        action()
                    return

        # Otherwise, initiate window dragging
        self._is_dragging = True
        self._drag_start_x = event.x_root - self.winfo_x()
        self._drag_start_y = event.y_root - self.winfo_y()

    def _on_button_drag(self, event: tk.Event) -> None:
        """Moves window across the desktop."""
        if not self._is_dragging:
            return
        new_x = event.x_root - self._drag_start_x
        new_y = event.y_root - self._drag_start_y
        self.geometry(f"+{new_x}+{new_y}")
        self.last_x = new_x
        self.last_y = new_y

    def _on_button_release(self, event: tk.Event) -> None:
        """Concludes drag operation and invokes position changed callback."""
        if self._is_dragging:
            self._is_dragging = False
            self.last_x = self.winfo_x()
            self.last_y = self.winfo_y()
            if self._on_position_changed:
                self._on_position_changed(self.last_x, self.last_y)

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        """Allows manual scrolling with mouse wheel."""
        # Windows event.delta is typically multiples of 120
        delta = event.delta
        # Invert sign: delta > 0 is scroll up, moves text down; delta < 0 is scroll down, moves text up
        shift_amount = (delta / 120.0) * 24.0
        self._scroll_delta(-shift_amount)

    # =========================================================================
    # Public & Internal Control Actions
    # =========================================================================

    def set_note(self, title: str, content: str) -> None:
        """
        Updates the displayed note.
        Re-measures and recalculates seamless escalator wrap cycle.
        """
        self._note_title = title or "Chưa có tiêu đề"
        self._note_content = content or ""
        self._rebuild_note_copies()
        self._build_overlay_controls()

    def set_note_object(self, note: Any) -> None:
        """
        Convenience method to set note from Note dataclass or dict.
        """
        if hasattr(note, "title") and hasattr(note, "content"):
            title = note.title
            content = note.content
            if hasattr(note, "speed") and note.speed:
                try:
                    self.set_speed(float(note.speed))
                except (ValueError, TypeError):
                    pass
        elif isinstance(note, dict):
            title = note.get("title", "")
            content = note.get("content", "")
            if "speed" in note and note["speed"]:
                try:
                    self.set_speed(float(note["speed"]))
                except (ValueError, TypeError):
                    pass
        else:
            title = str(note)
            content = ""

        self.set_note(title, content)

    def set_speed(self, speed: Union[float, int]) -> None:
        """
        Updates escalator scroll speed (clamped between 0.2x and 6.0x).
        """
        try:
            val = float(speed)
        except (ValueError, TypeError):
            val = 1.5

        self._speed = max(0.2, min(6.0, round(val, 2)))
        self._update_button_visuals()

        if self._on_speed_changed:
            self._on_speed_changed(self._speed)

    def get_speed(self) -> float:
        """Returns the current scroll speed."""
        return self._speed

    def _speed_down(self) -> None:
        """Decrements speed by 0.25x."""
        new_speed = max(0.25, self._speed - 0.25)
        self.set_speed(new_speed)

    def _speed_up(self) -> None:
        """Increments speed by 0.25x."""
        new_speed = min(5.0, self._speed + 0.25)
        self.set_speed(new_speed)

    def toggle_play_pause(self) -> None:
        """Toggles between scrolling and paused."""
        self._is_paused = not self._is_paused
        self._update_button_visuals()
        if self._on_pause_toggled:
            self._on_pause_toggled(self._is_paused)

    def is_paused(self) -> bool:
        """Returns True if user has paused scrolling."""
        return self._is_paused

    def toggle_always_on_top(self) -> None:
        """Toggles always-on-top window state."""
        self._is_topmost = not self._is_topmost
        self.attributes("-topmost", self._is_topmost)
        self._update_button_visuals()

    def is_topmost(self) -> bool:
        """Returns True if widget is set to stay on top."""
        return self._is_topmost

    def _toggle_pause_on_hover(self) -> None:
        """Toggles auto-pause on hover behavior."""
        self._pause_on_hover = not self._pause_on_hover

    def update_theme(self, mode: str) -> None:
        """
        Applies Dark Mode or Light Mode to window, canvas, text, and controls.
        """
        mode = mode.lower()
        if mode not in THEMES:
            mode = "dark"
        self._theme = mode

        colors = THEMES[self._theme]
        self.configure(bg=colors["card_bg"])
        self.canvas.configure(bg=colors["card_bg"])

        # Update border and handle
        self.canvas.itemconfigure("border", outline=colors["border"])
        self.canvas.itemconfigure("handle", fill=colors["handle"])

        # Rebuild text copies with new color palette
        self._rebuild_note_copies()

        # Rebuild overlay controls
        self._build_overlay_controls()
        self._build_context_menu()

        if self._on_theme_changed:
            self._on_theme_changed(self._theme)

    def _toggle_theme(self) -> None:
        """Switches between Dark and Light mode."""
        next_theme = "light" if self._theme == "dark" else "dark"
        self.update_theme(next_theme)

    def show_widget(self) -> None:
        """Makes the widget visible and resumes animation."""
        self.deiconify()
        self._is_visible = True
        self._schedule_next_frame()

    def hide_widget(self) -> None:
        """Hides the widget and stops animation timer to save CPU."""
        self.withdraw()
        self._is_visible = False
        if self._timer_id:
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

        if self._on_close:
            self._on_close()

    def get_state(self) -> Dict[str, Any]:
        """Returns snapshot of widget state for settings persistence."""
        return {
            "x": self.last_x,
            "y": self.last_y,
            "size": self._size,
            "speed": self._speed,
            "is_topmost": self._is_topmost,
            "is_paused": self._is_paused,
            "pause_on_hover": self._pause_on_hover,
            "theme": self._theme,
            "is_visible": self._is_visible,
        }

    # =========================================================================
    # Internal Callback Triggers
    # =========================================================================

    def _trigger_open_editor(self) -> None:
        """Notifies coordinator/UI to bring up the main editor window."""
        if self._on_open_editor:
            self._on_open_editor()

    def _trigger_next_note(self) -> None:
        """Notifies coordinator/UI to cycle to next note."""
        if self._on_next_note:
            self._on_next_note()

    def _trigger_prev_note(self) -> None:
        """Notifies coordinator/UI to cycle to previous note."""
        if self._on_prev_note:
            self._on_prev_note()

    def destroy(self) -> None:
        """Clean shutdown canceling any pending timer."""
        self._is_running = False
        self._is_visible = False
        if self._timer_id:
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
        super().destroy()
        if self._hidden_root:
            try:
                self._hidden_root.destroy()
            except Exception:
                pass


# =============================================================================
# Standalone Interactive Demo & Self-Test
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Starting ScrollNote DesktopScrollWidget Standalone Demo...")
    print("=" * 60)

    demo_notes = [
        {
            "title": "📌 Nhiệm vụ trọng tâm hôm nay",
            "content": (
                "1. Hoàn thành module Floating Desktop Widget.\n"
                "2. Kiểm tra hiệu ứng chữ chạy dọc Escalator mượt mà.\n"
                "3. Kiểm thử Dark Mode và Light Mode.\n"
                "4. Đảm bảo hỗ trợ tiếng Việt có dấu đầy đủ.\n\n"
                "💡 Mẹo: Rê chuột vào để hiện thanh công cụ điều khiển!"
            ),
        },
        {
            "title": "☕ Ý tưởng ScrollNote",
            "content": (
                "Một tiện ích ghi chú thông minh nổi trên màn hình.\n"
                "Chữ tự động cuộn lên liên tục như băng chuyền / máy nhắc chữ (teleprompter).\n\n"
                "Không bao giờ bỏ sót những lời nhắc quan trọng!"
            ),
        },
        {
            "title": "🎯 Danh ngôn truyền cảm hứng",
            "content": (
                "\"Cách tốt nhất để bắt đầu là ngừng nói và bắt đầu làm.\"\n"
                "- Walt Disney\n\n"
                "\"Sự đơn giản là tinh hoa tối thượng của sự tinh tế.\"\n"
                "- Leonardo da Vinci"
            ),
        },
    ]

    current_idx = [0]

    def on_editor():
        print("[Event] User requested Open Editor!")

    def on_next():
        current_idx[0] = (current_idx[0] + 1) % len(demo_notes)
        note = demo_notes[current_idx[0]]
        widget.set_note(note["title"], note["content"])
        print(f"[Event] Next note: {note['title']}")

    def on_prev():
        current_idx[0] = (current_idx[0] - 1) % len(demo_notes)
        note = demo_notes[current_idx[0]]
        widget.set_note(note["title"], note["content"])
        print(f"[Event] Prev note: {note['title']}")

    def on_pos(x, y):
        print(f"[Event] Widget repositioned to: ({x}, {y})")

    def on_spd(spd):
        print(f"[Event] Speed adjusted to: {spd:.2f}x")

    def on_thm(thm):
        print(f"[Event] Theme switched to: {thm}")

    def on_cls():
        print("[Event] Widget closed/hidden. Exiting demo...")
        widget.destroy()
        sys.exit(0)

    # Initialize demo widget
    initial_note = demo_notes[0]
    widget = DesktopScrollWidget(
        title="ScrollNote Demo",
        note_title=initial_note["title"],
        note_content=initial_note["content"],
        speed=1.5,
        theme="dark",
        size=280,
        on_open_editor=on_editor,
        on_next_note=on_next,
        on_prev_note=on_prev,
        on_position_changed=on_pos,
        on_speed_changed=on_spd,
        on_theme_changed=on_thm,
        on_close=on_cls,
    )

    print("Widget launched!")
    print("- Drag widget by dragging the card background.")
    print("- Hover over widget to reveal controls.")
    print("- Right-click for context menu.")
    print("- Mouse-wheel to manually scroll up/down.")

    widget.mainloop()
