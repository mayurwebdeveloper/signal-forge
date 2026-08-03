import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { api } from '../lib/api';
import { Button, Input, Loading, PageHeader, Panel } from '../components/ui';
import { useAuth } from '../context/AuthContext';

type Settings = {
  suggestions_enabled: boolean;
  suggestions_min_count: number;
  suggestions_max_count: number;
  suggestions_min_bullish_pct: number;
};

export default function AdminPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [u, j, l, s] = await Promise.all([
        api<any[]>('/api/admin/users'),
        api<any[]>('/api/admin/jobs'),
        api<any[]>('/api/admin/logs'),
        api<Settings>('/api/admin/settings'),
      ]);
      setUsers(u);
      setJobs(j);
      setLogs(l);
      setSettings(s);
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

  const regenerate = async () => {
    setMsg('Regenerating daily suggestions…');
    try {
      const res = await api<{ message: string }>('/api/admin/suggestions/regenerate', { method: 'POST' });
      setMsg(res.message);
      load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed');
    }
  };

  const saveSettings = async () => {
    if (!settings) return;
    setSaving(true);
    setMsg('');
    try {
      const res = await api<Settings>('/api/admin/settings', {
        method: 'PUT',
        body: JSON.stringify(settings),
      });
      setSettings(res);
      setMsg('System settings saved');
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed to save settings');
    } finally {
      setSaving(false);
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
        subtitle="Users, scheduler jobs, audit logs, system options, and data refresh"
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={refresh}>Refresh data</Button>
            <Button variant="ghost" onClick={pipeline}>Run pipeline</Button>
            <Button variant="ghost" onClick={regenerate}>Regenerate suggestions</Button>
          </div>
        }
      />
      {msg && <p className="mb-4 text-sm text-[var(--color-ink-muted)]">{msg}</p>}

      {settings && (
        <Panel className="mb-4">
          <h3 className="font-semibold mb-1">System options — daily suggestions</h3>
          <p className="text-xs text-[var(--color-ink-muted)] mb-3">
            Controls the ranked next-session stock list shown on Dashboard, Stocks, and Suggestions.
          </p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <label className="flex items-center gap-2 text-sm mt-6">
              <input
                type="checkbox"
                checked={settings.suggestions_enabled}
                onChange={(e) => setSettings({ ...settings, suggestions_enabled: e.target.checked })}
              />
              Enable daily suggestions
            </label>
            <div>
              <label className="text-xs">Min stocks / day</label>
              <Input
                type="number"
                min={5}
                max={50}
                value={settings.suggestions_min_count}
                onChange={(e) => setSettings({ ...settings, suggestions_min_count: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs">Max stocks / day</label>
              <Input
                type="number"
                min={10}
                max={100}
                value={settings.suggestions_max_count}
                onChange={(e) => setSettings({ ...settings, suggestions_max_count: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs">Min next-day score preference</label>
              <Input
                type="number"
                min={0}
                max={100}
                value={settings.suggestions_min_bullish_pct}
                onChange={(e) => setSettings({ ...settings, suggestions_min_bullish_pct: Number(e.target.value) })}
              />
            </div>
          </div>
          <div className="mt-3">
            <Button onClick={saveSettings} disabled={saving}>{saving ? 'Saving…' : 'Save settings'}</Button>
          </div>
        </Panel>
      )}

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
