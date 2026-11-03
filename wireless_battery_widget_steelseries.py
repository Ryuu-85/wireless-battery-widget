import asyncio
import base64
import ctypes
import ctypes.wintypes
import ctypes.wintypes as wt
import hashlib
import json
import os
import queue
import re
import socket
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import BOTH, LEFT, RIGHT, BooleanVar, Button, Canvas, Frame, Label, Menu, Scale, Tk, Toplevel, filedialog, messagebox, simpledialog

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageTk
except Exception:
    Image = ImageEnhance = ImageFilter = ImageOps = ImageTk = None


APP_NAME = "Wireless Battery Widget"
APP_USER_MODEL_ID = "Codex.WirelessBatteryWidget"
REFRESH_SECONDS = 60
POWERSHELL_TIMEOUT = 12

BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "wireless_battery_widget_config.json"
ICON_PATH = BASE_DIR / "wireless_battery_widget.ico"
BACKGROUND_DIR = BASE_DIR / "backgrounds"
DSH_USAGE_PATH = Path.home() / ".dsh" / ".dshw-usage.json"
DSH_CREDENTIALS_PATH = Path.home() / ".dsh" / ".credentials.yaml"
DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"
NOTIFY_SCRIPT = BASE_DIR / "low_battery_notify.ps1"
RUN_BAT_PATH = BASE_DIR / "run_wireless_battery_widget.bat"
STARTUP_LINK_NAME = "Wireless Battery Widget.lnk"
ATK_HELPER_SCRIPT = BASE_DIR / "atk_v75x_battery_probe.js"
ATK_TASK_NAME = "WirelessBatteryWidget-ATKHUB"
ATK_HIDE_TASK_NAME = "WirelessBatteryWidget-HideATKHUB"

DEFAULT_CONFIG = {
    "refresh_seconds": REFRESH_SECONDS,
    "always_on_top": False,
    "aggressive_topmost": False,
    "taskbar_alt_tab_mode": True,
    "restore_after_show_desktop": True,
    "opacity": 0.92,
    "background_image": "",
    "background_cache": "",
    "background_blur": 8,
    "background_crop": [0.0, 0.0, 1.0, 1.0],
    "position": {"x": 40, "y": 60},
    "dock_bottom_right": True,
    "bottom_right_margin": 18,
    "name_filters": [
        "Logitech",
        "Logi",
        "LIGHTSPEED",
        "Razer",
        "Viper",
        "BlackWidow",
        "黑寡妇",
        "DeathAdder",
        "Basilisk",
        "Naga",
        "Cobra",
        "Huntsman",
        "Ornata",
        "Barracuda",
        "BlackShark",
        "Kraken",
        "SteelSeries",
        "Arctis",
        "Aerox",
        "Rival",
        "Sensei",
        "Nova",
        "ATK",
        "ZOWIE",
        "BenQ",
        "Feizhi",
        "Flydigi",
        "PRO X",
        "Mouse",
        "Keyboard",
        "Headset",
        "Xbox",
    ],
    "hide_unknown": False,
    "show_devices_without_reading": False,
    "low_battery_threshold": 20,
    "notifications_enabled": True,
    "notification_cooldown_minutes": 30,
    "mute_notifications_while_fullscreen": True,
    "low_battery_active_keys": [],
    "last_low_battery_notifications": {},
    "max_cached_battery_age_seconds": 300,
    "force_flydigi_name": False,
    "flydigi_bluetooth_addresses": [],
    "prefer_windows_bluetooth_name": True,
    "enable_ble_probe": False,
    "enable_lghub": True,
    "enable_razer_synapse_log": True,
    "enable_steelseries_hid": True,
    "enable_steelseries_gg_log": True,
    "enable_atk_hub_probe": True,
    "auto_restart_atk_hub_reader": False,
    "auto_start_atk_hub_reader": False,
    "use_atk_hub_scheduled_task": True,
    "atk_hub_task_name": ATK_TASK_NAME,
    "atk_hub_hide_task_name": ATK_HIDE_TASK_NAME,
    "hide_atk_hub_window": True,
    "atk_cached_battery_age_seconds": 1800,
    "atk_last_battery_level": None,
    "atk_last_battery_time": 0,
    "node_path": "",
    "atk_hub_path": "",
}

KNOWN_USB_NAMES = {
    ("VID_1532", "PID_00C1"): "Razer Viper V3 Pro",
    ("VID_1532", "PID_02D5"): "Razer BlackWidow V4 Tenkeyless Hyperspeed",
    ("VID_320F", "PID_5055"): "ATK V75X",
    ("VID_320F", "PID_5088"): "ATK V75X",
    ("VID_04A5", "PID_800A"): "BenQ ZOWIE Gaming Mouse",
    ("VID_1038", "PID_12AD"): "SteelSeries Arctis 7",
}

USB_REQUIREMENTS = {
    "Razer Viper V3 Pro": ("VID_1532", "PID_00C1"),
    "Razer BlackWidow V4 Tenkeyless Hyperspeed": ("VID_1532", "PID_02D5"),
    "PRO X Wireless Gaming Headset": ("VID_046D", "PID_0ABA"),
    "Logitech PRO X Wireless Gaming Headset": ("VID_046D", "PID_0ABA"),
    "ATK V75X": ("VID_320F", "PID_5055"),
    "BenQ ZOWIE Gaming Mouse": ("VID_04A5", "PID_800A"),
    "SteelSeries Arctis 7": ("VID_1038", "PID_12AD"),
}

USB_ALTERNATE_REQUIREMENTS = {
    "ATK V75X": [("VID_320F", "PID_5055"), ("VID_320F", "PID_5088")],
}

VENDOR_USB_NAMES = {
    "VID_1532": "Razer Device",
    "VID_046D": "Logitech Device",
    "VID_1038": "SteelSeries Device",
}

RAZER_DEVICE_NAME_PATTERN = re.compile(
    r"Razer|Viper|DeathAdder|Basilisk|Naga|Cobra|BlackWidow|黑寡妇|Huntsman|Ornata|Barracuda|BlackShark|Kraken|Leviathan",
    re.IGNORECASE,
)

LOGITECH_DEVICE_NAME_PATTERN = re.compile(
    r"Logitech|Logi|G\s?PRO|G\s?502|G\s?903|G\s?915|G\s?733|G\s?435|G\s?PRO\s?X|LIGHTSPEED|Powerplay",
    re.IGNORECASE,
)

STEELSERIES_DEVICE_NAME_PATTERN = re.compile(
    r"SteelSeries|Arctis|Aerox|Rival|Sensei|Nova\s?(?:Pro|Wireless)?",
    re.IGNORECASE,
)

# HID battery query parameters.  The Arctis 7 (2019) protocol is documented by
# the open-source steelseries-arctis-battery project; other SteelSeries models
# often share the same 31-byte query but are only probed when their product
# string matches Arctis.
STEELSERIES_HID_MODELS = {
    0x12AD: ("SteelSeries Arctis 7", 31, 31, b"\x06\x18", 2),
}


@dataclass
class DeviceBattery:
    name: str
    level: int | None
    source: str
    status: str = ""


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_CONFIG.copy()
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        return DEFAULT_CONFIG.copy()
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    merged["position"] = {**DEFAULT_CONFIG["position"], **merged.get("position", {})}
    merged["name_filters"] = list(dict.fromkeys([*DEFAULT_CONFIG["name_filters"], *merged.get("name_filters", [])]))
    return merged


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def write_error_log(text: str) -> None:
    try:
        (BASE_DIR / "wireless_battery_widget_error.log").write_text(text, encoding="utf-8")
    except Exception:
        pass


def existing_path(value: str | Path | None) -> Path | None:
    if not value:
        return None
    try:
        path = Path(str(value)).expanduser()
        return path if path.exists() else None
    except Exception:
        return None


GENERIC_DEVICE_NODE = re.compile(
    r"^(?:Razer|Logitech|SteelSeries)\s+(?:Device|Control Device)\b|^Razer Device:|^Logitech Device$",
    re.IGNORECASE,
)
VENDOR_PATTERNS = {
    "razer": re.compile(r"razer|blackwidow|viper|deathadder|basilisk|naga|cobra|huntsman|ornata|barracuda|blackshark|kraken", re.IGNORECASE),
    "logitech": re.compile(r"logitech|logi|lightspeed|pro x|g hub", re.IGNORECASE),
    "steelseries": re.compile(r"steelseries|arctis|aerox|rival|sensei|nova", re.IGNORECASE),
    "atk": re.compile(r"\batk\b|\bvxe\b", re.IGNORECASE),
    "flydigi": re.compile(r"flydigi|feizhi|direwolf", re.IGNORECASE),
    "xbox": re.compile(r"xbox|xinput", re.IGNORECASE),
}


def device_vendor(name: str) -> str:
    for vendor, pattern in VENDOR_PATTERNS.items():
        if pattern.search(name or ""):
            return vendor
    return ""


def compact_source(source: str) -> str:
    """Turn long collector labels into one short tag that fits the row."""
    text = re.sub(r"\s+", " ", source or "").strip()
    replacements = (
        (r"Logitech G HUB", "G HUB"),
        (r"Razer Synapse(?: 4)?", "Synapse"),
        (r"SteelSeries GG", "GG"),
        (r"SteelSeries HID", "HID"),
        (r"Windows Settings Bluetooth", "Bluetooth"),
        (r"Windows BLE Battery Service", "BLE"),
        (r"Windows (?:HIDClass|PnP|Mouse|Keyboard|Bluetooth)", "USB"),
        (r"ATK HUB.*", "ATK HUB"),
        (r"XInput.*", "XInput"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text or "device"


def background_cache_file(path: Path) -> Path:
    extension = path.suffix.lower()
    if extension not in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}:
        extension = ".png"
    return BACKGROUND_DIR / f"background{extension}"


def cache_background_image(path: Path) -> Path | None:
    """Keep a private copy, so moving the original file cannot blank the widget."""
    try:
        BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
        target = background_cache_file(path)
        for old in BACKGROUND_DIR.glob("background.*"):
            if old != target:
                try:
                    old.unlink()
                except OSError:
                    pass
        shutil.copy2(path, target)
        return target
    except Exception:
        return None


def find_moved_background(file_name: str) -> Path | None:
    """Find a moved wallpaper by name in the folders a user normally uses."""
    if not file_name:
        return None
    roots = [BASE_DIR, BASE_DIR.parent, Path.home() / "Desktop", Path.home() / "Pictures", Path.home() / "Downloads", Path.home() / "Documents"]
    skip_dirs = {"node_modules", ".git", "__pycache__", "appdata", "windows", "$recycle.bin", "system volume information"}
    visited = 0
    for root in roots:
        try:
            if not root.is_dir():
                continue
            direct = root / file_name
            if direct.is_file():
                return direct
            base_depth = len(root.parts)
            for dirpath, dirnames, filenames in os.walk(root):
                visited += 1
                if visited > 4000:
                    return None
                if file_name in filenames:
                    return Path(dirpath) / file_name
                if len(Path(dirpath).parts) - base_depth >= 2:
                    dirnames[:] = []
                else:
                    dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in skip_dirs]
        except OSError:
            continue
    return None


def resolve_background_path(config: dict, search_moved: bool = True) -> tuple[Path | None, str]:
    """Return the best picture for the backdrop and whether it came from the cache.

    Order: configured file -> cached copy -> file found under a common folder.
    The cache is refreshed whenever the original exists, so moving or renaming
    the original later does not make the background disappear.
    """
    raw = str(config.get("background_image") or "").strip().strip('"')
    original: Path | None = None
    if raw:
        try:
            candidate = Path(os.path.expandvars(raw)).expanduser()
            if not candidate.is_absolute():
                candidate = BASE_DIR / candidate
            if candidate.is_file():
                original = candidate
        except Exception:
            original = None
    if original is None and raw and search_moved:
        moved = find_moved_background(Path(raw).name)
        if moved:
            original = moved
            config["background_image"] = str(moved)
            try:
                save_config(config)
            except Exception:
                pass
    cache_value = str(config.get("background_cache") or "").strip()
    cache = BASE_DIR / cache_value if cache_value else None
    if original is not None:
        if Image is not None:
            stale = cache is None or not cache.is_file()
            if not stale:
                try:
                    source_stat, cache_stat = original.stat(), cache.stat()
                    stale = source_stat.st_size != cache_stat.st_size or abs(source_stat.st_mtime - cache_stat.st_mtime) > 2
                except OSError:
                    stale = True
            if stale:
                cached = cache_background_image(original)
                if cached:
                    config["background_cache"] = str(cached.relative_to(BASE_DIR)).replace("\\", "/")
                    try:
                        save_config(config)
                    except Exception:
                        pass
        return original, "ok"
    if cache is not None and cache.is_file():
        return cache, "cache"
    return None, "missing"


