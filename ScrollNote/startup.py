"""
ScrollNote - Windows Startup Integration Module
Manages auto-start on Windows boot via Registry (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

# Platform check for Windows registry
try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULT_APP_NAME = "ScrollNote"


def _get_default_launch_command() -> str:
    r"""
    Construct the default startup command.
    Prefers pythonw.exe over python.exe to suppress console window,
    pointing to main.py in d:\ScrollNote or the project directory.
    """
    # 1. Determine script path
    base_dir = Path(__file__).resolve().parent
    main_script = base_dir / "main.py"
    if not main_script.exists():
        d_script = Path("d:/ScrollNote/main.py")
        if d_script.exists():
            main_script = d_script

    # 2. Determine python / pythonw executable
    executable = sys.executable
    if executable:
        exec_dir = Path(executable).parent
        pythonw = exec_dir / "pythonw.exe"
        if pythonw.exists():
            runner = str(pythonw)
        else:
            runner = executable
    else:
        runner = "pythonw.exe"

    return f'"{runner}" "{main_script}"'


def is_startup_enabled(app_name: str = DEFAULT_APP_NAME) -> bool:
    """
    Check if the application is set to start with Windows.

    :param app_name: Name of the registry value in HKCU Run key.
    :return: True if startup entry exists, False otherwise.
    """
    if not HAS_WINREG:
        return False

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_READ
        ) as key:
            try:
                winreg.QueryValueEx(key, app_name)
                return True
            except FileNotFoundError:
                return False
    except OSError:
        return False


def get_startup_command(app_name: str = DEFAULT_APP_NAME) -> Optional[str]:
    """
    Retrieve the current startup command string registered in HKCU Run key.

    :param app_name: Name of the registry value.
    :return: Command string if present, None otherwise.
    """
    if not HAS_WINREG:
        return None

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_READ
        ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, app_name)
                return str(val)
            except FileNotFoundError:
                return None
    except OSError:
        return None


def enable_startup(app_name: str = DEFAULT_APP_NAME, app_path: Optional[str] = None) -> bool:
    """
    Enable startup with Windows for the application.

    :param app_name: Name of the registry entry.
    :param app_path: Command or path to execute on boot. If None, auto-detected.
    :return: True if successfully registered, False on failure.
    """
    if not HAS_WINREG:
        print("[Startup] winreg is not available on this platform.")
        return False

    command_to_run = app_path if app_path else _get_default_launch_command()

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command_to_run)
            return True
    except OSError as e:
        print(f"[Startup] Failed to enable startup registry entry: {e}")
        return False


def disable_startup(app_name: str = DEFAULT_APP_NAME) -> bool:
    """
    Disable startup with Windows for the application.

    :param app_name: Name of the registry entry to delete.
    :return: True if disabled or was not enabled, False on failure.
    """
    if not HAS_WINREG:
        return True

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE
        ) as key:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                # Already not present
                pass
            return True
    except OSError as e:
        print(f"[Startup] Failed to delete startup registry entry: {e}")
        return False
