import sys
import os
import subprocess
from pathlib import Path

def current_keyboard_layout_as_json_path(_layout: str) -> str:
    if _layout:
        return Path(__file__).parent / f"{_layout}.json"
 
    layout = get_keyboard_layout()
    layout_type = layout["layout_type"].lower()
    candidate = Path(__file__).parent / f"{layout_type}.json"
    if candidate.exists():
        return candidate
 
    fallback = Path(__file__).parent / "qwerty.json"
    print(
        f"[keyboard] No mapping file for detected layout '{layout_type}' "
        f"(lang_code={layout['lang_code']!r}) - falling back to qwerty.json. "
        f"Add a '{layout_type}.json' next to this file to override, or set "
        f"'layout' explicitly in this project's app_config/defaults.toml."
    )
    return fallback

        

def get_keyboard_layout() -> dict:
    lang_code = "Unknown"
    # qwertz_locales = ["de-at", "de-de", "de-ch", "de", "at", "ch", "0x0c07", "0x0407"]

    # -------------------------------------------------------------
    # 1. LINUX DETECTION
    # -------------------------------------------------------------
    if sys.platform.startswith("linux"):
        # Try X11 / setxkbmap first
        try:
            output = subprocess.check_output(["setxkbmap", "-query"], stderr=subprocess.DEVNULL).decode()
            layout = ""
            variant = ""
            for line in output.splitlines():
                if line.startswith("layout:"):
                    layout = line.split(":")[1].strip()
                elif line.startswith("variant:"):
                    variant = line.split(":")[1].strip()
            
            lang_code = f"{layout}({variant})" if variant else layout
        except Exception:
            pass

        # Fallback for Wayland (e.g. GNOME/KDE on Fedora/Ubuntu) or missing setxkbmap
        if not lang_code or lang_code == "Unknown":
            try:
                # Query localectl system config
                output = subprocess.check_output(["localectl", "status"], stderr=subprocess.DEVNULL).decode()
                for line in output.splitlines():
                    if "X11 Layout" in line:
                        lang_code = line.split(":")[1].strip()
                        break
            except Exception:
                # Last resort fallback to LANG environment variable
                lang_code = os.environ.get("LANG", "Unknown").split(".")[0].replace("_", "-")

    # -------------------------------------------------------------
    # 2. WINDOWS DETECTION
    # -------------------------------------------------------------
    elif sys.platform == "win32":
        import ctypes
        user32 = ctypes.windll.user32

        hwnd = user32.GetForegroundWindow()
        thread_id = user32.GetWindowThreadProcessId(hwnd, 0)
        hkl = user32.GetKeyboardLayout(thread_id)
        lang_id = hkl & 0xFFFF

        windows_locales = {
            0x0C07: "de-AT",  # German (Austria)
            0x0407: "de-DE",  # German (Germany)
            0x0807: "de-CH",  # German (Switzerland)
            0x0409: "en-US",  # English (US)
            0x0809: "en-GB",  # English (UK)
        }

        # Check all loaded layout handles if active thread defaults to en-US
        if lang_id not in [0x0C07, 0x0407, 0x0807]:
            num_layouts = user32.GetKeyboardLayoutList(0, None)
            if num_layouts > 0:
                layouts = (ctypes.c_void_p * num_layouts)()
                user32.GetKeyboardLayoutList(num_layouts, layouts)
                for handle in layouts:
                    lid = handle & 0xFFFF
                    if lid in [0x0C07, 0x0407, 0x0807]:
                        lang_id = lid
                        break

        lang_code = windows_locales.get(lang_id, f"0x{lang_id:04x}")

    # -------------------------------------------------------------
    # 3. EVALUATE QWERTZ VS QWERTY
    # -------------------------------------------------------------
    base = lang_code.lower().split("-")[0].split("(")[0]
    layout_type = "QWERTZ" if base in {"de", "at", "ch"} else "QWERTY"

    return {
        "layout_type": layout_type,
        "lang_code": lang_code,
        "platform": sys.platform
    }
    