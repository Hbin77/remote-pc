export interface AuthMsg {
  type: 'auth';
  token: string;
}

export interface MouseMsg {
  type: 'mouse';
  action: 'move' | 'click' | 'double_click' | 'scroll' | 'drag' | 'button_down' | 'button_up';
  x: number;
  y: number;
  button?: 'left' | 'right' | 'middle';
  delta?: number;
}

export interface KeyMsg {
  type: 'key';
  action: 'press' | 'release';
  key: string;
}

export interface SessionMsg {
  type: 'session_start' | 'session_end';
  agent_id?: string;
}

export interface ConfigMsg {
  type: 'config';
  quality?: number;
  fps?: number;
  scale?: number;
}

export interface AgentInfo {
  agent_id: string;
  hostname: string;
  status: 'online' | 'offline';
  resolution: [number, number];
}

export type ProtocolMsg = AuthMsg | MouseMsg | KeyMsg | SessionMsg | ConfigMsg;

export interface FrameData {
  frameNum: number;
  jpegBlob: Blob;
}

export function parseFrame(buffer: ArrayBuffer): FrameData {
  const view = new DataView(buffer);
  // byte 0: message type (0x01 for frame)
  // bytes 1-4: frame number (uint32 big-endian)
  const frameNum = view.getUint32(1, false);
  const jpegData = buffer.slice(5);
  const jpegBlob = new Blob([jpegData], { type: 'image/jpeg' });
  return { frameNum, jpegBlob };
}

export function buildMouseMsg(
  action: MouseMsg['action'],
  x: number,
  y: number,
  button?: MouseMsg['button'],
  delta?: number,
): MouseMsg {
  const msg: MouseMsg = { type: 'mouse', action, x, y };
  if (button !== undefined) msg.button = button;
  if (delta !== undefined) msg.delta = delta;
  return msg;
}

export function buildKeyMsg(action: KeyMsg['action'], key: string): KeyMsg {
  return { type: 'key', action, key };
}

export function buildSessionMsg(msgType: SessionMsg['type'], agentId?: string): SessionMsg {
  const msg: SessionMsg = { type: msgType };
  if (agentId !== undefined) msg.agent_id = agentId;
  return msg;
}

export function buildConfigMsg(quality?: number, fps?: number, scale?: number): ConfigMsg {
  const msg: ConfigMsg = { type: 'config' };
  if (quality !== undefined) msg.quality = quality;
  if (fps !== undefined) msg.fps = fps;
  if (scale !== undefined) msg.scale = scale;
  return msg;
}
