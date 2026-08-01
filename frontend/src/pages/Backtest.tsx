import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Button, Empty, Input, Loading, PageHeader, Panel, Select, money, pct } from '../components/ui';

export default function BacktestPage() {
  const [stocks, setStocks] = useState<Array<{ id: number; symbol: string }>>([]);
  const [strategies, setStrategies] = useState<Array<{ id: string; name: string }>>([]);
  const [form, setForm] = useState({
    stock_id: '',
    strategy: 'sma_crossover',
    start_date: '2023-01-01',
    end_date: new Date().toISOString().slice(0, 10),
    capital: '100000',
  });
  const [result, setResult] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([
      api<Array<{ id: number; symbol: string }>>('/api/stocks'),
      api<Array<{ id: string; name: string }>>('/api/backtests/strategies'),
      api<any[]>('/api/backtests'),
    ]).then(([s, st, h]) => {
      setStocks(s);
      setStrategies(st);
      setHistory(h);
      if (s[0]) setForm((f) => ({ ...f, stock_id: String(s[0].id) }));
    });
  }, []);

  const run = async () => {
    setBusy(true);
    setError('');
    try {
      const bt = await api<any>('/api/backtests', {
        method: 'POST',
        body: JSON.stringify({
          stock_id: Number(form.stock_id),
          strategy: form.strategy,
          start_date: form.start_date,
          end_date: form.end_date,
          capital: Number(form.capital),
        }),
      });
      setResult(bt);
      setHistory(await api('/api/backtests'));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Backtest failed');
    } finally {
      setBusy(false);
    }
  };

  const r = result?.results;

  return (
    <div>
      <PageHeader title="Backtesting" subtitle="Simulate strategies on historical OHLC data" />
      <Panel className="mb-4">
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div>
            <label className="text-xs">Stock</label>
            <Select value={form.stock_id} onChange={(e) => setForm({ ...form, stock_id: e.target.value })}>
              {stocks.map((s) => <option key={s.id} value={s.id}>{s.symbol}</option>)}
            </Select>
          </div>
          <div>
            <label className="text-xs">Strategy</label>
            <Select value={form.strategy} onChange={(e) => setForm({ ...form, strategy: e.target.value })}>
              {strategies.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </div>
          <div>
            <label className="text-xs">Start</label>
            <Input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          </div>
          <div>
            <label className="text-xs">End</label>
            <Input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
          </div>
          <div>
            <label className="text-xs">Capital</label>
            <Input value={form.capital} onChange={(e) => setForm({ ...form, capital: e.target.value })} />
          </div>
        </div>
        <div className="mt-3">
          <Button onClick={run} disabled={busy || !form.stock_id}>{busy ? 'Running…' : 'Run backtest'}</Button>
        </div>
        {error && <p className="text-sm text-[var(--color-loss)] mt-2">{error}</p>}
      </Panel>

      {busy && <Loading />}

      {r && (
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
          <Panel><div className="text-xs text-[var(--color-ink-muted)]">Net P&L</div><div className={`text-xl font-semibold ${r.net_pnl >= 0 ? 'gain' : 'loss'}`}>{money(r.net_pnl)} ({pct(r.net_pnl_pct)})</div></Panel>
          <Panel><div className="text-xs text-[var(--color-ink-muted)]">Win rate</div><div className="text-xl font-semibold">{r.win_rate}%</div></Panel>
          <Panel><div className="text-xs text-[var(--color-ink-muted)]">Max drawdown</div><div className="text-xl font-semibold loss">{r.maximum_drawdown}%</div></Panel>
          <Panel><div className="text-xs text-[var(--color-ink-muted)]">Sharpe</div><div className="text-xl font-semibold">{r.sharpe_ratio}</div></Panel>
          <Panel><div className="text-xs text-[var(--color-ink-muted)]">Trades</div><div className="text-xl font-semibold">{r.trades_count}</div></Panel>
          <Panel><div className="text-xs text-[var(--color-ink-muted)]">Final equity</div><div className="text-xl font-semibold">{money(r.final_equity)}</div></Panel>
          <Panel><div className="text-xs text-[var(--color-ink-muted)]">Profit</div><div className="text-xl font-semibold gain">{money(r.profit)}</div></Panel>
          <Panel><div className="text-xs text-[var(--color-ink-muted)]">Loss</div><div className="text-xl font-semibold loss">{money(r.loss)}</div></Panel>
        </div>
      )}

      <Panel>
        <h3 className="font-semibold mb-3">Recent backtests</h3>
        {history.length === 0 ? <Empty text="No backtests yet" /> : (
          <ul className="space-y-2 text-sm">
            {history.map((h) => (
              <li key={h.id} className="flex justify-between border-b border-[var(--color-line)] pb-2">
                <span>#{h.id} · {h.strategy} · stock {h.stock_id}</span>
                <span className={(h.results?.net_pnl || 0) >= 0 ? 'gain' : 'loss'}>{money(h.results?.net_pnl)} · WR {h.results?.win_rate}%</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
