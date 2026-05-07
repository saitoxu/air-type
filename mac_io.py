"""Wrappers around pyautogui / pyperclip / mss for Mac control + screen capture."""

from __future__ import annotations

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
