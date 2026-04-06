import { Routes, Route, Navigate } from 'react-router-dom';
import { useSessionStore } from './stores/sessionStore';
import { LoginPage } from './components/LoginPage';
import { Dashboard } from './components/Dashboard';
import { RemoteScreen } from './components/RemoteScreen';

function AuthGuard({ children }: { children: React.ReactNode }) {
  const token = useSessionStore((s) => s.token);
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <AuthGuard>
            <Dashboard />
          </AuthGuard>
        }
      />
      <Route
        path="/session/:agentId"
        element={
          <AuthGuard>
            <RemoteScreen />
          </AuthGuard>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
