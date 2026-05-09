"""Wrappers around pyautogui / pyperclip / mss for Mac control + screen capture."""

from __future__ import annotations

import base64
import io
import time

import mss
import pyautogui
import pyperclip
from PIL import Image

pyautogui.PAUSE = 0.02
pyautogui.FAILSAFE = False

_warmed_up = False


def _warmup() -> None:
    """Press and release Command once so the first real hotkey doesn't drop the modifier."""
    global _warmed_up
    if _warmed_up:
        return
    pyautogui.keyDown('command')
    time.sleep(0.05)
    pyautogui.keyUp('command')
    time.sleep(0.05)
    _warmed_up = True


def paste_text(text: str) -> None:
    """Copy text to clipboard and emit Cmd+V at the current focus."""
    if not text:
        return
    _warmup()
    pyperclip.copy(text)
    pyautogui.keyDown('command')
    time.sleep(0.03)
    pyautogui.press('v')
    time.sleep(0.03)
    pyautogui.keyUp('command')


def press_backspace(count: int = 1) -> None:
    pyautogui.press('backspace', presses=max(1, count), interval=0.01)


def press_enter() -> None:
    pyautogui.press('enter')


def click_at(x: int, y: int) -> None:
    pyautogui.click(x=x, y=y)


def screen_size() -> tuple[int, int]:
    """Logical screen size (the coordinate space pyautogui uses)."""
    size = pyautogui.size()
    return int(size.width), int(size.height)


def caret_position() -> tuple[int, int] | None:
    """Return the current text caret screen position via macOS Accessibility API.

    Returns None when the focused app does not expose AX info, or accessibility
    permission has not been granted to the running process.
    """
    try:
        from HIServices import (
            AXUIElementCreateSystemWide,
            AXUIElementCopyAttributeValue,
            AXUIElementCopyParameterizedAttributeValue,
            AXValueGetValue,
            kAXValueCGRectType,
        )
    except Exception:
        return None

    try:
        sw = AXUIElementCreateSystemWide()
        err, focused = AXUIElementCopyAttributeValue(sw, 'AXFocusedUIElement', None)
        if err != 0 or focused is None:
            return None

        # Preferred: caret bounds inside a text field via AXBoundsForRange.
        err, rng = AXUIElementCopyAttributeValue(focused, 'AXSelectedTextRange', None)
        if err == 0 and rng is not None:
            err, bounds = AXUIElementCopyParameterizedAttributeValue(
                focused, 'AXBoundsForRange', rng, None
            )
            if err == 0 and bounds is not None:
                ok, rect = AXValueGetValue(bounds, kAXValueCGRectType, None)
                if ok:
                    cx = int(rect.origin.x + rect.size.width / 2)
                    cy = int(rect.origin.y + rect.size.height / 2)
                    return cx, cy

        # Fallback: center of the focused element itself.
        err_p, pos = AXUIElementCopyAttributeValue(focused, 'AXPosition', None)
        err_s, sz = AXUIElementCopyAttributeValue(focused, 'AXSize', None)
        if err_p == 0 and err_s == 0 and pos is not None and sz is not None:
            from HIServices import kAXValueCGPointType, kAXValueCGSizeType
            ok_p, point = AXValueGetValue(pos, kAXValueCGPointType, None)
            ok_s, size = AXValueGetValue(sz, kAXValueCGSizeType, None)
            if ok_p and ok_s:
                cx = int(point.x + size.width / 2)
                cy = int(point.y + size.height / 2)
                return cx, cy
    except Exception:
        return None
    return None


_icon_cache: dict[int, str] = {}


def _ns_image_to_data_url(image, size: int = 64) -> str | None:
    if image is None:
        return None
    try:
        from AppKit import NSBitmapImageRep
    except Exception:
        return None
    try:
        image.setSize_((size, size))
        tiff = image.TIFFRepresentation()
        if tiff is None:
            return None
        rep = NSBitmapImageRep.imageRepWithData_(tiff)
        if rep is None:
            return None
        # NSBitmapImageFileTypePNG = 4
        png = rep.representationUsingType_properties_(4, None)
        if png is None:
            return None
        b64 = base64.b64encode(bytes(png)).decode('ascii')
        return f'data:image/png;base64,{b64}'
    except Exception:
        return None


def list_apps() -> list[dict]:
    """Return regular GUI apps currently running, with name/pid/active/icon."""
    try:
        from AppKit import NSWorkspace
    except Exception:
        return []
    ws = NSWorkspace.sharedWorkspace()
    out: list[dict] = []
    live_pids: set[int] = set()
    for app in ws.runningApplications():
        # NSApplicationActivationPolicyRegular = 0 (skip background/agent apps)
        if app.activationPolicy() != 0:
            continue
        pid = int(app.processIdentifier())
        live_pids.add(pid)
        icon_url = _icon_cache.get(pid)
        if icon_url is None:
            icon_url = _ns_image_to_data_url(app.icon())
            if icon_url:
                _icon_cache[pid] = icon_url
        out.append({
            'pid': pid,
            'name': app.localizedName() or '?',
            'active': bool(app.isActive()),
            'icon': icon_url,
        })
    # Drop icons for apps that have quit
    for pid in list(_icon_cache.keys()):
        if pid not in live_pids:
            _icon_cache.pop(pid, None)
    out.sort(key=lambda a: (not a['active'], a['name'].lower()))
    return out


def activate_app(pid: int) -> bool:
    """Bring the given app's PID to the front."""
    try:
        from AppKit import NSRunningApplication
    except Exception:
        return False
    app = NSRunningApplication.runningApplicationWithProcessIdentifier_(int(pid))
    if app is None:
        return False
    # NSApplicationActivateAllWindows (1) | NSApplicationActivateIgnoringOtherApps (2)
    return bool(app.activateWithOptions_(3))


def grab_screenshot_jpeg(width: int, quality: int) -> bytes:
    """Capture the primary monitor and return a JPEG-encoded screenshot resized to `width`."""
    with mss.MSS() as sct:
        shot = sct.grab(sct.monitors[1])
        img = Image.frombytes('RGB', shot.size, shot.rgb)
    if img.width > width:
        ratio = width / img.width
        img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    return buf.getvalue()
