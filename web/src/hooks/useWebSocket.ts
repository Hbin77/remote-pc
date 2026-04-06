import { useEffect, useRef, useCallback, useState } from 'react';
import { parseFrame, type FrameData, type ProtocolMsg } from '../utils/protocol';

interface UseWebSocketOptions {
  url: string;
  token: string;
  onFrame: (frame: FrameData) => void;
  onMessage: (msg: Record<string, unknown>) => void;
  enabled?: boolean;
}

interface UseWebSocketReturn {
  send: (data: string | ProtocolMsg | Record<string, unknown>) => void;
  disconnect: () => void;
  isConnected: boolean;
  wsRef: React.RefObject<WebSocket | null>;
}

export function useWebSocket({
  url,
  token,
  onFrame,
  onMessage,
  enabled = true,
}: UseWebSocketOptions): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectDelay = useRef(1000);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalClose = useRef(false);
  const onFrameRef = useRef(onFrame);
  const onMessageRef = useRef(onMessage);

  onFrameRef.current = onFrame;
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (!enabled || !token) return;

    try {
      const ws = new WebSocket(url);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectDelay.current = 1000;
        ws.send(JSON.stringify({ type: 'auth', token }));
      };

      ws.onmessage = (event: MessageEvent) => {
        if (event.data instanceof ArrayBuffer) {
          const frame = parseFrame(event.data);
          onFrameRef.current(frame);
        } else if (typeof event.data === 'string') {
          try {
            const msg = JSON.parse(event.data) as Record<string, unknown>;
            onMessageRef.current(msg);
          } catch {
            // ignore malformed messages
          }
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        wsRef.current = null;

        if (!intentionalClose.current && enabled) {
          reconnectTimer.current = setTimeout(() => {
            reconnectDelay.current = Math.min(reconnectDelay.current * 2, 10000);
            connect();
          }, reconnectDelay.current);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // connection failed, will retry via onclose
    }
  }, [url, token, enabled]);

  useEffect(() => {
    intentionalClose.current = false;
    connect();

    return () => {
      intentionalClose.current = true;
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const send = useCallback((data: string | ProtocolMsg | Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const payload = typeof data === 'string' ? data : JSON.stringify(data);
      wsRef.current.send(payload);
    }
  }, []);

  const disconnect = useCallback(() => {
    intentionalClose.current = true;
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  return { send, disconnect, isConnected, wsRef };
}
