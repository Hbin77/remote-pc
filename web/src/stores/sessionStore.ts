import { create } from 'zustand';
import type { AgentInfo } from '../utils/protocol';

interface SessionState {
  token: string | null;
  refreshToken: string | null;
  agentId: string | null;
  agents: AgentInfo[];
  isConnected: boolean;
  fps: number;
  quality: number;
  latency: number;
  remoteResolution: [number, number];

  login: (token: string, refreshToken: string) => void;
  logout: () => void;
  setAgentId: (agentId: string | null) => void;
  setAgents: (agents: AgentInfo[]) => void;
  setConnected: (connected: boolean) => void;
  updateStats: (stats: Partial<{ fps: number; quality: number; latency: number }>) => void;
  setRemoteResolution: (w: number, h: number) => void;
}

function loadTokens(): { token: string | null; refreshToken: string | null } {
  try {
    return {
      token: localStorage.getItem('rg_token'),
      refreshToken: localStorage.getItem('rg_refresh_token'),
    };
  } catch {
    return { token: null, refreshToken: null };
  }
}

export const useSessionStore = create<SessionState>((set) => {
  const persisted = loadTokens();

  return {
    token: persisted.token,
    refreshToken: persisted.refreshToken,
    agentId: null,
    agents: [],
    isConnected: false,
    fps: 0,
    quality: 50,
    latency: 0,
    remoteResolution: [1920, 1080],

    login: (token, refreshToken) => {
      localStorage.setItem('rg_token', token);
      localStorage.setItem('rg_refresh_token', refreshToken);
      set({ token, refreshToken });
    },

    logout: () => {
      localStorage.removeItem('rg_token');
      localStorage.removeItem('rg_refresh_token');
      set({ token: null, refreshToken: null, agentId: null, agents: [], isConnected: false });
    },

    setAgentId: (agentId) => set({ agentId }),
    setAgents: (agents) => set({ agents }),
    setConnected: (isConnected) => set({ isConnected }),

    updateStats: (stats) =>
      set((state) => ({
        fps: stats.fps ?? state.fps,
        quality: stats.quality ?? state.quality,
        latency: stats.latency ?? state.latency,
      })),

    setRemoteResolution: (w, h) => set({ remoteResolution: [w, h] }),
  };
});
