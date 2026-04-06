import { useRef, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useSessionStore } from '../stores/sessionStore';
import { useWebSocket } from '../hooks/useWebSocket';
import { useMouseCapture } from '../hooks/useMouseCapture';
import { useKeyboardCapture } from '../hooks/useKeyboardCapture';
import { buildSessionMsg, type FrameData, type MouseMsg, type KeyMsg } from '../utils/protocol';
import { Toolbar } from './Toolbar';
import { StatusBar } from './StatusBar';

export function RemoteScreen() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const token = useSessionStore((s) => s.token);
  const remoteResolution = useSessionStore((s) => s.remoteResolution);
  const setRemoteResolution = useSessionStore((s) => s.setRemoteResolution);
  const setConnected = useSessionStore((s) => s.setConnected);
  const updateStats = useSessionStore((s) => s.updateStats);
  const setAgentId = useSessionStore((s) => s.setAgentId);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pendingBitmap = useRef<ImageBitmap | null>(null);
  const animFrameId = useRef<number>(0);
  const frameCount = useRef(0);
  const fpsInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionStarted = useRef(false);

  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/client`;

  const onFrame = useCallback((frame: FrameData) => {
    createImageBitmap(frame.jpegBlob).then((bitmap) => {
      if (pendingBitmap.current) {
        pendingBitmap.current.close();
      }
      pendingBitmap.current = bitmap;
    });
    frameCount.current += 1;
  }, []);

  const onMessage = useCallback(
    (msg: Record<string, unknown>) => {
      if (msg.type === 'session_start') {
        const res = msg.resolution as [number, number] | undefined;
        if (res) {
          setRemoteResolution(res[0], res[1]);
        }
      } else if (msg.type === 'resolution_changed') {
        const res = msg.resolution as [number, number] | undefined;
        if (res) {
          setRemoteResolution(res[0], res[1]);
        }
      } else if (msg.type === 'stats') {
        updateStats({
          latency: msg.latency as number | undefined,
        });
      } else if (msg.type === 'error') {
        console.error('Server error:', msg.message);
      }
    },
    [setRemoteResolution, updateStats],
  );

  const { send, disconnect, isConnected } = useWebSocket({
    url: wsUrl,
    token: token ?? '',
    onFrame,
    onMessage,
    enabled: !!token && !!agentId,
  });

  // Send session_start once connected
  useEffect(() => {
    if (isConnected && agentId && !sessionStarted.current) {
      sessionStarted.current = true;
      setAgentId(agentId);
      setConnected(true);
      send(buildSessionMsg('session_start', agentId));
    }
    if (!isConnected) {
      sessionStarted.current = false;
      setConnected(false);
    }
  }, [isConnected, agentId, send, setAgentId, setConnected]);

  // Render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    function renderLoop() {
      const bitmap = pendingBitmap.current;
      if (bitmap && canvas) {
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
        ctx!.drawImage(bitmap, 0, 0);
      }
      animFrameId.current = requestAnimationFrame(renderLoop);
    }

    animFrameId.current = requestAnimationFrame(renderLoop);

    return () => {
      cancelAnimationFrame(animFrameId.current);
    };
  }, []);

  // FPS counter
  useEffect(() => {
    fpsInterval.current = setInterval(() => {
      updateStats({ fps: frameCount.current });
      frameCount.current = 0;
    }, 1000);

    return () => {
      if (fpsInterval.current) {
        clearInterval(fpsInterval.current);
      }
    };
  }, [updateStats]);

  // Mouse capture
  const sendMouse = useCallback(
    (msg: MouseMsg) => send(msg),
    [send],
  );

  useMouseCapture(canvasRef, remoteResolution, sendMouse, isConnected);

  // Keyboard capture
  const sendKey = useCallback(
    (msg: KeyMsg) => send(msg),
    [send],
  );

  useKeyboardCapture(isConnected, sendKey);

  // Disconnect handler
  const handleDisconnect = useCallback(() => {
    send(buildSessionMsg('session_end'));
    disconnect();
    setConnected(false);
    setAgentId(null);
    navigate('/', { replace: true });
  }, [send, disconnect, setConnected, setAgentId, navigate]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pendingBitmap.current) {
        pendingBitmap.current.close();
        pendingBitmap.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!token) {
      navigate('/login', { replace: true });
    }
  }, [token, navigate]);

  if (!token) return null;

  return (
    <div className="flex h-screen flex-col bg-black">
      <Toolbar
        agentId={agentId ?? ''}
        onDisconnect={handleDisconnect}
        send={send}
      />

      <div className="flex flex-1 items-center justify-center overflow-hidden">
        <canvas
          ref={canvasRef}
          tabIndex={0}
          autoFocus
          className="max-h-full max-w-full outline-none"
          style={{
            aspectRatio: `${remoteResolution[0]} / ${remoteResolution[1]}`,
          }}
        />
      </div>

      <StatusBar />
    </div>
  );
}
