/**
 * WebRTC hook for establishing P2P connection with the agent.
 * Uses the existing signaling WebSocket to exchange SDP and ICE candidates.
 */
import { useEffect, useRef, useState, useCallback } from 'react';

interface UseWebRTCOptions {
  signalingWs: React.RefObject<WebSocket | null>;
  agentId: string | null;
  isSignalingConnected: boolean;
  enabled: boolean;
}

interface UseWebRTCReturn {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  sendInput: (msg: unknown) => void;
  isP2PConnected: boolean;
  connectionState: string;
}

const ICE_SERVERS: RTCIceServer[] = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' },
];

export function useWebRTC({
  signalingWs,
  agentId,
  isSignalingConnected,
  enabled,
}: UseWebRTCOptions): UseWebRTCReturn {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dataChannelRef = useRef<RTCDataChannel | null>(null);
  const [isP2PConnected, setIsP2PConnected] = useState(false);
  const [connectionState, setConnectionState] = useState('new');
  const signalingHandlerRef = useRef<((event: MessageEvent) => void) | null>(null);

  const sendInput = useCallback((msg: unknown) => {
    const dc = dataChannelRef.current;
    if (dc && dc.readyState === 'open') {
      dc.send(JSON.stringify(msg));
    }
  }, []);

  // Send signaling message via the existing WebSocket
  const sendSignaling = useCallback(
    (msg: Record<string, unknown>) => {
      const ws = signalingWs.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg));
      }
    },
    [signalingWs],
  );

  useEffect(() => {
    if (!enabled || !isSignalingConnected || !agentId) {
      return;
    }

    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
    pcRef.current = pc;

    // Add transceiver to receive video
    pc.addTransceiver('video', { direction: 'recvonly' });

    // Create DataChannel for input events
    const dc = pc.createDataChannel('input', { ordered: true });
    dataChannelRef.current = dc;

    dc.onopen = () => {
      // DataChannel is ready
    };

    dc.onclose = () => {
      // DataChannel closed
    };

    // Track connection state
    pc.oniceconnectionstatechange = () => {
      const state = pc.iceConnectionState;
      setConnectionState(state);

      if (state === 'connected' || state === 'completed') {
        setIsP2PConnected(true);
      } else if (state === 'disconnected' || state === 'failed' || state === 'closed') {
        setIsP2PConnected(false);
      }
    };

    // On track: attach stream to video element
    pc.ontrack = (event) => {
      if (videoRef.current && event.streams.length > 0) {
        videoRef.current.srcObject = event.streams[0];
      }
    };

    // Collect ICE candidates and send via signaling
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        sendSignaling({
          type: 'ice_candidate',
          candidate: {
            candidate: event.candidate.candidate,
            sdpMid: event.candidate.sdpMid,
            sdpMLineIndex: event.candidate.sdpMLineIndex,
          },
        });
      }
    };

    // Listen for signaling messages from the WS
    const handleSignalingMessage = (event: MessageEvent) => {
      if (typeof event.data !== 'string') return;

      let msg: Record<string, unknown>;
      try {
        msg = JSON.parse(event.data) as Record<string, unknown>;
      } catch {
        return;
      }

      if (msg.type === 'webrtc_answer') {
        const sdp = msg.sdp as string;
        pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp })).catch(
          (err) => console.error('Failed to set remote description:', err),
        );
      } else if (msg.type === 'ice_candidate') {
        const candidateData = msg.candidate as {
          candidate: string;
          sdpMid: string | null;
          sdpMLineIndex: number | null;
        };
        if (candidateData) {
          pc.addIceCandidate(
            new RTCIceCandidate({
              candidate: candidateData.candidate,
              sdpMid: candidateData.sdpMid ?? undefined,
              sdpMLineIndex: candidateData.sdpMLineIndex ?? undefined,
            }),
          ).catch((err) => console.error('Failed to add ICE candidate:', err));
        }
      }
    };

    const ws = signalingWs.current;
    if (ws) {
      ws.addEventListener('message', handleSignalingMessage);
      signalingHandlerRef.current = handleSignalingMessage;
    }

    // Create offer and start negotiation
    pc.createOffer()
      .then((offer) => pc.setLocalDescription(offer))
      .then(() => {
        if (pc.localDescription) {
          sendSignaling({
            type: 'webrtc_offer',
            sdp: pc.localDescription.sdp,
          });
        }
      })
      .catch((err) => {
        console.error('Failed to create WebRTC offer:', err);
      });

    // Handle renegotiation
    pc.onnegotiationneeded = () => {
      // Only renegotiate if we already have a local description (initial offer already sent)
      if (pc.localDescription) {
        pc.createOffer()
          .then((offer) => pc.setLocalDescription(offer))
          .then(() => {
            if (pc.localDescription) {
              sendSignaling({
                type: 'webrtc_offer',
                sdp: pc.localDescription.sdp,
              });
            }
          })
          .catch((err) => console.error('Renegotiation failed:', err));
      }
    };

    return () => {
      // Clean up signaling listener
      if (ws && signalingHandlerRef.current) {
        ws.removeEventListener('message', signalingHandlerRef.current);
        signalingHandlerRef.current = null;
      }

      // Close data channel
      if (dataChannelRef.current) {
        dataChannelRef.current.close();
        dataChannelRef.current = null;
      }

      // Close peer connection and remove tracks
      if (pcRef.current) {
        pcRef.current.getSenders().forEach((sender) => {
          if (sender.track) {
            sender.track.stop();
          }
        });
        pcRef.current.close();
        pcRef.current = null;
      }

      // Clear video source
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }

      setIsP2PConnected(false);
      setConnectionState('closed');
    };
  }, [enabled, isSignalingConnected, agentId, sendSignaling, signalingWs]);

  return { videoRef, sendInput, isP2PConnected, connectionState };
}
