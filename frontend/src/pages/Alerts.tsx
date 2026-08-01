import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Button, Empty, Loading, PageHeader, Panel, Select } from '../components/ui';

type Alert = {
  id: number;
  stock_id?: number;
  alert_type: string;
  condition: Record<string, unknown>;
  channel: string;
  is_active: boolean;
};

const TYPES = ['RSI Cross', 'MACD Cross', 'Price Breakout', 'Support Break', 'Resistance Break', 'Volume Spike'];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stocks, setStocks] = useState<Array<{ id: number; symbol: string }>>([]);
  const [notes, setNotes] = useState<Array<{ id: number; message: string; is_read: boolean }>>([]);
  const [form, setForm] = useState({ stock_id: '', alert_type: TYPES[0], channel: 'browser' });
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [a, s, n] = await Promise.all([
        api<Alert[]>('/api/alerts'),
        api<Array<{ id: number; symbol: string }>>('/api/stocks'),
        api<Array<{ id: number; message: string; is_read: boolean }>>('/api/alerts/notifications'),
      ]);
      setAlerts(a);
      setStocks(s);
      setNotes(n);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    await api('/api/alerts', {
      method: 'POST',
      body: JSON.stringify({
        stock_id: form.stock_id ? Number(form.stock_id) : null,
        alert_type: form.alert_type,
        channel: form.channel,
        condition: {},
      }),
    });
    load();
  };

  const remove = async (id: number) => {
    await api(`/api/alerts/${id}`, { method: 'DELETE' });
    load();
  };

  if (loading) return <Loading />;

  return (
    <div>
      <PageHeader title="Alerts" subtitle="Browser and email alert rules for RSI, MACD, breakouts, and volume" />
      <Panel className="mb-4">
        <div className="flex flex-wrap gap-2 items-end">
          <div>
            <label className="text-xs">Stock</label>
            <Select value={form.stock_id} onChange={(e) => setForm({ ...form, stock_id: e.target.value })} className="w-48">
              <option value="">Any / market</option>
              {stocks.map((s) => <option key={s.id} value={s.id}>{s.symbol}</option>)}
            </Select>
          </div>
          <div>
            <label className="text-xs">Type</label>
            <Select value={form.alert_type} onChange={(e) => setForm({ ...form, alert_type: e.target.value })}>
              {TYPES.map((t) => <option key={t}>{t}</option>)}
            </Select>
          </div>
          <div>
            <label className="text-xs">Channel</label>
            <Select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}>
              <option value="browser">Browser</option>
              <option value="email">Email</option>
            </Select>
          </div>
          <Button onClick={create}>Create alert</Button>
        </div>
      </Panel>

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel>
          <h3 className="font-semibold mb-3">Active rules</h3>
          {alerts.length === 0 ? <Empty text="No alerts configured" /> : (
            <ul className="space-y-2 text-sm">
              {alerts.map((a) => (
                <li key={a.id} className="flex justify-between items-center border-b border-[var(--color-line)] pb-2">
                  <div>
                    <div className="font-medium">{a.alert_type}</div>
                    <div className="text-xs text-[var(--color-ink-muted)]">Stock {a.stock_id ?? '—'} · {a.channel}</div>
                  </div>
                  <Button variant="ghost" onClick={() => remove(a.id)}>Delete</Button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">Notifications</h3>
          {notes.length === 0 ? <Empty text="No notifications yet" /> : (
            <ul className="space-y-2 text-sm">
              {notes.map((n) => (
                <li key={n.id} className="border-b border-[var(--color-line)] pb-2">{n.message}</li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