def read_dsh_account_grant() -> tuple[str, str] | None:
    """Read the DSH Platform grant without logging it."""
    try:
        text = DSH_CREDENTIALS_PATH.read_text(encoding="utf-8-sig")
    except Exception:
        return None
    block_match = re.search(r"^  deepseek-account-platform/default:\s*$([\s\S]*?)(?=^  \S|\Z)", text, re.MULTILINE)
    block = block_match.group(1) if block_match else text
    token_match = re.search(r"^\s*token:\s*['\"]?([^'\"\s]+)", block, re.MULTILINE)
    issuer_match = re.search(r"^\s*issuer:\s*['\"]?([^'\"\s]+)", block, re.MULTILINE)
    if not token_match:
        return None
    token = token_match.group(1)
    issuer = issuer_match.group(1) if issuer_match else "https://platform.deepseek.com"
    if not issuer.startswith("https://"):
        return None
    return token, issuer.rstrip("/")


def read_dsh_account_balance() -> dict | None:
    """Ask the DSH account Platform for the live wallet balance.

    This is the same call DSH's own account panel makes: the stored grant goes
    in x-dsh-auth-token to /api/v0/users/get_user_summary.  It reflects top-ups,
    bonuses and every spend immediately, unlike the local whale ledger.
    """
    grant = read_dsh_account_grant()
    if not grant:
        return None
    token, issuer = grant
    try:
        request = urllib.request.Request(
            issuer + "/api/v0/users/get_user_summary",
            headers={
                "x-dsh-auth-token": token,
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            root = json.loads(response.read().decode("utf-8"))
        if root.get("code") not in (0, None):
            return None
        payload = root.get("data") or {}
        if payload.get("biz_code") not in (0, None):
            return None
        business = payload.get("biz_data") or {}
        wallets = [w for w in [*(business.get("normal_wallets") or []), *(business.get("bonus_wallets") or [])] if isinstance(w, dict)]
        currencies = [str(w.get("currency") or "") for w in wallets if w.get("currency")]
        currency = "CNY" if "CNY" in currencies else (currencies[0] if currencies else "CNY")
        total = Decimal(0)
        found = False
        for wallet in wallets:
            if str(wallet.get("currency") or "") != currency:
                continue
            try:
                total += Decimal(str(wallet.get("balance")))
                found = True
            except (InvalidOperation, TypeError, ValueError):
                continue
        if not found:
            return None
        return {
            "balance": float(total),
            "today": None,
            "currency": currency,
            "fetched_at": time.time(),
            "source": "DSH account",
        }
    except Exception:
        return None


def read_deepseek_balance() -> dict | None:
    """Read the DeepSeek account balance.

    Order: explicit API key -> live DSH account platform -> local whale ledger.
    The ledger is only a fallback because it can be minutes or hours stale.
    """
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        try:
            request = urllib.request.Request(DEEPSEEK_BALANCE_URL, headers={"Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
            infos = data.get("balance_infos") or []
            info = infos[0] if infos else {}
            amount = float(info.get("total_balance"))
            return {
                "balance": amount,
                "today": None,
                "currency": str(info.get("currency") or "CNY"),
                "fetched_at": time.time(),
                "source": "API",
            }
        except Exception:
            pass
    account = read_dsh_account_balance()
    if account:
        return account
    try:
        if DSH_USAGE_PATH.is_file():
            data = json.loads(DSH_USAGE_PATH.read_text(encoding="utf-8-sig"))
            age = max(0.0, time.time() - DSH_USAGE_PATH.stat().st_mtime)
            stale = age > 600
            amount = data.get("lastBalance")
            if isinstance(amount, (int, float)) and not isinstance(amount, bool):
                today = data.get("todayUsage")
                return {
                    "balance": float(amount),
                    "today": float(today) if isinstance(today, (int, float)) and not isinstance(today, bool) else None,
                    "currency": "CNY",
                    "fetched_at": DSH_USAGE_PATH.stat().st_mtime,
                    "source": "DSH",
                    "stale": stale,
                }
            latest = None
            for book in ((data.get("accounting") or {}).get("books") or {}).values():
                for day in (book.get("days") or {}).values():
                    units, at = day.get("lastUnits"), day.get("lastAt") or 0
                    if isinstance(units, (int, float)) and (latest is None or at > latest[0]):
                        latest = (at, units)
            if latest:
                return {"balance": float(latest[1]) / 1e8, "today": None, "currency": "CNY", "fetched_at": DSH_USAGE_PATH.stat().st_mtime, "source": "DSH", "stale": stale}
    except Exception:
        pass
    return None


def format_money(value: float | None, currency: str = "CNY") -> str:
    if value is None:
        return "—"
    symbol = "¥" if currency.upper() == "CNY" else "$" if currency.upper() == "USD" else ""
    return f"{symbol}{value:,.2f}"



def resolve_node_path(config: dict) -> Path | str | None:
    configured = existing_path(config.get("node_path"))
    if configured:
        return configured
    candidates = [
        BASE_DIR / "node.exe",
        BASE_DIR / "node" / "node.exe",
        BASE_DIR / "tools" / "node.exe",
        BASE_DIR / "tools" / "node" / "node.exe",
        BASE_DIR.parent / "node" / "node.exe",
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return "node"


def resolve_atk_hub_path(config: dict) -> Path | None:
    configured = existing_path(config.get("atk_hub_path"))
    if configured and (configured / "ATK HUB.exe").exists():
        return configured
    env_path = existing_path(os.environ.get("ATK_HUB_PATH"))
    if env_path and (env_path / "ATK HUB.exe").exists():
        return env_path

    candidates: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        root = existing_path(os.environ.get(env_name))
        if root:
            candidates.extend([root / "ATK HUB", root / "ATK-HUB", root / "V HUB", root / "VXE HUB"])
            if env_name == "LOCALAPPDATA":
                candidates.extend([
                    root / "Programs" / "ATK HUB",
                    root / "Programs" / "ATK-HUB",
                    root / "Programs" / "V HUB",
                    root / "Programs" / "VXE HUB",
                ])
    for drive in ("C", "D", "E", "F"):
        candidates.extend([
            Path(f"{drive}:/software/ATK HUB"),
            Path(f"{drive}:/Program Files/ATK HUB"),
            Path(f"{drive}:/Program Files (x86)/ATK HUB"),
        ])
    for candidate in candidates:
        if (candidate / "ATK HUB.exe").exists():
            return candidate
    return None


def restart_atk_hub_with_debug(atk_hub_path: Path) -> bool:
    if os.name != "nt" or not (atk_hub_path / "ATK HUB.exe").exists():
        return False
    exe = str((atk_hub_path / "ATK HUB.exe").resolve()).replace("'", "''")
    cwd = str(atk_hub_path.resolve()).replace("'", "''")
    script = rf"""
$procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {{ $_.Name -eq 'ATK HUB.exe' }}
foreach ($p in $procs) {{
  try {{ Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }} catch {{}}
}}
Start-Sleep -Milliseconds 800
Start-Process -FilePath '{exe}' -WorkingDirectory '{cwd}' -ArgumentList @('--remote-debugging-port=9224','--remote-allow-origins=*') -WindowStyle Minimized
"""
    run_powershell(script, timeout=8)
    time.sleep(4)
    version = run_powershell(
        "try { (Invoke-RestMethod http://127.0.0.1:9224/json/version -TimeoutSec 2).'Protocol-Version' } catch { '' }",
        timeout=5,
    )
    return bool(version.strip())


def is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.6):
            return True
    except Exception:
        return False


def is_atk_hub_task_installed(config: dict) -> bool:
    task_name = str(config.get("atk_hub_task_name") or ATK_TASK_NAME).replace("'", "''")
    out = run_powershell(f"if (Get-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue) {{ 'true' }}", timeout=5)
    return out.strip().lower() == "true"


def is_atk_hide_task_installed(config: dict) -> bool:
    task_name = str(config.get("atk_hub_hide_task_name") or ATK_HIDE_TASK_NAME).replace("'", "''")
    out = run_powershell(f"if (Get-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue) {{ 'true' }}", timeout=5)
    return out.strip().lower() == "true"


def run_atk_hide_task(config: dict) -> bool:
    task_name = str(config.get("atk_hub_hide_task_name") or ATK_HIDE_TASK_NAME).replace("'", "''")
    out = run_powershell(
        f"$task = Get-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue; "
        f"if ($task) {{ Start-ScheduledTask -TaskName '{task_name}'; 'true' }}",
        timeout=6,
    )
    return out.strip().lower() == "true"


def run_atk_hub_task(config: dict) -> bool:
    task_name = str(config.get("atk_hub_task_name") or ATK_TASK_NAME).replace("'", "''")
    out = run_powershell(
        f"$task = Get-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue; "
        f"if ($task) {{ Start-ScheduledTask -TaskName '{task_name}'; 'true' }}",
        timeout=6,
    )
    started = out.strip().lower() == "true"
    if started:
        time.sleep(1.2)
        if config.get("hide_atk_hub_window", True):
            hide_atk_hub_windows(resolve_atk_hub_path(config))
            run_atk_hide_task(config)
    return started


def install_atk_hub_task(atk_hub_path: Path) -> None:
    installer = BASE_DIR / "install_atk_hub_task.ps1"
    if not installer.exists():
        messagebox.showwarning(APP_NAME, f"Missing installer script: {installer}")
        return
    try:
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                f"Start-Process powershell -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','{str(installer)}','-AtkHubPath','{str(atk_hub_path)}','-TaskName','{ATK_TASK_NAME}','-HideTaskName','{ATK_HIDE_TASK_NAME}')",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        pass


def open_path(path: Path, select: bool = False) -> None:
    try:
        if os.name == "nt":
            if select and path.exists():
                subprocess.Popen(["explorer", "/select,", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path if path.is_dir() else path.parent)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def configure_windows_app_identity() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def show_window_in_taskbar(root: Tk) -> None:
    if os.name != "nt":
        return
    try:
        root.update_idletasks()
        # Tk's winfo_id is the inner client window. Explorer uses its outer
        # top-level wrapper when deciding whether to show a taskbar button.
        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT]
        user32.GetAncestor.restype = ctypes.wintypes.HWND
        hwnd = user32.GetAncestor(root.winfo_id(), 2)  # GA_ROOT
        if not hwnd:
            return
        gwl_exstyle = -20
        ws_ex_toolwindow = 0x00000080
        ws_ex_appwindow = 0x00040000
        style = ctypes.windll.user32.GetWindowLongW(hwnd, gwl_exstyle)
        ctypes.windll.user32.SetWindowLongW(hwnd, gwl_exstyle, (style & ~ws_ex_toolwindow) | ws_ex_appwindow)
        root.withdraw()
        root.after(10, root.deiconify)
    except Exception:
        pass


def process_image_path(pid: int) -> str:
    if os.name != "nt" or not pid:
        return ""
    try:
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return ""
        try:
            size = ctypes.wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        return ""
    return ""


def hide_atk_hub_windows(atk_hub_path: Path | None = None) -> int:
    if os.name != "nt":
        return 0
    hidden = 0
    try:
        enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        expected_root = str(atk_hub_path.resolve()).lower() if atk_hub_path else ""

        def callback(hwnd, _lparam):
            nonlocal hidden
            try:
                if not ctypes.windll.user32.IsWindowVisible(hwnd):
                    return True
                pid = ctypes.wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                image_path = process_image_path(int(pid.value))
                image_lower = image_path.lower()
                if not image_lower.endswith("\\atk hub.exe"):
                    return True
                if expected_root and not image_lower.startswith(expected_root):
                    return True
                ctypes.windll.user32.ShowWindow(hwnd, 0)
                hidden += 1
            except Exception:
                pass
            return True

        ctypes.windll.user32.EnumWindows(enum_windows_proc(callback), 0)
    except Exception:
        return hidden
    return hidden


def visible_atk_hub_window_count(atk_hub_path: Path | None = None) -> int:
    if os.name != "nt":
        return 0
    count = 0
    try:
        enum_windows_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        expected_root = str(atk_hub_path.resolve()).lower() if atk_hub_path else ""

        def callback(hwnd, _lparam):
            nonlocal count
            try:
                if not ctypes.windll.user32.IsWindowVisible(hwnd):
                    return True
                pid = ctypes.wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                image_path = process_image_path(int(pid.value)).lower()
                if not image_path.endswith("\\atk hub.exe"):
                    return True
                if expected_root and not image_path.startswith(expected_root):
                    return True
                count += 1
            except Exception:
                pass
            return True

        ctypes.windll.user32.EnumWindows(enum_windows_proc(callback), 0)
    except Exception:
        return count
    return count


def get_work_area() -> tuple[int, int, int, int]:
    if os.name != "nt":
        return (0, 0, 1920, 1080)
    try:
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        pass
    return (0, 0, 1920, 1080)


def virtual_screen_bounds() -> tuple[int, int, int, int]:
    if os.name != "nt":
        return (0, 0, 1920, 1080)
    try:
        metrics = ctypes.windll.user32.GetSystemMetrics
        left, top = metrics(76), metrics(77)
        return (left, top, left + metrics(78), top + metrics(79))
    except Exception:
        return (0, 0, 1920, 1080)


def is_foreground_fullscreen() -> bool:
    if os.name != "nt":
        return False
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return False

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        return rect.left <= 0 and rect.top <= 0 and width >= screen_w - 4 and height >= screen_h - 4
    except Exception:
        return False


def foreground_window_class() -> str:
    if os.name != "nt":
        return ""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ""
        buffer = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, buffer, len(buffer))
        return buffer.value
    except Exception:
        return ""


def is_desktop_foreground() -> bool:
    return foreground_window_class() in {"Progman", "WorkerW", "Shell_TrayWnd"}


def startup_link_path() -> Path:
    startup = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return startup / STARTUP_LINK_NAME


def is_startup_enabled() -> bool:
    return startup_link_path().exists()


def set_startup_enabled(enabled: bool) -> bool:
    if os.name != "nt":
        return False
    link = startup_link_path()
    try:
        if enabled:
            link.parent.mkdir(parents=True, exist_ok=True)
            if getattr(sys, "frozen", False):
                target = Path(sys.executable).resolve()
            else:
                target = RUN_BAT_PATH if RUN_BAT_PATH.exists() else Path(__file__).resolve()
            icon = ICON_PATH if ICON_PATH.exists() else target
            script = rf"""
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut('{str(link).replace("'", "''")}')
$shortcut.TargetPath = '{str(target).replace("'", "''")}'
$shortcut.WorkingDirectory = '{str(BASE_DIR).replace("'", "''")}'
$shortcut.IconLocation = '{str(icon).replace("'", "''")}'
$shortcut.Save()
"""
            run_powershell(script, timeout=10)
        elif link.exists():
            link.unlink()
        return is_startup_enabled() == enabled
    except Exception:
        return False


def run_powershell(script: str, timeout: int = POWERSHELL_TIMEOUT) -> str:
    script = "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); $OutputEncoding = [Console]::OutputEncoding; " + script
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return ""
    if completed.returncode != 0 and not completed.stdout.strip():
        return ""
    return completed.stdout.strip()


def parse_percent(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        return number if 0 <= number <= 100 else None
    match = re.search(r"(?<!\d)(100|[1-9]?\d)\s*%?", str(value))
    if not match:
        return None
    number = int(match.group(1))
    return number if 0 <= number <= 100 else None


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name or "").strip()


def usb_vid_pid_present(vid: str, pid: str) -> bool:
    script = rf"""
$found = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
  Where-Object {{ $_.InstanceId -match '{re.escape(vid)}.*{re.escape(pid)}' }} |
  Select-Object -First 1
if ($found) {{ 'true' }} else {{ 'false' }}
"""
    return run_powershell(script, timeout=5).strip().lower() == "true"


def pnp_name_present(pattern: str) -> bool:
    safe_pattern = pattern.replace("'", "''")
    script = rf"""
$found = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
  Where-Object {{ $_.FriendlyName -match '{safe_pattern}' -or $_.InstanceId -match '{safe_pattern}' }} |
  Select-Object -First 1
if ($found) {{ 'true' }} else {{ 'false' }}
"""
    return run_powershell(script, timeout=5).strip().lower() == "true"


def usb_vendor_present(vid: str) -> bool:
    script = rf"""
$found = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
  Where-Object {{ $_.InstanceId -match '{re.escape(vid)}' }} |
  Select-Object -First 1
if ($found) {{ 'true' }} else {{ 'false' }}
"""
    return run_powershell(script, timeout=5).strip().lower() == "true"


def flydigi_direwolf_xinput_present() -> bool:
    script = r"""
$found = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
  Where-Object {
    $_.InstanceId -match 'FLYDIGI_DIREWOLF_4' -or
    $_.FriendlyName -match '飞智|Flydigi|冰原狼'
  } |
  Select-Object -First 1
if ($found) { 'true' } else { 'false' }
"""
    return run_powershell(script, timeout=5).strip().lower() == "true"


def device_is_present(device_name: str) -> bool:
    if STEELSERIES_DEVICE_NAME_PATTERN.search(device_name):
        return usb_vendor_present("VID_1038") or pnp_name_present("SteelSeries|Arctis|Aerox|Rival|Sensei")
    if RAZER_DEVICE_NAME_PATTERN.search(device_name):
        return usb_vendor_present("VID_1532") or pnp_name_present("Razer|BlackWidow|DeathAdder|Viper|Basilisk|Naga|Cobra|Huntsman|Ornata")
    if LOGITECH_DEVICE_NAME_PATTERN.search(device_name):
        return usb_vendor_present("VID_046D") or pnp_name_present("Logitech|Logi|LIGHTSPEED|PRO X|G HUB")

    alternate_requirements = USB_ALTERNATE_REQUIREMENTS.get(device_name)
    if alternate_requirements:
        return any(usb_vid_pid_present(*requirement) for requirement in alternate_requirements)

    requirement = USB_REQUIREMENTS.get(device_name)
    if not requirement:
        return True
    return usb_vid_pid_present(*requirement)


def notify_low_battery(device: DeviceBattery, threshold: int) -> None:
    if not NOTIFY_SCRIPT.exists() or device.level is None:
        return
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(NOTIFY_SCRIPT),
        "-DeviceName",
        device.name,
        "-Level",
        str(device.level),
        "-Threshold",
        str(threshold),
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass


def notification_device_key(device: DeviceBattery) -> str:
    name = normalize_name(device.name).lower()
    if re.search(r"flydigi|feizhi|genitech|direwolf|xbox 360", name, re.IGNORECASE):
        return "flydigi-controller"
    if re.search(r"xbox|xinput", name, re.IGNORECASE):
        return "xbox-controller"
    for known in KNOWN_USB_NAMES.values():
        known_key = known.lower()
        if name == known_key or name in known_key or known_key in name:
            return known_key
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-") or "device"


def known_name_from_instance(instance_id: str, fallback: str) -> str:
    upper = (instance_id or "").upper()
    for (vid, pid), name in KNOWN_USB_NAMES.items():
        if vid in upper and pid in upper:
            return name
    for vid, vendor_name in VENDOR_USB_NAMES.items():
        if vid in upper:
            fallback_name = normalize_name(fallback)
            if fallback_name and not re.fullmatch(r"(HID Keyboard Device|HID-compliant mouse|HID-compliant device|USB Input Device|USB 输入设备|符合 HID 标准的.*)", fallback_name, re.IGNORECASE):
                return fallback_name if re.search(r"Razer|Logitech|Logi", fallback_name, re.IGNORECASE) else f"{vendor_name}: {fallback_name}"
            return vendor_name
    if "FLYDIGI_DIREWOLF_4" in upper:
        return "Flydigi Direwolf 4"
    if "FEIZHI" in upper or "GENITECH_VIRTUAL_GAMEPAD" in upper:
        return "Flydigi Controller"
    return normalize_name(fallback)


def unique_devices(devices: list[DeviceBattery]) -> list[DeviceBattery]:
    seen: dict[str, DeviceBattery] = {}
    for device in devices:
        key = normalize_name(device.name).lower()
        if not key:
            continue
        for known in KNOWN_USB_NAMES.values():
            known_key = known.lower()
            if key != known_key and (key in known_key or known_key in key):
                key = known_key
                device.name = known
                break
        if re.search(r"flydigi|feizhi", key, re.IGNORECASE):
            key = "flydigi controller"
            if device.level is not None:
                device.name = "Flydigi Direwolf 4"
        if device.level is None and any(existing.level is not None and (key in seen_key or seen_key in key) for seen_key, existing in seen.items()):
            continue
        current = seen.get(key)
        if current is None or (current.level is None and device.level is not None):
            seen[key] = device
    # A fresh numeric reading from a vendor API (G HUB/Synapse/ATK) is already
    # stronger evidence of presence than the relatively slow and occasionally
    # timing-out PnP query.  Only use PnP to validate placeholder rows.
    return sorted(
        (d for d in seen.values() if d.level is not None or device_is_present(d.name)),
        key=lambda d: (d.level is None, d.name.lower()),
    )


class SimpleWebSocket:
    def __init__(self, host: str, port: int, protocol: str = "json", timeout: float = 4.0) -> None:
        self.host = host
        self.port = port
        self.protocol = protocol
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self._handshake()

    def _handshake(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET / HTTP/1.1\r\nHost: {self.host}:{self.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: {self.protocol}\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self.sock.recv(4096)
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest())
        if b" 101 " not in response or expected not in response:
            raise OSError("WebSocket handshake failed")

    def send_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.extend([0x80 | 126, (length >> 8) & 0xFF, length & 0xFF])
        else:
            header.append(0x80 | 127)
            header.extend(length.to_bytes(8, "big"))
        mask = os.urandom(4)
        self.sock.sendall(bytes(header) + mask + bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload)))

    def recv_text(self) -> str | None:
        first = self._recv_exact(2)
        if not first:
            return None
        opcode = first[0] & 0x0F
        length = first[1] & 0x7F
        masked = bool(first[1] & 0x80)
        if length == 126:
            length = int.from_bytes(self._recv_exact(2), "big")
        elif length == 127:
            length = int.from_bytes(self._recv_exact(8), "big")
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length)
        if masked:
            payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        if opcode == 8:
            return None
        return payload.decode("utf-8", errors="replace") if opcode == 1 else ""

    def _recv_exact(self, count: int) -> bytes:
        data = bytearray()
        while len(data) < count:
            chunk = self.sock.recv(count - len(data))
            if not chunk:
                raise OSError("Socket closed")
            data.extend(chunk)
        return bytes(data)

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


def get_lghub_batteries(config: dict) -> list[DeviceBattery]:
    if not config.get("enable_lghub", True):
        return []
    ws = None
    try:
        ws = SimpleWebSocket("127.0.0.1", 9010, "json", timeout=4.0)
        ws.send_text(json.dumps({"path": "/devices/list", "verb": "GET"}))
        names: dict[str, str] = {}
        active_ids: set[str] = set()
        batteries: dict[str, DeviceBattery] = {}
        # Some G HUB builds list headset sub-devices that never return a
        # battery state. Keep any valid response rather than discarding the
        # whole batch when one of those requests times out.
        deadline = time.time() + 4
        while time.time() < deadline:
            try:
                message = ws.recv_text()
            except (TimeoutError, socket.timeout):
                if batteries:
                    break
                continue
            if not message:
                continue
            try:
                data = json.loads(message)
            except Exception:
                continue
            path = str(data.get("path", ""))
            payload = data.get("payload") or {}
            if path == "/devices/list":
                for item in payload.get("deviceInfos", []) or []:
                    device_id = str(item.get("id") or "")
                    name = normalize_name(item.get("extendedDisplayName") or item.get("displayName") or item.get("name") or device_id)
                    state = str(item.get("state") or "").upper()
                    resources_available = item.get("resourcesAvailable") is not False
                    capabilities = item.get("capabilities") or {}
                    has_battery = capabilities.get("hasBatteryStatus") is not False
                    # Recent G HUB builds omit some of these fields.  Query any
                    # connected-looking device and let the battery endpoint decide.
                    disconnected = state in {"INACTIVE", "OFFLINE", "DISCONNECTED", "UNAVAILABLE"}
                    if device_id and not disconnected and resources_available and has_battery:
                        names[device_id] = name
                        active_ids.add(device_id)
                        ws.send_text(json.dumps({"path": f"/battery/{device_id}/state", "verb": "GET"}))
            elif path.startswith("/battery/") and path.endswith("/state"):
                device_id = path.replace("/battery/", "").replace("/state", "")
                if device_id not in active_ids:
                    continue
                level = parse_percent(payload.get("percentage"))
                if level is None:
                    level = parse_percent(payload.get("level"))
                if level is not None:
                    batteries[device_id] = DeviceBattery(names.get(device_id, device_id), level, "Logitech G HUB")
                # Do not wait for non-battery sub-devices once every likely
                # battery-capable entry has answered. A missing/unsupported
                # child entry must not erase an already valid headset level.
                if len(batteries) >= max(1, len(names)):
                    break
        return list(batteries.values())
    except Exception:
        return []
    finally:
        if ws:
            ws.close()


def get_razer_synapse_batteries(config: dict) -> list[DeviceBattery]:
    if not config.get("enable_razer_synapse_log", True):
        return []
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    program_data = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
    roots = [
        local / "Razer" / "RazerAppEngine" / "User Data" / "Logs",
        local / "Razer" / "Synapse3" / "Logs",
        local / "Razer" / "Synapse" / "Logs",
        program_data / "Razer" / "Synapse3" / "Log",
        program_data / "Razer" / "Synapse" / "Logs",
    ]
    max_age = max(30, int(config.get("max_cached_battery_age_seconds", 300)))
    now = time.time()
    records: list[tuple[float, DeviceBattery]] = []
    log_paths = {p for root in roots if root.exists() for p in root.rglob("*.log")}
    for log_path in sorted(log_paths, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:80]:
        try:
            if now - log_path.stat().st_mtime > max_age:
                continue
        except Exception:
            continue
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for match in re.finditer(r'"newValue":"((?:\\.|[^"\\])*)"', text):
            try:
                payload = json.loads(json.loads(f'"{match.group(1)}"'))
            except Exception:
                continue
            level = parse_percent((payload.get("powerStatus") or {}).get("level"))
            if level is None:
                continue
            name = payload.get("productName") or payload.get("name") or "Razer device"
            if isinstance(name, dict):
                name = name.get("en") or name.get("zh-cn") or next((v for v in name.values() if v), "")
            name = normalize_name(str(name))
            if RAZER_DEVICE_NAME_PATTERN.search(name):
                stamp = log_path.stat().st_mtime + match.start() / 1_000_000_000
                if now - stamp <= max_age:
                    records.append((stamp, DeviceBattery(name, level, "Razer Synapse")))
        # Synapse versions differ in how they serialize powerStatus. Accept
        # ordinary JSON/log fragments as a fallback, while still applying the
        # same freshness and Razer-name checks below.
        for match in re.finditer(
            r'(?is)(?:"(?:productName|deviceName|name)"\s*:\s*"(?P<name>[^"\\]{2,120})").{0,1200}?'
            r'"(?:battery(?:Level|Percentage)?|percentage|level)"\s*:\s*"?(?P<level>100|[1-9]?\d)\s*%?"?',
            text,
        ):
            name = normalize_name(match.group("name"))
            level = parse_percent(match.group("level"))
            if level is not None and RAZER_DEVICE_NAME_PATTERN.search(name):
                stamp = log_path.stat().st_mtime
                records.append((stamp, DeviceBattery(name, level, "Razer Synapse")))
        # Synapse 4 writes localized names as an object and powerStatus much
        # later in the same (very long) log line.  The older short-fragment
        # expression above cannot reach it.
        for match in re.finditer(
            r'(?i)"productName"\s*:\s*(?P<name>\{[^{}]*\}|"[^"\\]{2,160}")'
            r'[^\r\n]{0,20000}?"powerStatus"\s*:\s*\{[^{}]*?"level"\s*:\s*"?'
            r'(?P<level>100|[1-9]?\d)\s*%?"?',
            text,
        ):
            raw_name = match.group("name")
            try:
                parsed_name = json.loads(raw_name)
            except Exception:
                parsed_name = raw_name.strip('"')
            if isinstance(parsed_name, dict):
                parsed_name = (
                    parsed_name.get("en")
                    or parsed_name.get("zh-cn")
                    or next((value for value in parsed_name.values() if value), "")
                )
            name = normalize_name(str(parsed_name))
            level = parse_percent(match.group("level"))
            if level is not None and RAZER_DEVICE_NAME_PATTERN.search(name):
                records.append((log_path.stat().st_mtime, DeviceBattery(name, level, "Razer Synapse 4")))
    newest: dict[str, tuple[float, DeviceBattery]] = {}
    for stamp, device in records:
        key = device.name.lower()
        if key not in newest or stamp > newest[key][0]:
            newest[key] = (stamp, device)
    # A fresh Synapse record with powerStatus is direct evidence that the
    # device is online. PnP queries can time out and previously discarded
    # valid Razer readings here.
    return [item[1] for item in newest.values()]



# ---------------------------------------------------------------------------
# SteelSeries
# ---------------------------------------------------------------------------
class _HidGuid(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


class _SpDeviceInterfaceData(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("InterfaceClassGuid", _HidGuid), ("Flags", wt.DWORD), ("Reserved", ctypes.c_void_p)]


class _HidAttributes(ctypes.Structure):
    _fields_ = [("Size", wt.DWORD), ("VendorID", wt.WORD), ("ProductID", wt.WORD), ("VersionNumber", wt.WORD)]


class _HidpCaps(ctypes.Structure):
    _fields_ = [
        ("Usage", wt.USHORT), ("UsagePage", wt.USHORT),
        ("InputReportByteLength", wt.USHORT), ("OutputReportByteLength", wt.USHORT),
        ("FeatureReportByteLength", wt.USHORT), ("Reserved", wt.USHORT * 17),
        ("NumberLinkCollectionNodes", wt.USHORT),
        ("NumberInputButtonCaps", wt.USHORT), ("NumberInputValueCaps", wt.USHORT),
        ("NumberInputDataIndices", wt.USHORT),
        ("NumberOutputButtonCaps", wt.USHORT), ("NumberOutputValueCaps", wt.USHORT),
        ("NumberOutputDataIndices", wt.USHORT),
        ("NumberFeatureButtonCaps", wt.USHORT), ("NumberFeatureValueCaps", wt.USHORT),
        ("NumberFeatureDataIndices", wt.USHORT),
    ]


_HID_GUID = _HidGuid(0x4D1E55B2, 0xF16F, 0x11CF, (ctypes.c_ubyte * 8)(0x88, 0xCB, 0x00, 0x11, 0x11, 0x00, 0x00, 0x30))
_HID_DLL = None
_CFGMGR_DLL = None
_KERNEL32 = None


def _hid_dlls():
    global _HID_DLL, _CFGMGR_DLL, _KERNEL32
    if os.name != "nt":
        return None
    if _HID_DLL is None:
        try:
            _HID_DLL = ctypes.WinDLL("hid", use_last_error=True)
            _CFGMGR_DLL = ctypes.WinDLL("cfgmgr32", use_last_error=True)
            _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
        except Exception:
            _HID_DLL = None
    return _HID_DLL


def _hid_paths_for_vid(vid: int) -> list[str]:
    if not _hid_dlls():
        return []
    size = wt.DWORD(0)
    if _CFGMGR_DLL.CM_Get_Device_Interface_List_SizeW(ctypes.byref(size), ctypes.byref(_HID_GUID), None, 0) != 0:
        return []
    if size.value <= 1:
        return []
    buffer = ctypes.create_unicode_buffer(size.value)
    if _CFGMGR_DLL.CM_Get_Device_Interface_ListW(ctypes.byref(_HID_GUID), None, buffer, size.value, 0) != 0:
        return []
    raw = ctypes.wstring_at(ctypes.addressof(buffer), size.value)
    pattern = re.compile(rf"vid[_&]0*{vid:04x}", re.IGNORECASE)
    paths = []
    for path in raw.split("\0"):
        if path and pattern.search(path):
            paths.append(path)
    return paths[:32]


def _hid_open(path: str):
    handle = _KERNEL32.CreateFileW(path, 0x80000000 | 0x40000000, 3, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        return None
    return handle


def _hid_product_name(handle) -> str:
    try:
        buffer = ctypes.create_unicode_buffer(256)
        if _HID_DLL.HidD_GetProductString(handle, buffer, len(buffer)):
            return normalize_name(buffer.value)
    except Exception:
        pass
    return ""


def _hid_battery_for_path(path: str):
    handle = _hid_open(path)
    if not handle:
        return None
    try:
        attrs = _HidAttributes()
        attrs.Size = ctypes.sizeof(attrs)
        if not _HID_DLL.HidD_GetAttributes(handle, ctypes.byref(attrs)):
            return None
        if attrs.VendorID != 0x1038:
            return None
        product = _hid_product_name(handle)
        model = STEELSERIES_HID_MODELS.get(int(attrs.ProductID))
        if model is None:
            # Only probe products that identify themselves as Arctis; a wrong
            # HID write to an unrelated SteelSeries mouse is not worth the risk.
            if not re.search(r"arctis|headset", product, re.IGNORECASE):
                return None
            model = (product or "SteelSeries Arctis", 31, 31, b"\x06\x18", 2)
        name, in_len, out_len, command, index = model
        preparsed = ctypes.c_void_p()
        if not _HID_DLL.HidD_GetPreparsedData(handle, ctypes.byref(preparsed)):
            return None
        try:
            caps = _HidpCaps()
            if _HID_DLL.HidP_GetCaps(preparsed, ctypes.byref(caps)) != 0:
                return None
            if caps.InputReportByteLength != in_len or caps.OutputReportByteLength != out_len:
                return None
            out = bytearray(out_len)
            out[:len(command)] = command
            written = wt.DWORD(0)
            if not _KERNEL32.WriteFile(handle, bytes(out), out_len, ctypes.byref(written), None):
                return None
            time.sleep(0.02)
            incoming = ctypes.create_string_buffer(in_len)
            read = wt.DWORD(0)
            if not _KERNEL32.ReadFile(handle, incoming, in_len, ctypes.byref(read), None):
                return None
            level = int(incoming.raw[index])
            if 0 <= level <= 100:
                return DeviceBattery(product or name, level, "SteelSeries HID")
        finally:
            _HID_DLL.HidD_FreePreparsedData(preparsed)
    except Exception:
        return None
    finally:
        _KERNEL32.CloseHandle(handle)
    return None


def get_steelseries_hid_batteries(config: dict) -> list[DeviceBattery]:
    if not config.get("enable_steelseries_hid", True):
        return []
    if not usb_vendor_present("VID_1038"):
        return []
    devices: list[DeviceBattery] = []
    for path in _hid_paths_for_vid(0x1038):
        result: list[DeviceBattery] = []
        def worker(p=path):
            item = _hid_battery_for_path(p)
            if item:
                result.append(item)
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=2.0)
        if result:
            devices.append(result[0])
    return devices


def get_steelseries_gg_batteries(config: dict) -> list[DeviceBattery]:
    if not config.get("enable_steelseries_gg_log", True):
        return []
    roots = [
        Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "SteelSeries" / "GG",
        Path(os.environ.get("LOCALAPPDATA", "")) / "SteelSeries" / "GG",
    ]
    max_age = max(60, int(config.get("max_cached_battery_age_seconds", 300)))
    now = time.time()
    records: list[tuple[float, DeviceBattery]] = []
    candidates = []
    for root in roots:
        if not root.exists():
            continue
        for pattern in ("*.log", "*.json", "*.txt"):
            try:
                candidates.extend(root.rglob(pattern))
            except OSError:
                continue
    for path in sorted(set(candidates), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:80]:
        try:
            if now - path.stat().st_mtime > max_age:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for pattern in (
            r'(?is)"(?:productName|deviceName|name)"\s*:\s*"([^"\\]{2,120})".{0,4000}?"(?:battery(?:Level|Percentage)?|percentage|level)"\s*:\s*"?(\d{1,3})',
            r'(?is)"(?:battery(?:Level|Percentage)?|percentage|level)"\s*:\s*"?(\d{1,3})".{0,4000}?"(?:productName|deviceName|name)"\s*:\s*"([^"\\]{2,120})"',
        ):
            for match in re.finditer(pattern, text):
                first, second = match.group(1), match.group(2)
                if first.isdigit():
                    level, name = parse_percent(first), normalize_name(second)
                else:
                    name, level = normalize_name(first), parse_percent(second)
                if level is not None and name and STEELSERIES_DEVICE_NAME_PATTERN.search(name):
                    records.append((path.stat().st_mtime, DeviceBattery(name, level, "SteelSeries GG")))
    newest: dict[str, tuple[float, DeviceBattery]] = {}
    for stamp, device in records:
        key = device.name.lower()
        if key not in newest or stamp > newest[key][0]:
            newest[key] = (stamp, device)
    return [item[1] for item in newest.values()]


def get_atk_hub_batteries(config: dict) -> list[DeviceBattery]:
    if not config.get("enable_atk_hub_probe", True):
        return []
    if not device_is_present("ATK V75X"):
        return []

    node_path = resolve_node_path(config)
    atk_hub_path = resolve_atk_hub_path(config)
    if node_path is None or atk_hub_path is None:
        return []
    if not ATK_HELPER_SCRIPT.exists() or not atk_hub_path.exists():
        return []
    if str(node_path) != "node" and not Path(str(node_path)).exists():
        return []

    if config.get("use_atk_hub_scheduled_task", True) and not is_port_open(9224) and is_atk_hub_task_installed(config):
        if run_atk_hub_task(config):
            time.sleep(5)

    fallback_node_modules = BASE_DIR.parent / "work" / "atk_node_modules"
    env = os.environ.copy()
    if fallback_node_modules.exists():
        existing_node_path = env.get("NODE_PATH", "")
        env["NODE_PATH"] = str(fallback_node_modules) + (os.pathsep + existing_node_path if existing_node_path else "")

    def run_helper() -> dict | None:
        try:
            completed = subprocess.run(
                [
                    str(node_path),
                    str(ATK_HELPER_SCRIPT),
                    str(atk_hub_path),
                    str(fallback_node_modules),
                    "9224",
                    "",
                    "start" if config.get("auto_start_atk_hub_reader", False) else "nostart",
                ],
                capture_output=True,
                text=True,
                timeout=12,
                creationflags=subprocess.CREATE_NO_WINDOW,
                env=env,
            )
        except Exception:
            return None
        if completed.returncode != 0 or not completed.stdout.strip():
            return None
        try:
            return json.loads(completed.stdout.strip())
        except Exception:
            return None

    result = run_helper()
    if result and result.get("ok") and str(result.get("status") or "") == "sleeping" and config.get("auto_restart_atk_hub_reader", False):
        if restart_atk_hub_with_debug(atk_hub_path):
            result = run_helper()

    if not result:
        return []
    if not result.get("ok"):
        return []
    level = parse_percent(result.get("level"))
    source = str(result.get("source") or "ATK HUB")
    status = str(result.get("status") or "")
    if level is None and status == "sleeping":
        cached_level = parse_percent(config.get("atk_last_battery_level"))
        cached_at = float(config.get("atk_last_battery_time") or 0)
        max_age = max(60, int(config.get("atk_cached_battery_age_seconds", 1800)))
        if cached_level is not None and time.time() - cached_at <= max_age:
            return [DeviceBattery("ATK V75X", cached_level, f"{source} (cached; sleeping)", status)]
        return [DeviceBattery("ATK V75X", None, f"{source} (sleeping)", status)]
    if level is None:
        return []
    config["atk_last_battery_level"] = level
    config["atk_last_battery_time"] = time.time()
    save_config(config)
    return [DeviceBattery("ATK V75X", level, source, status)]


def get_pnp_candidates(config: dict) -> list[DeviceBattery]:
    filters = [str(x) for x in config.get("name_filters", []) if str(x).strip()]
    filter_regex = "|".join(re.escape(x) for x in filters) or "Bluetooth|HID|Mouse|Keyboard|Headset"
    script = rf"""
$rx = '{filter_regex}'
$devices = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
  Where-Object {{
    $_.Class -match 'Bluetooth|HIDClass|Mouse|Keyboard' -or
    $_.FriendlyName -match $rx
  }} |
  Select-Object -First 80 Class,FriendlyName,InstanceId
$devices | ConvertTo-Json -Compress
"""
    out = run_powershell(script)
    if not out:
        return []
    try:
        data = json.loads(out)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]
    devices: list[DeviceBattery] = []
    flydigi_xinput_present = flydigi_direwolf_xinput_present()
    flydigi_addresses = {
        str(address).upper().replace(":", "")
        for address in config.get("flydigi_bluetooth_addresses", [])
        if str(address).strip()
    }
    for item in data or []:
        device_class = str(item.get("Class", ""))
        friendly = normalize_name(item.get("FriendlyName") or "")
        instance_id = str(item.get("InstanceId") or "")
        name = known_name_from_instance(item.get("InstanceId") or "", friendly)
        if not name:
            continue
        if name == "Flydigi Controller" and not config.get("force_flydigi_name", False):
            continue
        if name == "Flydigi Direwolf 4" and item.get("Class") == "XnaComposite":
            continue
        address_match = re.search(r"DEV_([0-9A-F]{12})", instance_id.upper())
        address = address_match.group(1) if address_match else ""
        if name == "Xbox Wireless Controller" and flydigi_xinput_present and address in flydigi_addresses:
            continue
        if re.search(r"virtual|effect|bus enumerator|blue vo!ce|surround", name, re.IGNORECASE):
            continue
        if name == friendly and re.fullmatch(r"(HID Keyboard Device|HID-compliant mouse|USB 输入设备|符合 HID 标准的.*)", name, re.IGNORECASE):
            continue
        if not re.search(filter_regex, name, re.IGNORECASE):
            continue
        devices.append(DeviceBattery(name, None, f"Windows {device_class or 'PnP'}"))
    return devices


def get_bluetooth_battery_devices() -> list[tuple[str, str]]:
    script = r"""
$devices = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
  Where-Object {
    $_.InstanceId -match 'BTHLE\\DEV_[0-9A-F]{12}' -or
    $_.InstanceId -match 'BTHLEDEVICE\\\{0000180F-0000-1000-8000-00805F9B34FB\}_DEV_[^\\]+'
  } |
  Select-Object FriendlyName,InstanceId
$devices | ConvertTo-Json -Compress
"""
    out = run_powershell(script, timeout=5)
    if not out:
        return []
    try:
        data = json.loads(out)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]
    devices: list[tuple[str, str]] = []
    for item in data or []:
        text = f"{item.get('FriendlyName', '')} {item.get('InstanceId', '')}".upper()
        if not re.search(r"XBOX|FEIZHI|FLYDIGI|GENITECH|STEELSERIES|ARCTIS|AEROX|RIVAL|SENSEI|0000180F", text):
            continue
        match = re.search(r"DEV_([0-9A-F]{12})", text)
        if not match:
            continue
        friendly = normalize_name(item.get("FriendlyName") or "")
        name = "Xbox Wireless Controller" if re.search(r"xbox|xinput", friendly, re.IGNORECASE) else friendly
        if not name or re.search(r"0000180F|battery|电池|service|服务", name, re.IGNORECASE):
            name = "SteelSeries Device" if re.search(r"STEELSERIES|ARCTIS|AEROX|RIVAL|SENSEI", text) else "Xbox Wireless Controller"
        address = match.group(1)
        if address not in [existing[0] for existing in devices]:
            devices.append((address, name))
    return devices


