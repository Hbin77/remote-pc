import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSessionStore } from '../stores/sessionStore';
import { useWebSocket } from '../hooks/useWebSocket';
import type { AgentInfo } from '../utils/protocol';

export function Dashboard() {
  const token = useSessionStore((s) => s.token);
  const agents = useSessionStore((s) => s.agents);
  const setAgents = useSessionStore((s) => s.setAgents);
  const logout = useSessionStore((s) => s.logout);
  const navigate = useNavigate();

  const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/client`;

  const { isConnected } = useWebSocket({
    url: wsUrl,
    token: token ?? '',
    onFrame: () => {},
    onMessage: (msg) => {
      if (msg.type === 'agent_list') {
        setAgents(msg.agents as AgentInfo[]);
      } else if (msg.type === 'agent_status') {
        const info = msg as unknown as AgentInfo & { type: string };
        useSessionStore.setState((state) => ({
          agents: state.agents.map((a) =>
            a.agent_id === info.agent_id ? { ...a, status: info.status, resolution: info.resolution } : a,
          ),
        }));
      }
    },
    enabled: !!token,
  });

  useEffect(() => {
    if (!token) {
      navigate('/login', { replace: true });
    }
  }, [token, navigate]);

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  function handleAgentClick(agent: AgentInfo) {
    if (agent.status === 'online') {
      navigate(`/session/${agent.agent_id}`);
    }
  }

  return (
    <div className="min-h-screen px-4 py-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">RemoteGate</h1>
            <p className="text-sm text-gray-400">
              {isConnected ? (
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-green-500" />
                  Connected
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-red-500" />
                  Disconnected
                </span>
              )}
            </p>
          </div>
          <button
            onClick={handleLogout}
            className="rounded-lg border border-gray-700 px-4 py-2 text-sm text-gray-300 transition hover:bg-gray-800"
          >
            Logout
          </button>
        </div>

        {agents.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-gray-800 bg-gray-900 py-20">
            <div className="mb-3 text-4xl text-gray-600">&#x1F5A5;</div>
            <p className="text-lg font-medium text-gray-400">No agents connected</p>
            <p className="mt-1 text-sm text-gray-500">
              Start the RemoteGate Agent on your Windows PC to see it here.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => (
              <button
                key={agent.agent_id}
                onClick={() => handleAgentClick(agent)}
                disabled={agent.status !== 'online'}
                className="group rounded-xl border border-gray-800 bg-gray-900 p-5 text-left transition hover:border-gray-600 hover:bg-gray-800/80 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-lg font-semibold text-white">{agent.hostname}</span>
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      agent.status === 'online'
                        ? 'bg-green-900/50 text-green-400'
                        : 'bg-gray-800 text-gray-500'
                    }`}
                  >
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${
                        agent.status === 'online' ? 'bg-green-400' : 'bg-gray-500'
                      }`}
                    />
                    {agent.status}
                  </span>
                </div>
                <div className="space-y-1 text-sm text-gray-400">
                  <p>ID: {agent.agent_id}</p>
                  <p>
                    Resolution: {agent.resolution[0]}x{agent.resolution[1]}
                  </p>
                </div>
                {agent.status === 'online' && (
                  <p className="mt-3 text-xs text-blue-400 opacity-0 transition group-hover:opacity-100">
                    Click to connect
                  </p>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
