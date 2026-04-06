import { useState, useRef, useCallback } from 'react';
import { useSessionStore } from '../stores/sessionStore';
import { buildConfigMsg, type ProtocolMsg } from '../utils/protocol';

interface ToolbarProps {
  agentId: string;
  onDisconnect: () => void;
  send: (msg: ProtocolMsg | Record<string, unknown>) => void;
}

export function Toolbar({ agentId, onDisconnect, send }: ToolbarProps) {
  const quality = useSessionStore((s) => s.quality);
  const updateStats = useSessionStore((s) => s.updateStats);

  const [localQuality, setLocalQuality] = useState(quality);
  const [localFps, setLocalFps] = useState(24);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sendConfig = useCallback(
    (q: number, f: number) => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
      debounceTimer.current = setTimeout(() => {
        send(buildConfigMsg(q, f));
        updateStats({ quality: q });
      }, 300);
    },
    [send, updateStats],
  );

  function handleQualityChange(val: number) {
    setLocalQuality(val);
    sendConfig(val, localFps);
  }

  function handleFpsChange(val: number) {
    setLocalFps(val);
    sendConfig(localQuality, val);
  }

  function handleFullscreen() {
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      document.documentElement.requestFullscreen();
    }
  }

  return (
    <div className="flex items-center justify-between border-b border-gray-800 bg-gray-900/90 px-4 py-2 backdrop-blur">
      <div className="flex items-center gap-3">
        <span className="text-sm font-bold text-white">RemoteGate</span>
        <span className="text-xs text-gray-400">{agentId}</span>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-400">Quality</label>
          <input
            type="range"
            min={30}
            max={80}
            value={localQuality}
            onChange={(e) => handleQualityChange(Number(e.target.value))}
            className="h-1 w-20 cursor-pointer accent-blue-500"
          />
          <span className="w-6 text-xs text-gray-300">{localQuality}</span>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-400">FPS</label>
          <input
            type="range"
            min={10}
            max={30}
            value={localFps}
            onChange={(e) => handleFpsChange(Number(e.target.value))}
            className="h-1 w-20 cursor-pointer accent-blue-500"
          />
          <span className="w-6 text-xs text-gray-300">{localFps}</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={handleFullscreen}
          className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-300 transition hover:bg-gray-800"
          title="Toggle Fullscreen"
        >
          Fullscreen
        </button>
        <button
          onClick={onDisconnect}
          className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-red-500"
        >
          Disconnect
        </button>
      </div>
    </div>
  );
}
