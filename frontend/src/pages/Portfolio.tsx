import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { Button, Empty, Input, Loading, PageHeader, Panel, Select, money, pct } from '../components/ui';

type Portfolio = {
  id: number;
  name: string;
  holdings: Array<{
    id: number;
    stock_id: number;
    quantity: number;
    avg_buy_price: number;
    current_price?: number;
    market_value?: number;
    pnl?: number;
    pnl_pct?: number;
    stock?: { symbol: string; sector?: string };
  }>;
  total_investment: number;
  total_value: number;
  total_pnl: number;
  total_return_pct: number;
  sector_allocation?: Record<string, number>;
};

export default function PortfolioPage() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [stocks, setStocks] = useState<Array<{ id: number; symbol: string }>>([]);
  const [form, setForm] = useState({ stock_id: '', quantity: '', avg_buy_price: '' });
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      let ps = await api<Portfolio[]>('/api/portfolios');
      if (!ps.length) {
        await api('/api/portfolios', { method: 'POST', body: JSON.stringify({ name: 'My Portfolio' }) });
        ps = await api<Portfolio[]>('/api/portfolios');
      }
      setPortfolios(ps);
      setStocks(await api('/api/stocks'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const p = portfolios[0];

  const add = async () => {
    if (!p) return;
    await api(`/api/portfolios/${p.id}/holdings`, {
      method: 'POST',
      body: JSON.stringify({
        stock_id: Number(form.stock_id),
        quantity: Number(form.quantity),
        avg_buy_price: Number(form.avg_buy_price),
      }),
    });
    setForm({ stock_id: '', quantity: '', avg_buy_price: '' });
    load();
  };

  const remove = async (hid: number) => {
    if (!p) return;
    await api(`/api/portfolios/${p.id}/holdings/${hid}`, { method: 'DELETE' });
    load();
  };

  if (loading) return <Loading />;
  if (!p) return <Empty text="Could not create portfolio" />;

  return (
    <div>
      <PageHeader title="Portfolio" subtitle="Manual holdings with live P&L and sector allocation" />
      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
        <Panel><div className="text-xs text-[var(--color-ink-muted)]">Investment</div><div className="text-2xl font-semibold">{money(p.total_investment)}</div></Panel>
        <Panel><div className="text-xs text-[var(--color-ink-muted)]">Value</div><div className="text-2xl font-semibold">{money(p.total_value)}</div></Panel>
        <Panel><div className="text-xs text-[var(--color-ink-muted)]">P&L</div><div className={`text-2xl font-semibold ${p.total_pnl >= 0 ? 'gain' : 'loss'}`}>{money(p.total_pnl)}</div></Panel>
        <Panel><div className="text-xs text-[var(--color-ink-muted)]">Return</div><div className={`text-2xl font-semibold ${p.total_return_pct >= 0 ? 'gain' : 'loss'}`}>{pct(p.total_return_pct)}</div></Panel>
      </div>

      <Panel className="mb-4">
        <h3 className="font-semibold mb-2">Add holding</h3>
        <div className="flex flex-wrap gap-2">
          <Select value={form.stock_id} onChange={(e) => setForm({ ...form, stock_id: e.target.value })} className="w-48">
            <option value="">Stock…</option>
            {stocks.map((s) => <option key={s.id} value={s.id}>{s.symbol}</option>)}
          </Select>
          <Input placeholder="Qty" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} className="w-28" />
          <Input placeholder="Avg buy" value={form.avg_buy_price} onChange={(e) => setForm({ ...form, avg_buy_price: e.target.value })} className="w-32" />
          <Button onClick={add}>Add</Button>
        </div>
      </Panel>

      <div className="grid lg:grid-cols-3 gap-4">
        <Panel className="lg:col-span-2 overflow-x-auto">
          {p.holdings.length === 0 ? <Empty text="No holdings yet" /> : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-[var(--color-ink-muted)]">
                  <th className="pb-2">Symbol</th>
                  <th className="pb-2">Qty</th>
                  <th className="pb-2">Avg</th>
                  <th className="pb-2">Price</th>
                  <th className="pb-2">P&L</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {p.holdings.map((h) => (
                  <tr key={h.id} className="border-t border-[var(--color-line)]">
                    <td className="py-2 font-medium">{h.stock?.symbol}</td>
                    <td>{h.quantity}</td>
                    <td>{money(h.avg_buy_price)}</td>
                    <td>{money(h.current_price)}</td>
                    <td className={(h.pnl || 0) >= 0 ? 'gain' : 'loss'}>{money(h.pnl)} ({pct(h.pnl_pct)})</td>
                    <td><Button variant="ghost" onClick={() => remove(h.id)}>Remove</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">Sector allocation</h3>
          {Object.keys(p.sector_allocation || {}).length === 0 ? <Empty text="No allocation" /> : (
            <ul className="space-y-2 text-sm">
              {Object.entries(p.sector_allocation || {}).map(([k, v]) => (
                <li key={k} className="flex justify-between">
                  <span>{k}</span>
                  <span className="font-medium">{money(v)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