def get_windows_settings_bluetooth_batteries(config: dict) -> list[DeviceBattery]:
    script = r"""
$items = @()
Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
  Where-Object { $_.Class -eq 'Bluetooth' -and $_.FriendlyName -match 'Xbox|Controller|Gamepad|手柄|SteelSeries|Arctis|Aerox|Rival|Sensei' } |
  ForEach-Object {
    $props = Get-PnpDeviceProperty -InstanceId $_.InstanceId -ErrorAction SilentlyContinue
    $battery = $props | Where-Object { $_.KeyName -eq '{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2' } | Select-Object -First 1
    $address = $props | Where-Object { $_.KeyName -eq 'DEVPKEY_Bluetooth_DeviceAddress' } | Select-Object -First 1
    if ($battery -and $battery.Data -ne $null) {
      $items += [PSCustomObject]@{
        name = $_.FriendlyName
        level = [int]$battery.Data
        address = if ($address) { [string]$address.Data } else { "" }
      }
    }
  }
$items | ConvertTo-Json -Compress
"""
    out = run_powershell(script, timeout=8)
    if not out:
        return []
    try:
        data = json.loads(out)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]

    flydigi_addresses = {
        str(address).upper().replace(":", "")
        for address in config.get("flydigi_bluetooth_addresses", [])
        if str(address).strip()
    }
    prefer_windows_name = bool(config.get("prefer_windows_bluetooth_name", True))
    devices: list[DeviceBattery] = []
    for item in data or []:
        name = normalize_name(str(item.get("name") or "Xbox Wireless Controller"))
        address = str(item.get("address") or "").upper().replace(":", "")
        if address in flydigi_addresses and not prefer_windows_name:
            name = "Flydigi Direwolf 4"
        level = parse_percent(item.get("level"))
        if level is not None:
            devices.append(DeviceBattery(name, level, "Windows Settings Bluetooth"))
    return devices


