import { useEffect } from 'react';
import { buildKeyMsg, type KeyMsg } from '../utils/protocol';

const KEY_MAP: Record<string, string> = {
  Enter: 'Enter',
  Tab: 'Tab',
  Escape: 'Escape',
  Backspace: 'Backspace',
  Delete: 'Delete',
  ArrowUp: 'Up',
  ArrowDown: 'Down',
  ArrowLeft: 'Left',
  ArrowRight: 'Right',
  Home: 'Home',
  End: 'End',
  PageUp: 'PageUp',
  PageDown: 'PageDown',
  Insert: 'Insert',
  F1: 'F1',
  F2: 'F2',
  F3: 'F3',
  F4: 'F4',
  F5: 'F5',
  F6: 'F6',
  F7: 'F7',
  F8: 'F8',
  F9: 'F9',
  F10: 'F10',
  F11: 'F11',
  F12: 'F12',
  ' ': 'space',
  CapsLock: 'CapsLock',
  PrintScreen: 'PrintScreen',
  ScrollLock: 'ScrollLock',
  Pause: 'Pause',
  NumLock: 'NumLock',
};

function buildKeyString(e: KeyboardEvent): string | null {
  // Ignore standalone modifier key events
  if (['Control', 'Alt', 'Shift', 'Meta'].includes(e.key)) {
    return null;
  }

  const parts: string[] = [];
  if (e.ctrlKey) parts.push('ctrl');
  if (e.altKey) parts.push('alt');
  if (e.shiftKey && (e.key.length > 1 || e.ctrlKey || e.altKey)) parts.push('shift');
  if (e.metaKey) parts.push('meta');

  const mapped = KEY_MAP[e.key];
  if (mapped) {
    parts.push(mapped);
  } else if (e.key.length === 1) {
    parts.push(e.key);
  } else {
    parts.push(e.key);
  }

  return parts.join('+');
}

export function useKeyboardCapture(
  isActive: boolean,
  sendFn: (msg: KeyMsg) => void,
): void {
  useEffect(() => {
    if (!isActive) return;

    function onKeyDown(e: KeyboardEvent) {
      e.preventDefault();
      e.stopPropagation();
      const key = buildKeyString(e);
      if (key) {
        sendFn(buildKeyMsg('press', key));
      }
    }

    function onKeyUp(e: KeyboardEvent) {
      e.preventDefault();
      e.stopPropagation();
      const key = buildKeyString(e);
      if (key) {
        sendFn(buildKeyMsg('release', key));
      }
    }

    window.addEventListener('keydown', onKeyDown, true);
    window.addEventListener('keyup', onKeyUp, true);

    return () => {
      window.removeEventListener('keydown', onKeyDown, true);
      window.removeEventListener('keyup', onKeyUp, true);
    };
  }, [isActive, sendFn]);
}
