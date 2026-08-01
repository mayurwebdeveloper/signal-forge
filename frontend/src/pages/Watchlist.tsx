import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Button, Empty, Loading, PageHeader, Panel, Select } from '../components/ui';

type Stock = { id: number; symbol: string; company_name: string };
type Watchlist = {
  id: number;
  name: string;
  items: Array<{ id: number; stock_id: number; stock?: Stock; notes?: string }>;
};

export default function WatchlistPage() {
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [stockId, setStockId] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [w, s] = await Promise.all([
        api<Watchlist[]>('/api/watchlists'),
        api<Stock[]>('/api/stocks'),
      ]);
      setLists(w);
      setStocks(s);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const wl = lists[0];

  const add = async () => {
    if (!wl || !stockId) return;
    await api(`/api/watchlists/${wl.id}/items`, {
      method: 'POST',
      body: JSON.stringify({ stock_id: Number(stockId) }),
    });
    setStockId('');
    load();
  };

  const remove = async (itemId: number) => {
    if (!wl) return;
    await api(`/api/watchlists/${wl.id}/items/${itemId}`, { method: 'DELETE' });
    load();
  };

  if (loading) return <Loading />;

  return (
    <div>
      <PageHeader title="Watchlist" subtitle="Track favorites and surface them on the dashboard" />
      <Panel className="mb-4">
        <div className="flex flex-wrap gap-2 items-end">
          <div className="min-w-[220px]">
            <label className="text-xs">Add stock</label>
            <Select value={stockId} onChange={(e) => setStockId(e.target.value)}>
              <option value="">Select…</option>
              {stocks.map((s) => (
                <option key={s.id} value={s.id}>{s.symbol} — {s.company_name}</option>
              ))}
            </Select>
          </div>
          <Button onClick={add} disabled={!stockId}>Add</Button>
        </div>
      </Panel>

      {!wl || wl.items.length === 0 ? (
        <Empty text="Your watchlist is empty" />
      ) : (
        <Panel>
          <ul className="divide-y divide-[var(--color-line)]">
            {wl.items.map((item) => (
              <li key={item.id} className="py-3 flex items-center justify-between gap-3">
                <div>
                  <Link to={`/stocks/${item.stock_id}`} className="font-semibold hover:text-teal-700">
                    {item.stock?.symbol || item.stock_id}
                  </Link>
                  <div className="text-xs text-[var(--color-ink-muted)]">{item.stock?.company_name}</div>
                </div>
                <Button variant="ghost" onClick={() => remove(item.id)}>Remove</Button>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}