async def read_winrt_battery(address_hex: str) -> int | None:
    try:
        from winrt.windows.devices.bluetooth import BluetoothLEDevice
    except Exception:
        return None
    try:
        device = await BluetoothLEDevice.from_bluetooth_address_async(int(address_hex, 16))
        if device is None:
            return None
        services = await device.get_gatt_services_for_uuid_async(uuid.UUID("0000180F-0000-1000-8000-00805F9B34FB"))
        if int(services.status) != 0:
            return None
        for service in services.services:
            chars = await service.get_characteristics_for_uuid_async(uuid.UUID("00002A19-0000-1000-8000-00805F9B34FB"))
            if int(chars.status) != 0:
                continue
            for characteristic in chars.characteristics:
                result = await characteristic.read_value_async()
                if int(result.status) == 0 and result.value.length >= 1:
                    raw = bytes(result.value)
                    if raw:
                        return parse_percent(raw[0])
    except Exception:
        return None
    return None


async def get_winrt_bluetooth_batteries(config: dict) -> list[DeviceBattery]:
    bluetooth_devices = get_bluetooth_battery_devices()
    if not bluetooth_devices:
        return []
    force_flydigi_name = bool(config.get("force_flydigi_name", False))
    flydigi_xinput_present = flydigi_direwolf_xinput_present()
    flydigi_addresses = {
        str(address).upper().replace(":", "")
        for address in config.get("flydigi_bluetooth_addresses", [])
        if str(address).strip()
    }
    if flydigi_xinput_present and len(bluetooth_devices) == 1:
        only_address = bluetooth_devices[0][0].upper().replace(":", "")
        if only_address not in flydigi_addresses:
            flydigi_addresses.add(only_address)
            config["flydigi_bluetooth_addresses"] = sorted(flydigi_addresses)
            save_config(config)
    devices: list[DeviceBattery] = []
    for index, (address, detected_name) in enumerate(bluetooth_devices[:6]):
        normalized_address = address.upper().replace(":", "")
        name = detected_name or "Xbox Wireless Controller"
        if (
            normalized_address in flydigi_addresses
            or (force_flydigi_name and index == 0 and re.search(r"xbox|controller", name, re.IGNORECASE))
        ):
            name = "Flydigi Direwolf 4"
        try:
            level = await asyncio.wait_for(read_winrt_battery(address), timeout=8)
        except Exception:
            level = None
        if level is not None:
            devices.append(DeviceBattery(name, level, "Windows BLE Battery Service"))
    return devices


