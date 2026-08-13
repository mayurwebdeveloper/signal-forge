import { useEffect, useState } from 'react';
import { API_BASE, api, getAccessToken } from '../lib/api';
import { Button, Empty, Loading, PageHeader, Panel, Select } from '../components/ui';

export default function ReportsPage() {
  const [stocks, setStocks] = useState<Array<{ id: number; symbol: string }>>([]);
  const [portfolios, setPortfolios] = useState<Array<{ id: number; name: string }>>([]);
  const [backtests, setBacktests] = useState<Array<{ id: number; strategy: string }>>([]);
  const [reports, setReports] = useState<Array<{ id: number; title: string; report_type: string; format: string; created_at: string }>>([]);
  const [form, setForm] = useState({ report_type: 'stock_analysis', stock_id: '', portfolio_id: '', backtest_id: '', format: 'pdf' });
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [s, p, b, r] = await Promise.all([
        api<Array<{ id: number; symbol: string }>>('/api/stocks'),
        api<Array<{ id: number; name: string }>>('/api/portfolios'),
        api<Array<{ id: number; strategy: string }>>('/api/backtests'),
        api<Array<{ id: number; title: string; report_type: string; format: string; created_at: string }>>('/api/reports'),
      ]);
      setStocks(s);
      setPortfolios(p);
      setBacktests(b);
      setReports(r);
      if (s[0]) setForm((f) => ({ ...f, stock_id: String(s[0].id) }));
      if (p[0]) setForm((f) => ({ ...f, portfolio_id: String(p[0].id) }));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const generate = async () => {
    setMsg('');
    try {
      const body: Record<string, unknown> = {
        report_type: form.report_type,
        format: form.format,
      };
      if (form.report_type === 'stock_analysis') body.stock_id = Number(form.stock_id);
      if (form.report_type === 'portfolio') body.portfolio_id = Number(form.portfolio_id);
      if (form.report_type === 'strategy') body.backtest_id = Number(form.backtest_id);
      const res = await api<{ id: number; title: string }>('/api/reports', { method: 'POST', body: JSON.stringify(body) });
      setMsg(`Created: ${res.title}`);
      load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed');
    }
  };

  const download = async (id: number) => {
    const token = getAccessToken();
    const res = await fetch(`${API_BASE}/api/reports/${id}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Download failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report-${id}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <Loading />;

  return (
    <div>
      <PageHeader title="Reports" subtitle="Generate PDF/Excel stock, portfolio, strategy, and performance reports" />
      <Panel className="mb-4">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-xs">Type</label>
            <Select value={form.report_type} onChange={(e) => setForm({ ...form, report_type: e.target.value })}>
              <option value="stock_analysis">Stock analysis</option>
              <option value="portfolio">Portfolio</option>
              <option value="strategy">Strategy</option>
              <option value="performance">Performance</option>
            </Select>
          </div>
          {form.report_type === 'stock_analysis' && (
            <div>
              <label className="text-xs">Stock</label>
              <Select value={form.stock_id} onChange={(e) => setForm({ ...form, stock_id: e.target.value })}>
                {stocks.map((s) => <option key={s.id} value={s.id}>{s.symbol}</option>)}
              </Select>
            </div>
          )}
          {form.report_type === 'portfolio' && (
            <div>
              <label className="text-xs">Portfolio</label>
              <Select value={form.portfolio_id} onChange={(e) => setForm({ ...form, portfolio_id: e.target.value })}>
                {portfolios.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </Select>
            </div>
          )}
          {form.report_type === 'strategy' && (
            <div>
              <label className="text-xs">Backtest</label>
              <Select value={form.backtest_id} onChange={(e) => setForm({ ...form, backtest_id: e.target.value })}>
                {backtests.map((b) => <option key={b.id} value={b.id}>#{b.id} {b.strategy}</option>)}
              </Select>
            </div>
          )}
          <div>
            <label className="text-xs">Format</label>
            <Select value={form.format} onChange={(e) => setForm({ ...form, format: e.target.value })}>
              <option value="pdf">PDF</option>
              <option value="excel">Excel</option>
            </Select>
          </div>
        </div>
        <div className="mt-3"><Button onClick={generate}>Generate</Button></div>
        {msg && <p className="text-sm mt-2 text-[var(--color-ink-muted)]">{msg}</p>}
      </Panel>

      <Panel>
        <h3 className="font-semibold mb-3">Generated reports</h3>
        {reports.length === 0 ? <Empty text="No reports yet" /> : (
          <ul className="space-y-2 text-sm">
            {reports.map((r) => (
              <li key={r.id} className="flex justify-between items-center border-b border-[var(--color-line)] pb-2">
                <div>
                  <div className="font-medium">{r.title}</div>
                  <div className="text-xs text-[var(--color-ink-muted)]">{r.report_type} · {r.format} · {new Date(r.created_at).toLocaleString()}</div>
                </div>
                <Button variant="ghost" onClick={() => download(r.id)}>Download</Button>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
