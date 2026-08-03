import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { Badge, Button, Empty, Input, Loading, PageHeader, Panel, money, pct } from '../components/ui';

type Stock = {
  id: number;
  symbol: string;
  company_name: string;
  exchange: string;
  sector?: string;
  market_cap?: number;
};

type LookupItem = {
  symbol: string;
  company_name: string;
  exchange?: string;
  quote_type?: string;
  already_tracked: boolean;
  stock_id?: number | null;
};

type Suggestion = {
  stock_id: number;
  symbol: string;
  company_name: string;
  sector?: string;
  next_day_probability: number;
  expected_direction: string;
  confidence: string;
  risk: string;
  price?: number;
  change_pct?: number;
  reasons?: string[];
  rank: number;
};

export default function StocksPage() {
  const navigate = useNavigate();
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [lookupQ, setLookupQ] = useState('');
  const [lookupResults, setLookupResults] = useState<LookupItem[]>([]);
  const [looking, setLooking] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [msg, setMsg] = useState('');
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestionsEnabled, setSuggestionsEnabled] = useState(true);

  const load = (query = q) => {
    setLoading(true);
    const qs = query ? `?q=${encodeURIComponent(query)}` : '';
    api<Stock[]>(`/api/stocks${qs}`)
      .then(setStocks)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    api<{ enabled: boolean; suggestions: Suggestion[] }>('/api/suggestions/daily')
      .then((res) => {
        setSuggestionsEnabled(res.enabled);
        setSuggestions(res.suggestions || []);
      })
      .catch(() => undefined);
  }, []);

  const searchLocal = (e?: FormEvent) => {
    e?.preventDefault();
    load(q);
  };

  const searchYahoo = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!lookupQ.trim()) return;
    setLooking(true);
    setMsg('');
    setLookupResults([]);
    try {
      const res = await api<{ results: LookupItem[] }>(`/api/stocks/lookup?q=${encodeURIComponent(lookupQ.trim())}`);
      setLookupResults(res.results || []);
      if (!(res.results || []).length) {
        setMsg('No matches. Try NSE tickers with .NS (e.g. INFY.NS) or US tickers like AAPL.');
      }
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Lookup failed');
    } finally {
      setLooking(false);
    }
  };

  const addSymbol = async (item: LookupItem) => {
    if (item.already_tracked && item.stock_id) {
      navigate(`/stocks/${item.stock_id}`);
      return;
    }
    setAdding(item.symbol);
    setMsg(`Adding ${item.symbol} and downloading history…`);
    try {
      const stock = await api<Stock>('/api/stocks', {
        method: 'POST',
        body: JSON.stringify({
          symbol: item.symbol,
          company_name: item.company_name,
          exchange: item.exchange || 'NSE',
        }),
      });
      setMsg(`${stock.symbol} added`);
      load();
      navigate(`/stocks/${stock.id}`);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : 'Failed to add');
    } finally {
      setAdding(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Stock universe"
        subtitle="Search your tracked list, or look up any Yahoo Finance symbol and add it"
        action={
          <form onSubmit={searchLocal} className="flex gap-2">
            <Input placeholder="Filter tracked…" value={q} onChange={(e) => setQ(e.target.value)} className="w-48" />
            <Button type="submit">Filter</Button>
          </form>
        }
      />

      {suggestionsEnabled && suggestions.length > 0 && (
        <Panel className="mb-4">
          <div className="flex flex-wrap items-end justify-between gap-2 mb-3">
            <div>
              <h3 className="font-semibold">Suggested for you today</h3>
              <p className="text-xs text-[var(--color-ink-muted)]">
                Not sure where to start? These {suggestions.length} ranked next-session setups are highlighted from analytics.
              </p>
            </div>
            <Link to="/suggestions" className="text-sm text-teal-800 hover:underline">
              Full suggestions list
            </Link>
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestions.slice(0, 12).map((s) => (
              <Link
                key={s.stock_id}
                to={`/stocks/${s.stock_id}`}
                className="rounded-md border border-[var(--color-line)] px-3 py-2 text-sm hover:border-teal-600 min-w-[140px]"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">#{s.rank} {s.symbol}</span>
                  <Badge tone={s.expected_direction === 'Bullish' ? 'bull' : s.expected_direction === 'Bearish' ? 'bear' : 'neutral'}>
                    {s.next_day_probability}%
                  </Badge>
                </div>
                <div className="text-xs text-[var(--color-ink-muted)] mt-0.5">
                  {s.price != null ? money(s.price) : ''} {s.change_pct != null ? pct(s.change_pct) : ''}
                </div>
              </Link>
            ))}
          </div>
        </Panel>
      )}

      <Panel className="mb-4">
        <h3 className="font-semibold mb-1">Find & add any share</h3>
        <p className="text-xs text-[var(--color-ink-muted)] mb-3">
          Search by company or ticker. NSE examples: <code>INFY.NS</code>, <code>SBIN.NS</code> · US: <code>AAPL</code>, <code>TSLA</code> · BSE: <code>500325.BO</code>
        </p>
        <form onSubmit={searchYahoo} className="flex flex-wrap gap-2">
          <Input
            placeholder="e.g. Adani, TSLA, HDFC…"
            value={lookupQ}
            onChange={(e) => setLookupQ(e.target.value)}
            className="min-w-[240px] flex-1"
          />
          <Button type="submit" disabled={looking || !lookupQ.trim()}>
            {looking ? 'Searching…' : 'Search markets'}
          </Button>
        </form>
        {msg && <p className="text-sm mt-2 text-[var(--color-ink-muted)]">{msg}</p>}

        {lookupResults.length > 0 && (
          <ul className="mt-4 divide-y divide-[var(--color-line)]">
            {lookupResults.map((item) => (
              <li key={item.symbol} className="py-2.5 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-semibold">{item.symbol}</div>
                  <div className="text-xs text-[var(--color-ink-muted)]">
                    {item.company_name}
                    {item.exchange ? ` · ${item.exchange}` : ''}
                    {item.quote_type ? ` · ${item.quote_type}` : ''}
                  </div>
                </div>
                <Button
                  onClick={() => addSymbol(item)}
                  disabled={adding === item.symbol}
                  variant={item.already_tracked ? 'ghost' : 'primary'}
                >
                  {item.already_tracked ? 'Open' : adding === item.symbol ? 'Adding…' : 'Add & download'}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <h3 className="font-semibold mb-2">Tracked stocks</h3>
      {loading ? (
        <Loading />
      ) : stocks.length === 0 ? (
        <Empty text="No tracked stocks match. Use Find & add above to pull any Yahoo symbol." />
      ) : (
        <Panel className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--color-ink-muted)]">
                <th className="pb-2">Symbol</th>
                <th className="pb-2">Company</th>
                <th className="pb-2">Exchange</th>
                <th className="pb-2">Sector</th>
                <th className="pb-2 text-right">Market cap</th>
              </tr>
            </thead>
            <tbody>
              {stocks.map((s) => (
                <tr key={s.id} className="border-t border-[var(--color-line)]">
                  <td className="py-2.5">
                    <Link className="font-semibold text-teal-800 hover:underline" to={`/stocks/${s.id}`}>{s.symbol}</Link>
                  </td>
                  <td>{s.company_name}</td>
                  <td>{s.exchange}</td>
                  <td>{s.sector || '—'}</td>
                  <td className="text-right">{s.market_cap ? money(s.market_cap, 0) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}