def get_xinput_batteries(existing_gamepads: int = 0) -> list[DeviceBattery]:
    if os.name != "nt":
        return []
    dll = None
    for name in ("xinput1_4.dll", "xinput9_1_0.dll", "xinput1_3.dll"):
        try:
            dll = ctypes.WinDLL(name)
            break
        except Exception:
            continue
    if dll is None:
        return []

    class XINPUT_BATTERY_INFORMATION(ctypes.Structure):
        _fields_ = [("BatteryType", ctypes.c_ubyte), ("BatteryLevel", ctypes.c_ubyte)]

    level_map = {
        0: 5,
        1: 25,
        2: 55,
        3: 100,
    }
    connected: list[DeviceBattery] = []
    for index in range(4):
        info = XINPUT_BATTERY_INFORMATION()
        try:
            result = dll.XInputGetBatteryInformation(index, 0, ctypes.byref(info))
        except Exception:
            continue
        if result != 0 or info.BatteryType == 0:
            continue
        if info.BatteryType == 1:
            level = None
            source = "XInput wired"
        else:
            level = level_map.get(int(info.BatteryLevel))
            source = "XInput Battery"
        connected.append(DeviceBattery(f"Xbox Controller (XInput {index + 1})", level, source))

    if existing_gamepads > 0 and len(connected) > existing_gamepads:
        return connected[existing_gamepads:]
    if existing_gamepads > 0:
        return []
    return connected


def collect_devices(config: dict) -> list[DeviceBattery]:
    devices: list[DeviceBattery] = []
    errors: list[str] = []
    counts: list[str] = []

    def safe(label: str, function):
        try:
            result = function()
            counts.append(f"{label}: {len(result)}")
            return result
        except Exception:
            errors.append(f"[{label}]\n{traceback.format_exc()}")
            counts.append(f"{label}: error")
            return []

    devices.extend(safe("logitech-g-hub", lambda: get_lghub_batteries(config)))
    devices.extend(safe("razer-synapse", lambda: get_razer_synapse_batteries(config)))
    devices.extend(safe("steelseries-hid", lambda: get_steelseries_hid_batteries(config)))
    devices.extend(safe("steelseries-gg", lambda: get_steelseries_gg_batteries(config)))
    devices.extend(safe("atk-hub", lambda: get_atk_hub_batteries(config)))
    devices.extend(safe("windows-pnp", lambda: get_pnp_candidates(config)))
    settings_bluetooth = safe("windows-bluetooth", lambda: get_windows_settings_bluetooth_batteries(config))
    devices.extend(settings_bluetooth)
    ble_gamepads: list[DeviceBattery] = []
    if not settings_bluetooth:
        try:
            ble_gamepads = asyncio.run(get_winrt_bluetooth_batteries(config))
            counts.append(f"winrt-ble: {len(ble_gamepads)}")
            devices.extend(ble_gamepads)
        except Exception:
            counts.append("winrt-ble: error")
    existing_xbox_gamepads = sum(1 for device in [*settings_bluetooth, *ble_gamepads] if re.search(r"xbox", device.name, re.IGNORECASE))
    devices.extend(safe("xinput", lambda: get_xinput_batteries(existing_gamepads=existing_xbox_gamepads)))
    devices = unique_devices(devices)
    if config.get("hide_unknown"):
        devices = [d for d in devices if d.level is not None]
    if errors:
        write_error_log(f"{datetime.now():%Y-%m-%d %H:%M:%S}\n" + "\n".join(errors))
    elif os.environ.get("WBW_DEBUG"):
        write_error_log(f"{datetime.now():%Y-%m-%d %H:%M:%S}\n" + "\n".join(counts) + f"\ntotal: {len(devices)}")
    return devices


