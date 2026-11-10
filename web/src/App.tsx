import { useState } from 'react';
import { ToastProvider } from './components/ui';
import { AdminApp } from './pages/AdminApp';
import { RolePage } from './pages/RolePage';
import { UserApp } from './pages/UserApp';
import type { Role } from './types';

export default function App() {
  const [role, setRole] = useState<Role | null>(null);
  return (
    <ToastProvider>
      {role === null ? <RolePage onPick={setRole} /> : null}
      {role === 'user' ? <UserApp onExit={() => setRole(null)} /> : null}
      {role === 'admin' ? <AdminApp onExit={() => setRole(null)} /> : null}
    </ToastProvider>
  );
}
