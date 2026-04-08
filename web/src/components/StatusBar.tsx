import { useSessionStore } from '../stores/sessionStore';

export function StatusBar() {
  const isConnected = useSessionStore((s) => s.isConnected);
  const fps = useSessionStore((s) => s.fps);
  const latency = useSessionStore((s) => s.latency);
  const remoteResolution = useSessionStore((s) => s.remoteResolution);

  return (
    <div className="flex items-center justify-between border-t border-gray-800 bg-gray-900/90 px-4 py-1.5 text-xs backdrop-blur">
      <div className="flex items-center gap-1.5">
        <span
          className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}
        />
        <span className={isConnected ? 'text-green-400' : 'text-red-400'}>
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      <div className="flex items-center gap-4 text-gray-400">
        <span>{fps} FPS</span>
        {latency > 0 && <span>{latency}ms</span>}
      </div>

      <div className="text-gray-400">
        {remoteResolution[0]}x{remoteResolution[1]}
      </div>
    </div>
  );
}
