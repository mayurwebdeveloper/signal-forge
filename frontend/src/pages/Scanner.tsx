import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Button, Empty, Input, Loading, PageHeader, Panel, Select, money, pct } from '../components/ui';

type Row = {
  stock_id: number;
  symbol: string;
  company_name: string;
  sector?: string;
  price: number;
  change_pct: number;
  volume: number;
  rsi?: number;
  breakout?: boolean;
  near_support?: boolean;
  near_resistance?: boolean;
  golden_cross?: boolean;
};

export default function ScannerPage() {
  const [filters, setFilters] = useState({
    min_rsi: '',
    max_rsi: '',
    sector: '',
    macd_signal: '',
    breakout: false,
    near_support: false,
    near_resistance: false,
    golden_cross: false,
    near_52w_high: false,
    limit: 50,
  });
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const scan = async () => {
    setBusy(true);
    setError('');
    try {
      const body: Record<string, unknown> = { limit: filters.limit };
      if (filters.min_rsi) body.min_rsi = Number(filters.min_rsi);
      if (filters.max_rsi) body.max_rsi = Number(filters.max_rsi);
      if (filters.sector) body.sector = filters.sector;
      if (filters.macd_signal) body.macd_signal = filters.macd_signal;
      if (filters.breakout) body.breakout = true;
      if (filters.near_support) body.near_support = true;
      if (filters.near_resistance) body.near_resistance = true;
      if (filters.golden_cross) body.golden_cross = true;
      if (filters.near_52w_high) body.near_52w_high = true;
      const res = await api<{ results: Row[]; count: number }>('/api/scanner/scan', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setRows(res.results);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Scan failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader title="Stock scanner" subtitle="Filter by RSI, MACD, breakouts, crosses, and proximity to S/R" />
      <Panel className="mb-4">
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-xs">Min RSI</label>
            <Input value={filters.min_rsi} onChange={(e) => setFilters({ ...filters, min_rsi: e.target.value })} />
          </div>
          <div>
            <label className="text-xs">Max RSI</label>
            <Input value={filters.max_rsi} onChange={(e) => setFilters({ ...filters, max_rsi: e.target.value })} />
          </div>
          <div>
            <label className="text-xs">Sector</label>
            <Input value={filters.sector} onChange={(e) => setFilters({ ...filters, sector: e.target.value })} placeholder="Technology" />
          </div>
          <div>
            <label className="text-xs">MACD</label>
            <Select value={filters.macd_signal} onChange={(e) => setFilters({ ...filters, macd_signal: e.target.value })}>
              <option value="">Any</option>
              <option value="bullish">Bullish</option>
              <option value="bearish">Bearish</option>
            </Select>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-sm">
          {([
            ['breakout', 'Breakout'],
            ['near_support', 'Near support'],
            ['near_resistance', 'Near resistance'],
            ['golden_cross', 'Golden cross'],
            ['near_52w_high', 'Near 52w high'],
          ] as const).map(([key, label]) => (
            <label key={key} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={filters[key] as boolean}
                onChange={(e) => setFilters({ ...filters, [key]: e.target.checked })}
              />
              {label}
            </label>
          ))}
        </div>
        <div className="mt-4">
          <Button onClick={scan} disabled={busy}>{busy ? 'Scanning…' : 'Run scanner'}</Button>
        </div>
        {error && <p className="text-sm text-[var(--color-loss)] mt-2">{error}</p>}
      </Panel>

      {busy ? <Loading /> : rows.length === 0 ? <Empty text="Run a scan to see matches" /> : (
        <Panel className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--color-ink-muted)]">
                <th className="pb-2">Symbol</th>
                <th className="pb-2">Price</th>
                <th className="pb-2">Change</th>
                <th className="pb-2">RSI</th>
                <th className="pb-2">Flags</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.stock_id} className="border-t border-[var(--color-line)]">
                  <td className="py-2">
                    <Link to={`/stocks/${r.stock_id}`} className="font-semibold hover:text-teal-700">{r.symbol}</Link>
                    <div className="text-xs text-[var(--color-ink-muted)]">{r.sector}</div>
                  </td>
                  <td>{money(r.price)}</td>
                  <td className={r.change_pct >= 0 ? 'gain' : 'loss'}>{pct(r.change_pct)}</td>
                  <td>{r.rsi ?? '—'}</td>
                  <td className="text-xs">
                    {[r.breakout && 'Breakout', r.near_support && 'Support', r.near_resistance && 'Resistance', r.golden_cross && 'Golden']
                      .filter(Boolean)
                      .join(' · ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}