def read_codex_usage() -> dict:
    """Read the signed-in account through the official local app-server RPC."""
    executable = shutil.which("codex.exe")
    if not executable:
        candidates = list((Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"))
        if candidates:
            executable = str(max(candidates, key=lambda p: p.stat().st_mtime))
    if not executable:
        raise RuntimeError("Codex is not installed")
    process = subprocess.Popen(
        [executable, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    messages = queue.Queue()
    def receive():
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                pass
        messages.put(None)
    reader = threading.Thread(target=receive, daemon=True)
    reader.start()
    def send(data):
        process.stdin.write(json.dumps(data) + "\n")
        process.stdin.flush()
    deadline = time.monotonic() + 20
    def response(request_id):
        while time.monotonic() < deadline:
            item = messages.get(timeout=max(0.01, deadline - time.monotonic()))
            if item is None:
                raise RuntimeError("Codex disconnected")
            if item.get("id") == request_id:
                if "error" in item:
                    raise RuntimeError("Codex usage request failed")
                return item["result"]
        raise TimeoutError("Codex usage timed out")
    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "wireless_battery_widget", "version": "1.0"}}})
        response(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "account/rateLimits/read"})
        result = response(2)
        buckets = result.get("rateLimitsByLimitId")
        limits = buckets.get("codex", {}) if isinstance(buckets, dict) else result.get("rateLimits", {})
        for key in ("primary", "secondary"):
            window = limits.get(key) or {}
            used = window.get("usedPercent")
            if window.get("windowDurationMins") == 300 and isinstance(used, (int, float)) and not isinstance(used, bool):
                return {"remaining": max(0, min(100, 100 - used)), "fetched_at": time.time(), "resets_at": window.get("resetsAt")}
        raise RuntimeError("Five-hour window unavailable")
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        reader.join(timeout=1)
        process.stdin.close()
        process.stdout.close()


class ReadableCanvas(Canvas):
    """Bold foreground text with a one-pixel outline over photos."""
    def create_text(self, *args, **kwargs):
        x, y = args
        outline = kwargs.pop("outline", True)
        bold = kwargs.pop("bold", True)
        font = kwargs.get("font", ("Segoe UI", 8))
        kwargs["font"] = (font[0], font[1], "bold") if bold else (font[0], font[1])
        if outline:
            outline_kwargs = {**kwargs, "fill": "#000000"}
            for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)):
                super().create_text(x + dx, y + dy, **outline_kwargs)
        return super().create_text(x, y, **kwargs)


