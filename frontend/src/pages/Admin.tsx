import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { api } from '../lib/api';
import { Button, Loading, PageHeader, Panel } from '../components/ui';
import { useAuth } from '../context/AuthContext';

export default function AdminPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [u, j, l] = await Promise.all([
        api<any[]>('/api/admin/users'),
        api<any[]>('/api/admin/jobs'),
        api<any[]>('/api/admin/logs'),
      ]);
      setUsers(u);
      setJobs(j);
      setLogs(l);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.is_admin) load();
  }, [user?.is_admin]);

  if (!user?.is_admin) return <Navigate to="/" replace />;
  if (loading) return <Loading />;

  const refresh = async () => {
    setMsg('Refreshing market data — this may take a few minutes…');
    try {
      const res = await api<{ message: string }>('/api/admin/refresh-data', { method: 'POST' });
      setMsg(res.message);
      load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed');
    }
  };

  const pipeline = async () => {
    setMsg('Running daily pipeline…');
    try {
      const res = await api<{ message: string }>('/api/admin/run-pipeline', { method: 'POST' });
      setMsg(res.message);
      load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed');
    }
  };

  const toggle = async (id: number) => {
    await api(`/api/admin/users/${id}/toggle`, { method: 'PATCH' });
    load();
  };

  return (
    <div>
      <PageHeader
        title="Admin"
        subtitle="Users, scheduler jobs, audit logs, and data refresh"
        action={
          <div className="flex gap-2">
            <Button onClick={refresh}>Refresh data</Button>
            <Button variant="ghost" onClick={pipeline}>Run pipeline</Button>
          </div>
        }
      />
      {msg && <p className="mb-4 text-sm text-[var(--color-ink-muted)]">{msg}</p>}

      <div className="grid lg:grid-cols-3 gap-4">
        <Panel>
          <h3 className="font-semibold mb-3">Users</h3>
          <ul className="space-y-2 text-sm max-h-96 overflow-auto">
            {users.map((u) => (
              <li key={u.id} className="flex justify-between gap-2 border-b border-[var(--color-line)] pb-2">
                <div>
                  <div className="font-medium">{u.username}</div>
                  <div className="text-xs text-[var(--color-ink-muted)]">{u.email} {u.is_admin ? '· admin' : ''}</div>
                </div>
                <Button variant="ghost" onClick={() => toggle(u.id)}>{u.is_active ? 'Disable' : 'Enable'}</Button>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">Jobs</h3>
          <ul className="space-y-2 text-sm max-h-96 overflow-auto">
            {jobs.length === 0 && <li className="text-[var(--color-ink-muted)]">No jobs yet</li>}
            {jobs.map((j) => (
              <li key={j.id} className="border-b border-[var(--color-line)] pb-2">
                <div className="font-medium">{j.job_type} · {j.status}</div>
                <div className="text-xs text-[var(--color-ink-muted)]">{j.message}</div>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">Audit logs</h3>
          <ul className="space-y-2 text-sm max-h-96 overflow-auto">
            {logs.map((l) => (
              <li key={l.id} className="border-b border-[var(--color-line)] pb-2">
                <div className="font-medium">{l.action}</div>
                <div className="text-xs text-[var(--color-ink-muted)]">user {l.user_id ?? '—'} · {new Date(l.created_at).toLocaleString()}</div>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
