"""
Input handler module.
Receives mouse and keyboard events from the relay server and injects them
into the local system using pynput.
"""

import logging

from pynput import keyboard, mouse

logger = logging.getLogger(__name__)

# Map of special key names to pynput Key enum values
SPECIAL_KEYS = {
    "ctrl": keyboard.Key.ctrl_l,
    "ctrl_l": keyboard.Key.ctrl_l,
    "ctrl_r": keyboard.Key.ctrl_r,
    "control": keyboard.Key.ctrl_l,
    "alt": keyboard.Key.alt_l,
    "alt_l": keyboard.Key.alt_l,
    "alt_r": keyboard.Key.alt_r,
    "shift": keyboard.Key.shift_l,
    "shift_l": keyboard.Key.shift_l,
    "shift_r": keyboard.Key.shift_r,
    "enter": keyboard.Key.enter,
    "return": keyboard.Key.enter,
    "tab": keyboard.Key.tab,
    "escape": keyboard.Key.esc,
    "esc": keyboard.Key.esc,
    "backspace": keyboard.Key.backspace,
    "delete": keyboard.Key.delete,
    "space": keyboard.Key.space,
    "up": keyboard.Key.up,
    "down": keyboard.Key.down,
    "left": keyboard.Key.left,
    "right": keyboard.Key.right,
    "home": keyboard.Key.home,
    "end": keyboard.Key.end,
    "pageup": keyboard.Key.page_up,
    "page_up": keyboard.Key.page_up,
    "pagedown": keyboard.Key.page_down,
    "page_down": keyboard.Key.page_down,
    "insert": keyboard.Key.insert,
    "caps_lock": keyboard.Key.caps_lock,
    "capslock": keyboard.Key.caps_lock,
    "num_lock": keyboard.Key.num_lock,
    "numlock": keyboard.Key.num_lock,
    "print_screen": keyboard.Key.print_screen,
    "printscreen": keyboard.Key.print_screen,
    "scroll_lock": keyboard.Key.scroll_lock,
    "pause": keyboard.Key.pause,
    "menu": keyboard.Key.menu,
    "cmd": keyboard.Key.cmd,
    "win": keyboard.Key.cmd,
    "super": keyboard.Key.cmd,
    "f1": keyboard.Key.f1,
    "f2": keyboard.Key.f2,
    "f3": keyboard.Key.f3,
    "f4": keyboard.Key.f4,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
    "f9": keyboard.Key.f9,
    "f10": keyboard.Key.f10,
    "f11": keyboard.Key.f11,
    "f12": keyboard.Key.f12,
}

# Map button names to pynput mouse buttons
MOUSE_BUTTONS = {
    "left": mouse.Button.left,
    "right": mouse.Button.right,
    "middle": mouse.Button.middle,
}


class InputHandler:
    """Handles mouse and keyboard input injection using pynput."""

    def __init__(self):
        self._mouse = mouse.Controller()
        self._keyboard = keyboard.Controller()
        logger.info("InputHandler initialized")

    def handle_input(self, data: dict):
        """Dispatch input event based on its type.

        Args:
            data: Dict with "type" key being "mouse" or "key".
        """
        event_type = data.get("type")
        try:
            if event_type == "mouse":
                self._handle_mouse(data)
            elif event_type == "key":
                self._handle_keyboard(data)
            else:
                logger.warning("Unknown input type: %s", event_type)
        except Exception:
            logger.exception("Error handling input event: %s", data)

    def _handle_mouse(self, data: dict):
        """Handle mouse events: move, click, double_click, scroll, drag.

        Args:
            data: Dict with "action", "x", "y", and optional "button"/"delta".
        """
        action = data.get("action")
        x = data.get("x", 0)
        y = data.get("y", 0)

        if action == "move":
            self._mouse.position = (x, y)

        elif action == "click":
            self._mouse.position = (x, y)
            button = MOUSE_BUTTONS.get(data.get("button", "left"), mouse.Button.left)
            self._mouse.click(button, 1)

        elif action == "double_click":
            self._mouse.position = (x, y)
            button = MOUSE_BUTTONS.get(data.get("button", "left"), mouse.Button.left)
            self._mouse.click(button, 2)

        elif action == "scroll":
            self._mouse.position = (x, y)
            delta = data.get("delta", 0)
            self._mouse.scroll(0, delta)

        elif action == "drag":
            # During drag, the client sends continuous "drag" events with the mouse
            # button held down. We just move the mouse position; the button press/release
            # is managed by separate click events from the client.
            self._mouse.position = (x, y)

        elif action == "button_down":
            self._mouse.position = (x, y)
            button = MOUSE_BUTTONS.get(data.get("button", "left"), mouse.Button.left)
            self._mouse.press(button)

        elif action == "button_up":
            self._mouse.position = (x, y)
            button = MOUSE_BUTTONS.get(data.get("button", "left"), mouse.Button.left)
            self._mouse.release(button)

        else:
            logger.warning("Unknown mouse action: %s", action)

    def _handle_keyboard(self, data: dict):
        """Handle keyboard events: single keys and combos (e.g. ctrl+c).

        Args:
            data: Dict with "action" and "key" fields.
                  key can be a single character or a combo like "ctrl+shift+a".
        """
        action = data.get("action", "press")
        key_str = data.get("key", "")

        if not key_str:
            logger.warning("Empty key in keyboard event")
            return

        # Check if it's a key combination (contains "+")
        if "+" in key_str:
            self._handle_combo(key_str)
        else:
            resolved = self._resolve_key(key_str)
            if action == "press":
                self._keyboard.press(resolved)
                self._keyboard.release(resolved)
            elif action == "down":
                self._keyboard.press(resolved)
            elif action == "up":
                self._keyboard.release(resolved)
            else:
                # Default: press and release
                self._keyboard.press(resolved)
                self._keyboard.release(resolved)

    def _handle_combo(self, combo_str: str):
        """Execute a keyboard combination like ctrl+c or ctrl+shift+a.

        Presses all modifier keys, then the main key, then releases in reverse order.

        Args:
            combo_str: Key combination string like "ctrl+c" or "ctrl+shift+a".
        """
        parts = [p.strip().lower() for p in combo_str.split("+")]
        if not parts:
            return

        # The last part is the main key, everything before is a modifier
        main_key_str = parts[-1]
        modifier_strs = parts[:-1]

        modifiers = [self._resolve_key(m) for m in modifier_strs]
        main_key = self._resolve_key(main_key_str)

        # Press modifiers in order
        for mod in modifiers:
            self._keyboard.press(mod)

        # Press and release main key
        self._keyboard.press(main_key)
        self._keyboard.release(main_key)

        # Release modifiers in reverse order
        for mod in reversed(modifiers):
            self._keyboard.release(mod)

    def _resolve_key(self, key_str: str):
        """Resolve a key string to a pynput key object.

        Args:
            key_str: Key name like "a", "ctrl", "f1", "enter", etc.

        Returns:
            pynput Key enum value or a character string for regular keys.
        """
        lower = key_str.lower().strip()

        # Check special keys map
        if lower in SPECIAL_KEYS:
            return SPECIAL_KEYS[lower]

        # Single character: return as-is for pynput
        if len(key_str) == 1:
            return key_str

        # Try keyboard.KeyCode for unknown keys
        logger.warning("Unrecognized key '%s', attempting as character", key_str)
        return key_str