class BatteryWidget:
    def __init__(self) -> None:
        self.config = load_config()
        self.codex_usage = None
        self.codex_usage_status = "Checking account usage..."
        self.deepseek_balance = None
        self.deepseek_status = "Checking balance…"
        self.background_status = "missing"
        self.background_search_done = False
        self.show_unknown = bool(self.config.get("show_devices_without_reading", False))
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        configure_windows_app_identity()
        self.root = Tk()
        self.root.title(APP_NAME)
        self.taskbar_alt_tab_mode = bool(self.config.get("taskbar_alt_tab_mode", True))
        # Use a frameless widget window. show_window_in_taskbar() applies the
        # app-window style separately so removing the title bar need not hide
        # the widget from the taskbar/Alt+Tab list.
        self.root.overrideredirect(True)
        if self.taskbar_alt_tab_mode:
            self.root.resizable(False, False)
        self.root.attributes("-topmost", bool(self.config.get("always_on_top", False)))
        self.root.attributes("-alpha", float(self.config.get("opacity", 0.92)))
        try:
            if ICON_PATH.exists():
                self.root.iconbitmap(str(ICON_PATH))
        except Exception:
            pass
        self.root.configure(bg="#0B111A")

        pos = self.config.get("position", {})
        self.root.geometry(f"+{int(pos.get('x', 40))}+{int(pos.get('y', 60))}")

        self.canvas = ReadableCanvas(self.root, bg="#0B111A", highlightthickness=0, bd=0)
        self.canvas.pack(fill=BOTH, expand=True)
        self.backdrop_photo = None
        self.last_updated_text = "Checking connected devices…"
        self.current_devices: list[DeviceBattery] = []

        self.menu = Menu(self.root, tearoff=False)
        self.menu.add_command(label="Refresh now", command=self.refresh)
        self.show_unknown_var = BooleanVar(value=self.show_unknown)
        self.menu.add_checkbutton(label="Show devices without readings", variable=self.show_unknown_var, command=self.toggle_show_unknown)
        self.menu.add_separator()
        self.menu.add_command(label="Choose background image…", command=self.choose_background)
        self.bg_menu_index = 3
        self.menu.add_command(label="Select background area…", command=self.select_background_area)
        self.menu.add_command(label="Adjust background blur…", command=self.adjust_background_blur)
        self.menu.add_command(label="Reset background", command=self.reset_background)
        self.menu.add_separator()
        self.menu.add_command(label="Set low battery threshold...", command=self.set_threshold)
        self.menu.add_command(label="Toggle low battery notifications", command=self.toggle_notifications)
        self.menu.add_command(label="Toggle stay on top", command=self.toggle_stay_on_top)
        self.menu.add_command(label="Toggle startup", command=self.toggle_startup)
        self.menu.add_command(label="Toggle hide ATK HUB", command=self.toggle_hide_atk_hub)
        self.menu.add_command(label="Install ATK task...", command=self.install_atk_task)
        self.menu.add_separator()
        self.menu.add_command(label="Open source file", command=self.open_source_file)
        self.menu.add_command(label="Open app folder", command=self.open_app_folder)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.root.destroy)

        self.drag_start = (0, 0)
        self.user_moved = False
        self.refreshing = False
        self.refresh_timer = None
        self.last_notifications: dict[str, float] = {
            str(k): float(v)
            for k, v in (self.config.get("last_low_battery_notifications") or {}).items()
            if isinstance(v, (int, float))
        }
        self.low_battery_active_keys = set(str(key) for key in self.config.get("low_battery_active_keys", []))
        self.menu_open_until = 0.0
        self.last_atk_hide_task_run = 0.0

        self.root.bind("<ButtonPress-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.drag)
        self.root.bind("<ButtonRelease-1>", self.end_drag)
        self.root.bind("<Button-3>", self.show_menu)
        self.root.bind("<FocusOut>", lambda _event: self.force_topmost())
        self.canvas.bind("<Configure>", self.schedule_redraw)

        self.root.after(50, lambda: show_window_in_taskbar(self.root))
        self.root.after(100, self.refresh)
        self.root.after(150, self.refresh_codex_usage)
        self.root.after(200, self.refresh_deepseek_balance)
        self.root.after(250, self.drain_events)
        self.root.after(500, self.force_topmost)
        self.root.after(1000, self.restore_after_show_desktop)
        self.root.after(1200, self.hide_atk_hub_window_loop)

    def apply_window_corners(self) -> None:
        if os.name != "nt":
            return
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        user32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT]
        user32.GetAncestor.restype = ctypes.wintypes.HWND
        user32.GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.RECT)]
        user32.SetWindowRgn.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.HANDLE, ctypes.wintypes.BOOL]
        gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
        gdi32.CreateRoundRectRgn.restype = ctypes.wintypes.HANDLE
        gdi32.DeleteObject.argtypes = [ctypes.wintypes.HANDLE]
        hwnd = user32.GetAncestor(self.root.winfo_id(), 2)
        rect = ctypes.wintypes.RECT()
        if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return
        width, height = rect.right - rect.left, rect.bottom - rect.top
        key = (hwnd, width, height)
        if width < 32 or height < 32 or getattr(self, "rounded_window_size", None) == key:
            return
        region = gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, 32, 32)
        if region:
            # Windows owns the region after a successful SetWindowRgn.
            if user32.SetWindowRgn(hwnd, region, True):
                self.rounded_window_size = key
            else:
                gdi32.DeleteObject(region)

    def schedule_redraw(self, _event=None) -> None:
        if getattr(self, "redraw_timer", None):
            try:
                self.root.after_cancel(self.redraw_timer)
            except Exception:
                pass
        self.redraw_timer = self.root.after(80, self.draw_ui)

    def choose_background(self) -> None:
        if Image is None:
            messagebox.showerror(APP_NAME, "Image backgrounds require Pillow. Install it with: python -m pip install Pillow", parent=self.root)
            return
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Choose a widget background",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff"), ("All files", "*.*")],
        )
        if not selected:
            return
        try:
            with Image.open(selected) as source:
                source.verify()
            selected_path = Path(selected)
            previous = str(self.config.get("background_image") or "")
            self.config["background_image"] = str(selected_path)
            cached = cache_background_image(selected_path)
            if cached:
                self.config["background_cache"] = str(cached.relative_to(BASE_DIR)).replace("\\", "/")
            if previous != str(selected_path):
                self.config["background_crop"] = [0.0, 0.0, 1.0, 1.0]
            self.background_search_done = False
            self.background_status = "ok"
            save_config(self.config)
            self.draw_ui()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open that image:\n{exc}", parent=self.root)

    def adjust_background_blur(self) -> None:
        if Image is None:
            messagebox.showerror(APP_NAME, "Image backgrounds require Pillow. Install it with: python -m pip install Pillow", parent=self.root)
            return
        dialog = Toplevel(self.root)
        dialog.title("Background blur")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.configure(bg="#111A27")
        dialog.geometry("320x150")
        Label(dialog, text="Background blur", bg="#111A27", fg="#F1F5F9", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=18, pady=(16, 0))
        amount = Scale(dialog, from_=0, to=24, orient="horizontal", length=280, showvalue=True, bg="#111A27", fg="#CBD5E1", troughcolor="#263548", highlightthickness=0)
        amount.set(max(0, min(24, int(self.config.get("background_blur", 8)))))
        amount.pack(padx=18, pady=(4, 6))
        actions = Frame(dialog, bg="#111A27")
        actions.pack(fill="x", padx=18)
        def apply() -> None:
            self.config["background_blur"] = int(amount.get())
            save_config(self.config)
            dialog.destroy()
            self.draw_ui()
        Button(actions, text="Cancel", command=dialog.destroy, bg="#263548", fg="#E2E8F0", relief="flat", padx=12).pack(side=RIGHT)
        Button(actions, text="Apply", command=apply, bg="#5B8DEF", fg="#FFFFFF", relief="flat", padx=12).pack(side=RIGHT, padx=(0, 8))

    def select_background_area(self) -> None:
        image_path, _status = resolve_background_path(self.config)
        if Image is None or image_path is None:
            messagebox.showinfo(APP_NAME, "Choose a background image first.", parent=self.root)
            return
        try:
            with Image.open(image_path) as source:
                preview = source.convert("RGB")
            preview.thumbnail((560, 420), Image.Resampling.LANCZOS)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open that image:\n{exc}", parent=self.root)
            return

        dialog = Toplevel(self.root)
        dialog.title("Select background area")
        dialog.transient(self.root)
        dialog.configure(bg="#111A27")
        dialog.resizable(False, False)
        Label(dialog, text="Drag to select the part of the image to show", bg="#111A27", fg="#F1F5F9", font=("Segoe UI", 10, "bold")).pack(padx=12, pady=(12, 8))
        photo = ImageTk.PhotoImage(preview)
        canvas = Canvas(dialog, width=preview.width, height=preview.height, bg="#0B111A", highlightthickness=0, cursor="crosshair")
        canvas.pack(padx=12)
        canvas.create_image(0, 0, image=photo, anchor="nw")
        canvas.image = photo
        crop = self.config.get("background_crop", [0.0, 0.0, 1.0, 1.0])
        try:
            initial = (float(crop[0]), float(crop[1]), float(crop[2]), float(crop[3]))
            x0, y0, x1, y1 = (int(initial[0] * preview.width), int(initial[1] * preview.height), int(initial[2] * preview.width), int(initial[3] * preview.height))
        except Exception:
            x0, y0, x1, y1 = (0, 0, preview.width, preview.height)
        rect = canvas.create_rectangle(x0, y0, x1, y1, outline="#73E0B1", width=2, dash=(5, 3))
        selection = {"start": None, "coords": (x0, y0, x1, y1)}
        def start(event) -> None:
            selection["start"] = (max(0, min(preview.width - 1, event.x)), max(0, min(preview.height - 1, event.y)))
            canvas.coords(rect, *selection["start"], *selection["start"])
        def drag(event) -> None:
            if selection["start"] is None:
                return
            x = max(0, min(preview.width, event.x))
            y = max(0, min(preview.height, event.y))
            sx, sy = selection["start"]
            selection["coords"] = (min(sx, x), min(sy, y), max(sx, x), max(sy, y))
            canvas.coords(rect, *selection["coords"])
        canvas.bind("<ButtonPress-1>", start)
        canvas.bind("<B1-Motion>", drag)
        actions = Frame(dialog, bg="#111A27")
        actions.pack(fill="x", padx=12, pady=10)
        def apply() -> None:
            x0, y0, x1, y1 = selection["coords"]
            if x1 - x0 < 8 or y1 - y0 < 8:
                messagebox.showwarning(APP_NAME, "Select a larger area by dragging on the image.", parent=dialog)
                return
            self.config["background_crop"] = [x0 / preview.width, y0 / preview.height, x1 / preview.width, y1 / preview.height]
            save_config(self.config)
            dialog.destroy()
            self.draw_ui()
        Button(actions, text="Cancel", command=dialog.destroy, bg="#263548", fg="#E2E8F0", relief="flat", padx=12).pack(side=RIGHT)
        Button(actions, text="Apply selection", command=apply, bg="#5B8DEF", fg="#FFFFFF", relief="flat", padx=12).pack(side=RIGHT, padx=(0, 8))

    def reset_background(self) -> None:
        cache_value = str(self.config.get("background_cache") or "").strip()
        if cache_value:
            try:
                (BASE_DIR / cache_value).unlink(missing_ok=True)
            except OSError:
                pass
        self.config["background_image"] = ""
        self.config["background_cache"] = ""
        self.config["background_blur"] = 0
        self.config["background_crop"] = [0.0, 0.0, 1.0, 1.0]
        self.background_status = "missing"
        self.background_search_done = True
        save_config(self.config)
        self.draw_ui()

    def toggle_show_unknown(self) -> None:
        self.show_unknown = bool(self.show_unknown_var.get())
        self.config["show_devices_without_reading"] = self.show_unknown
        save_config(self.config)
        self.draw_ui()

    def start_drag(self, event) -> None:
        self.drag_start = (event.x, event.y)

    def drag(self, event) -> None:
        x = self.root.winfo_pointerx() - self.drag_start[0]
        y = self.root.winfo_pointery() - self.drag_start[1]
        self.root.geometry(f"+{x}+{y}")

    def end_drag(self, _event) -> None:
        self.user_moved = True
        x, y = self.clamp_window_position(self.root.winfo_x(), self.root.winfo_y())
        self.root.geometry(f"+{x}+{y}")
        self.config["position"] = {"x": x, "y": y}
        self.config["dock_bottom_right"] = False
        save_config(self.config)

    def show_menu(self, event) -> None:
        self.menu_open_until = time.time() + 8
        try:
            label = "Locate background image…" if self.background_status == "missing" else "Choose background image…"
            self.menu.entryconfigure(self.bg_menu_index, label=label)
        except Exception:
            pass
        try:
            x, y = self.menu_popup_position(event.x_root, event.y_root)
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()
            if self.config.get("always_on_top", False):
                try:
                    self.root.attributes("-topmost", True)
                except Exception:
                    pass

    def menu_popup_position(self, requested_x: int, requested_y: int) -> tuple[int, int]:
        left, top, right, bottom = get_work_area()
        menu_width = 230
        menu_height = 360
        x = requested_x
        y = requested_y
        if x + menu_width > right:
            x = max(left, requested_x - menu_width)
        if y + menu_height > bottom:
            y = max(top, bottom - menu_height)
        return x, y

    def position_bottom_right_if_needed(self) -> None:
        if not self.config.get("dock_bottom_right", True):
            self.ensure_window_inside_work_area()
            return
        self.root.update_idletasks()
        left, top, right, bottom = get_work_area()
        margin = int(self.config.get("bottom_right_margin", 18))
        width, height = self.actual_window_size()
        x = max(left, right - width - margin)
        y = max(top, bottom - height - margin)
        self.root.geometry(f"+{x}+{y}")
        self.config["position"] = {"x": x, "y": y}
        save_config(self.config)

    def actual_window_size(self) -> tuple[int, int]:
        self.root.update_idletasks()
        width = max(self.root.winfo_width(), self.root.winfo_reqwidth())
        height = max(self.root.winfo_height(), self.root.winfo_reqheight())
        return width, height

    def clamp_window_position(self, x: int, y: int) -> tuple[int, int]:
        left, top, right, bottom = get_work_area()
        width, height = self.actual_window_size()
        x = min(max(left, x), max(left, right - width))
        y = min(max(top, y), max(top, bottom - height))
        return x, y

    def ensure_window_inside_work_area(self) -> None:
        x, y = self.clamp_window_position(self.root.winfo_x(), self.root.winfo_y())
        if x != self.root.winfo_x() or y != self.root.winfo_y():
            self.root.geometry(f"+{x}+{y}")
            self.config["position"] = {"x": x, "y": y}
            save_config(self.config)

    def set_threshold(self) -> None:
        current = int(self.config.get("low_battery_threshold", 20))
        value = simpledialog.askinteger("Low Battery Threshold", "Notify when battery is at or below:", initialvalue=current, minvalue=1, maxvalue=100, parent=self.root)
        if value is None:
            return
        self.config["low_battery_threshold"] = int(value)
        save_config(self.config)
        self.render(getattr(self, "current_devices", []))

    def toggle_notifications(self) -> None:
        enabled = not bool(self.config.get("notifications_enabled", True))
        self.config["notifications_enabled"] = enabled
        save_config(self.config)
        messagebox.showinfo(APP_NAME, f"Low battery notifications {'enabled' if enabled else 'disabled'}.", parent=self.root)

    def toggle_stay_on_top(self) -> None:
        enabled = not bool(self.config.get("always_on_top", False))
        self.config["always_on_top"] = enabled
        self.config["aggressive_topmost"] = enabled
        save_config(self.config)
        try:
            self.root.attributes("-topmost", enabled)
        except Exception:
            pass

    def toggle_startup(self) -> None:
        enabled = not is_startup_enabled()
        ok = set_startup_enabled(enabled)
        state = "enabled" if is_startup_enabled() else "disabled"
        if ok:
            messagebox.showinfo(APP_NAME, f"Startup is {state}.", parent=self.root)
        else:
            messagebox.showwarning(APP_NAME, f"Could not change startup. Current state: {state}.", parent=self.root)

    def toggle_hide_atk_hub(self) -> None:
        enabled = not bool(self.config.get("hide_atk_hub_window", True))
        self.config["hide_atk_hub_window"] = enabled
        save_config(self.config)
        if enabled:
            hide_atk_hub_windows(resolve_atk_hub_path(self.config))
        messagebox.showinfo(APP_NAME, f"ATK HUB window hiding is {'enabled' if enabled else 'disabled'}.", parent=self.root)

    def install_atk_task(self) -> None:
        atk_hub_path = resolve_atk_hub_path(self.config)
        if not atk_hub_path:
            messagebox.showwarning(APP_NAME, "Could not find ATK HUB. Set atk_hub_path in the config first.", parent=self.root)
            return
        install_atk_hub_task(atk_hub_path)
        messagebox.showinfo(APP_NAME, "Approve the Windows prompt once. After that, ATK HUB can be started through a scheduled task.", parent=self.root)

    def open_source_file(self) -> None:
        if getattr(sys, "frozen", False):
            open_path(BASE_DIR)
        else:
            open_path(Path(__file__).resolve(), select=True)

    def open_app_folder(self) -> None:
        open_path(BASE_DIR)

    def force_topmost(self) -> None:
        if self.config.get("always_on_top", False) and time.time() >= self.menu_open_until:
            try:
                self.root.attributes("-topmost", True)
                if self.config.get("aggressive_topmost", False) and os.name == "nt":
                    hwnd = self.root.winfo_id()
                    ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)
            except Exception:
                pass
        elif not self.config.get("always_on_top", False):
            try:
                self.root.attributes("-topmost", False)
            except Exception:
                pass
        self.root.after(800, self.force_topmost)

    def bring_to_front(self) -> None:
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            show_window_in_taskbar(self.root)
        except Exception:
            pass

    def hide_atk_hub_window_loop(self) -> None:
        if self.config.get("hide_atk_hub_window", True):
            atk_hub_path = resolve_atk_hub_path(self.config)
            hide_atk_hub_windows(atk_hub_path)
            visible_count = visible_atk_hub_window_count(atk_hub_path)
            if visible_count > 0 and time.time() - self.last_atk_hide_task_run >= 10 and is_atk_hide_task_installed(self.config):
                if run_atk_hide_task(self.config):
                    self.last_atk_hide_task_run = time.time()
        self.root.after(2000, self.hide_atk_hub_window_loop)

    def restore_after_show_desktop(self) -> None:
        if self.config.get("restore_after_show_desktop", True):
            try:
                if self.root.state() == "iconic" and is_desktop_foreground():
                    self.bring_to_front()
            except Exception:
                pass
        self.root.after(1000, self.restore_after_show_desktop)

    def refresh(self) -> None:
        if self.refreshing:
            return
        self.refreshing = True
        if self.refresh_timer is not None:
            self.root.after_cancel(self.refresh_timer)
            self.refresh_timer = None
        if not self.current_devices:
            self.last_updated_text = "syncing…"
        self.draw_ui()
        threading.Thread(target=self.worker, daemon=True).start()

    def refresh_codex_usage(self) -> None:
        def fetch():
            try:
                result = read_codex_usage()
            except Exception:
                result = None
            self.events.put(("codex_usage", result))
        threading.Thread(target=fetch, daemon=True).start()

    def refresh_deepseek_balance(self) -> None:
        def fetch():
            try:
                result = read_deepseek_balance()
            except Exception:
                result = None
            self.events.put(("deepseek_balance", result))
        threading.Thread(target=fetch, daemon=True).start()

    def worker(self) -> None:
        try:
            devices = collect_devices(self.config)
        except Exception:
            write_error_log(f"{datetime.now():%Y-%m-%d %H:%M:%S}\n{traceback.format_exc()}")
            devices = []
        self.events.put(("devices", devices))

    def drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "codex_usage":
                    if payload:
                        self.codex_usage = payload
                        self.codex_usage_status = ""
                    else:
                        self.codex_usage_status = "Last reading kept; retrying in 60s"
                    self.draw_ui()
                    self.root.after(60000, self.refresh_codex_usage)
                if kind == "deepseek_balance":
                    if payload:
                        self.deepseek_balance = payload
                        self.deepseek_status = ""
                    else:
                        self.deepseek_status = "Balance unavailable"
                    self.draw_ui()
                    self.root.after(60000, self.refresh_deepseek_balance)
                if kind == "devices":
                    self.refreshing = False
                    self.render(payload)
        except queue.Empty:
            pass
        self.root.after(250, self.drain_events)

    def render(self, devices: list[DeviceBattery]) -> None:
        self.current_devices = devices
        self.check_low_battery(devices)
        self.last_updated_text = datetime.now().strftime("%H:%M")
        self.draw_ui()
        self.position_bottom_right_if_needed()
        interval = int(self.config.get("refresh_seconds", REFRESH_SECONDS))
        self.refresh_timer = self.root.after(max(10, interval) * 1000, self.refresh)

    def check_low_battery(self, devices: list[DeviceBattery]) -> None:
        if not self.config.get("notifications_enabled", True):
            return
        threshold = int(self.config.get("low_battery_threshold", 20))
        cooldown = max(1, int(self.config.get("notification_cooldown_minutes", 30))) * 60
        now = time.time()
        low_keys: set[str] = set()
        changed = False
        for device in devices:
            if device.level is None or device.level > threshold:
                continue
            key = notification_device_key(device)
            low_keys.add(key)
            if key in self.low_battery_active_keys:
                continue
            if now - self.last_notifications.get(key, 0) < cooldown:
                continue
            self.low_battery_active_keys.add(key)
            self.last_notifications[key] = now
            changed = True
            if self.config.get("mute_notifications_while_fullscreen", True) and is_foreground_fullscreen():
                continue
            notify_low_battery(device, threshold)
        recovered_keys = self.low_battery_active_keys - low_keys
        if recovered_keys:
            self.low_battery_active_keys -= recovered_keys
            changed = True
        if changed:
            self.config["low_battery_active_keys"] = sorted(self.low_battery_active_keys)
            self.config["last_low_battery_notifications"] = self.last_notifications
            save_config(self.config)

    @staticmethod
    def rounded_rect(canvas: Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> None:
        points = [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]
        canvas.create_polygon(points, smooth=True, splinesteps=12, **kwargs)

    def presentation(self) -> tuple[list[DeviceBattery], list[DeviceBattery]]:
        """Pick what is worth showing: readable batteries first, noise last.

        Vendor PnP nodes such as "Razer Device" or "Logitech Device" are only
        interface names.  When a real device from the same vendor already has a
        percentage, those placeholder rows add nothing and are dropped.
        """
        known = [device for device in self.current_devices if device.level is not None]
        unknown = [device for device in self.current_devices if device.level is None]
        known_vendors = {device_vendor(device.name) for device in known}
        filtered: list[DeviceBattery] = []
        seen: set[str] = set()
        for device in unknown:
            key = device.name.lower()
            if key in seen:
                continue
            vendor = device_vendor(device.name)
            if vendor and vendor in known_vendors and GENERIC_DEVICE_NODE.search(device.name):
                continue
            seen.add(key)
            filtered.append(device)
        known.sort(key=lambda device: (device.level if device.level is not None else 101, device.name.lower()))
        filtered.sort(key=lambda device: (device_vendor(device.name), device.name.lower()))
        return known, filtered

    @staticmethod
    def _epoch_seconds(value) -> float | None:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return None
        return None

    def codex_snapshot(self) -> tuple[str, str, str, str]:
        label = "CODEX 5H"
        usage = self.codex_usage
        if not usage:
            return label, "—", self.codex_usage_status or "waiting for Codex", "#7E90A6"
        try:
            remaining = max(0.0, min(100.0, float(usage.get("remaining"))))
        except (TypeError, ValueError):
            return label, "—", "bad reading", "#7E90A6"
        color = "#F16E6E" if remaining <= 10 else "#F2B65D" if remaining <= 30 else "#69D5A6"
        age = max(0.0, time.time() - float(usage.get("fetched_at") or 0))
        resets_at = self._epoch_seconds(usage.get("resets_at"))
        if resets_at and resets_at > time.time():
            seconds = int(resets_at - time.time())
            sub = f"resets in {seconds // 3600}h {seconds % 3600 // 60:02d}m" if seconds >= 3600 else f"resets in {max(1, seconds // 60)}m"
        elif resets_at:
            sub = "window resetting"
        elif age > 300:
            sub = f"stale · {int(age // 60)}m ago"
        else:
            sub = f"updated {datetime.fromtimestamp(usage.get('fetched_at', time.time())).strftime('%H:%M')}"
        return label, f"{remaining:g}% left", sub, color

    def balance_snapshot(self) -> tuple[str, str, str, str]:
        label = "DEEPSEEK"
        data = self.deepseek_balance
        if not data:
            return label, "—", self.deepseek_status or "waiting for balance", "#7E90A6"
        amount = data.get("balance")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            return label, "—", "bad reading", "#7E90A6"
        currency = str(data.get("currency") or "CNY")
        fetched_at = self._epoch_seconds(data.get("fetched_at")) or 0
        age = max(0.0, time.time() - fetched_at) if fetched_at else 0
        if data.get("stale"):
            return label, "—", f"stale · {max(1, int(age // 60))}m old", "#F2B65D"
        value = format_money(float(amount), currency)
        today = data.get("today")
        if fetched_at and age > 600:
            sub = f"stale · {int(age // 60)}m ago"
        elif isinstance(today, (int, float)) and not isinstance(today, bool):
            sub = f"today {format_money(float(today), currency)}"
        elif fetched_at:
            sub = f"updated {datetime.fromtimestamp(fetched_at).strftime('%H:%M')}"
        else:
            sub = str(data.get("source") or "DSH")
        color = "#F16E6E" if float(amount) <= 1 else "#F2B65D" if float(amount) <= 5 else "#DCE7F5"
        return label, value, sub, color

    def draw_ui(self) -> None:
        if not hasattr(self, "canvas") or not self.root.winfo_exists():
            return
        width, pad, header_h, row_h, footer_h = 360, 10, 58, 58, 56
        known, unknown = self.presentation()
        rows = len(known) + (len(unknown) if self.show_unknown else 0)
        summary_h = 24 if unknown else 0
        empty_h = 36 if not known and not unknown else 0
        height = pad * 2 + header_h + rows * row_h + summary_h + empty_h + footer_h
        try:
            pos = self.config.get("position", {})
            if getattr(self, "user_moved", False):
                x, y = self.root.winfo_x(), self.root.winfo_y()
            else:
                # The window manager can pick its own cascade position before
                # the first geometry call.  Trust the saved position instead.
                x, y = int(pos.get("x", 40)), int(pos.get("y", 60))
                if self.config.get("dock_bottom_right", True):
                    left, top, right, bottom = get_work_area()
                    margin = int(self.config.get("bottom_right_margin", 18))
                    x = max(left, right - width - margin)
                    y = max(top, bottom - height - margin)
            screen_left, screen_top, screen_right, screen_bottom = virtual_screen_bounds()
            if x + width <= screen_left + 30 or x >= screen_right - 30 or y + height <= screen_top + 30 or y >= screen_bottom - 30:
                x = max(screen_left + 10, screen_right - width - 18)
                y = max(screen_top + 10, screen_bottom - height - 18)
                if not getattr(self, "user_moved", False):
                    self.config["position"] = {"x": x, "y": y}
                    try:
                        save_config(self.config)
                    except Exception:
                        pass
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass
        self.canvas.configure(width=width, height=height, bg="#0B111A")
        self.root.after_idle(self.apply_window_corners)
        self.canvas.delete("all")
        self.backdrop_photo = None

        image_path, background_status = resolve_background_path(self.config, search_moved=not self.background_search_done)
        self.background_search_done = True
        self.background_status = background_status
        has_backdrop = False
        if Image is not None and image_path is not None:
            try:
                with Image.open(image_path) as original:
                    source = original.convert("RGB")
                    crop = self.config.get("background_crop", [0.0, 0.0, 1.0, 1.0])
                    try:
                        left, top, right, bottom = (float(crop[0]), float(crop[1]), float(crop[2]), float(crop[3]))
                        left, top = max(0.0, min(1.0, left)), max(0.0, min(1.0, top))
                        right, bottom = max(left + 0.01, min(1.0, right)), max(top + 0.01, min(1.0, bottom))
                        source = source.crop((int(left * source.width), int(top * source.height), int(right * source.width), int(bottom * source.height)))
                    except Exception:
                        pass
                    image = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS)
                if ImageEnhance is not None:
                    image = ImageEnhance.Brightness(image).enhance(0.82)
                blur = max(0, min(24, int(self.config.get("background_blur", 8))))
                if blur:
                    image = image.filter(ImageFilter.GaussianBlur(radius=blur))
                # Blend instead of a Tk stipple: a smooth overlay avoids the
                # visible dot pattern and keeps the photo readable behind text.
                dark = Image.new("RGB", image.size, "#08111D")
                image = Image.blend(image, dark, 0.55)
                self.backdrop_photo = ImageTk.PhotoImage(image)
                self.canvas.create_image(0, 0, image=self.backdrop_photo, anchor="nw")
                has_backdrop = True
            except Exception:
                has_backdrop = False

        panel = {"outline": "#2A3B50", "width": 1, "fill": "#0E1927"}
        if has_backdrop:
            panel["fill"] = ""
        self.rounded_rect(self.canvas, pad, pad, width - pad, height - pad, 14, **panel)

        threshold = int(self.config.get("low_battery_threshold", 20))
        lowest = min((device.level for device in known if device.level is not None), default=None)
        status_color = "#7E90A6" if lowest is None else "#F16E6E" if lowest <= threshold else "#F2B65D" if lowest <= 40 else "#69D5A6"
        self.canvas.create_oval(pad + 13, pad + 17, pad + 21, pad + 25, fill=status_color, outline="")
        self.canvas.create_text(pad + 28, pad + 9, text="WIRELESS BATTERY", fill="#F2F6FC", font=("Segoe UI", 9), anchor="nw", outline=False)
        if known:
            subtitle = f"{len(known)} active · lowest {lowest}%"
        elif unknown:
            subtitle = f"{len(unknown)} connected · no reading"
        else:
            subtitle = "No devices found"
        self.canvas.create_text(pad + 28, pad + 29, text=subtitle, fill="#93A4B8", font=("Segoe UI", 7), anchor="nw", outline=False)
        self.canvas.create_text(width - pad - 12, pad + 9, text=self.last_updated_text, fill="#8FA2B8", font=("Segoe UI", 7), anchor="ne", outline=False)
        self.canvas.create_text(width - pad - 12, pad + 28, text="···", fill="#C7D3E3", font=("Segoe UI", 10), anchor="ne", tags=("menu",))

        y = pad + header_h
        drawn = 0
        for device in known:
            self.draw_device_row(y, device, width, row_h, pad)
            drawn += 1
            if drawn < rows:
                self.canvas.create_line(pad + 16, y + row_h - 1, width - pad - 14, y + row_h - 1, fill="#1B2A3C")
            y += row_h
        if self.show_unknown:
            for device in unknown:
                self.draw_device_row(y, device, width, row_h, pad, show_bar=False)
                drawn += 1
                if drawn < rows:
                    self.canvas.create_line(pad + 16, y + row_h - 1, width - pad - 14, y + row_h - 1, fill="#1B2A3C")
                y += row_h
        if unknown:
            action = "hide" if self.show_unknown else "show"
            label = f"{'−' if self.show_unknown else '+'} {len(unknown)} device{'s' if len(unknown) != 1 else ''} without reading · tap to {action}"
            self.canvas.create_text(pad + 16, y + 5, text=label, fill="#8FA2B8", font=("Segoe UI", 7), anchor="nw", outline=False, tags=("unknowns",))
            y += summary_h
        if not known and not unknown:
            self.canvas.create_text(width // 2, y + 10, text="Connect a wireless device, then refresh.", fill="#93A4B8", font=("Segoe UI", 7), anchor="n", outline=False)

        footer_top = height - pad - footer_h
        self.canvas.create_line(pad + 14, footer_top, width - pad - 14, footer_top, fill="#26364A")
        self.canvas.create_line(width // 2, footer_top + 9, width // 2, footer_top + footer_h - 12, fill="#1E2C3E")
        for column, snapshot in enumerate((self.codex_snapshot(), self.balance_snapshot())):
            label, value, sub, color = snapshot
            x = pad + 14 if column == 0 else width // 2 + 12
            self.canvas.create_text(x, footer_top + 9, text=label, fill="#7E90A6", font=("Segoe UI", 6), anchor="nw", outline=False)
            self.canvas.create_text(x, footer_top + 21, text=value, fill=color, font=("Segoe UI", 12), anchor="nw")
            self.canvas.create_text(x, footer_top + 41, text=sub, fill="#8FA2B8", font=("Segoe UI", 7), anchor="nw", outline=False)

        self.canvas.tag_bind("menu", "<Button-1>", self.open_menu_from_canvas)
        self.canvas.tag_bind("unknowns", "<Button-1>", self.toggle_unknown_from_canvas)

    def draw_device_row(self, top: int, device: DeviceBattery, width: int, row_h: int, pad: int, show_bar: bool = True) -> None:
        left, right = pad + 16, width - pad - 14
        threshold = int(self.config.get("low_battery_threshold", 20))
        level = device.level
        color = "#4A5A70" if level is None else "#69D5A6"
        if level is not None:
            color = "#F16E6E" if level <= threshold else "#F2B65D" if level <= 40 else "#69D5A6"
        self.rounded_rect(self.canvas, left - 7, top + 13, left - 4, top + row_h - 15, 2, fill=color, outline="")
        name = device.name if len(device.name) <= 32 else device.name[:30] + "…"
        self.canvas.create_text(left, top + 8, text=name, fill="#F2F6FC", font=("Segoe UI", 9), anchor="nw")
        source = compact_source(device.source)
        status = re.sub(r"\s+", " ", device.status or "").strip()
        if status:
            source = f"{source} · {status}"
        if len(source) > 44:
            source = source[:42] + "…"
        self.canvas.create_text(left, top + 27, text=source, fill="#93A4B8", font=("Segoe UI", 7), anchor="nw", outline=False)
        percent = "—" if level is None else f"{level}%"
        self.canvas.create_text(right, top + 6, text=percent, fill="#8EA0B6" if level is None else color, font=("Segoe UI", 14), anchor="ne")
        if show_bar and level is not None:
            bar_y = top + 45
            self.rounded_rect(self.canvas, left, bar_y, right, bar_y + 4, 2, fill="#223247", outline="")
            fill_width = max(4, int((right - left) * level / 100))
            self.rounded_rect(self.canvas, left, bar_y, left + fill_width, bar_y + 4, 2, fill=color, outline="")

    def open_menu_from_canvas(self, event) -> None:
        self.show_menu(event)

    def toggle_unknown_from_canvas(self, _event) -> None:
        self.show_unknown_var.set(not self.show_unknown)
        self.toggle_show_unknown()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    if os.name != "nt":
        print("This widget is intended for Windows.")
    else:
        BatteryWidget().run()
