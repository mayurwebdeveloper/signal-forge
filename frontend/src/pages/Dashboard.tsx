import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Badge, Empty, Loading, PageHeader, Panel, Stat, money, pct } from '../components/ui';

type Suggestion = {
  stock_id: number;
  symbol: string;
  company_name: string;
  next_day_probability: number;
  expected_direction: string;
  confidence: string;
  risk: string;
  price?: number;
  change_pct?: number;
  reasons?: string[];
  rank?: number;
};

type Overview = {
  market_overview: { stocks_tracked: number; avg_change_pct: number; bullish_count: number; bearish_count: number };
  top_gainers: Array<{ stock_id: number; symbol: string; company_name: string; price: number; change_pct: number }>;
  top_losers: Array<{ stock_id: number; symbol: string; company_name: string; price: number; change_pct: number }>;
  watchlist: Array<{ stock_id: number; symbol: string; price?: number; change_pct?: number }>;
  todays_signals: Array<{ stock_id: number; symbol: string; expected_direction: string; bullish_probability: number; confidence: string }>;
  ai_recommendations: Array<{ stock_id: number; symbol: string; company_name: string; bullish_probability: number; expected_direction: string; confidence: string; risk: string }>;
  daily_suggestions?: Suggestion[];
  suggestions_enabled?: boolean;
  suggestions_date?: string;
  upcoming_breakouts: Array<{ stock_id: number; symbol: string; change_pct: number; price: number }>;
};

export default function DashboardPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api<Overview>('/api/dashboard/overview')
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-[var(--color-loss)]">{error}</p>;
  if (!data) return <Loading />;

  const m = data.market_overview;
  const picks = data.daily_suggestions || [];

  return (
    <div>
      <PageHeader title="Market pulse" subtitle="Live snapshot across tracked symbols, signals, and AI estimates" />
      <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-6">
        <Stat label="Tracked" value={m.stocks_tracked} />
        <Stat label="Avg change" value={pct(m.avg_change_pct)} tone={m.avg_change_pct >= 0 ? 'gain' : 'loss'} />
        <Stat label="Bullish bias" value={m.bullish_count} tone="gain" />
        <Stat label="Bearish bias" value={m.bearish_count} tone="loss" />
      </div>

      {data.suggestions_enabled !== false && (
        <Panel className="mb-4">
          <div className="flex flex-wrap items-end justify-between gap-2 mb-3">
            <div>
              <h3 className="font-semibold">Today&apos;s suggested stocks</h3>
              <p className="text-xs text-[var(--color-ink-muted)] mt-0.5">
                At least 10 next-session setups{data.suggestions_date ? ` · ${data.suggestions_date}` : ''}
              </p>
            </div>
            <Link to="/suggestions" className="text-sm text-teal-800 hover:underline">
              View all suggestions
            </Link>
          </div>
          {picks.length === 0 ? (
            <Empty text="Suggestions will appear after analysis — open Suggestions or refresh data in Admin" />
          ) : (
            <div className="grid sm:grid-cols-2 xl:grid-cols-5 gap-2">
              {picks.map((s) => (
                <Link
                  key={s.stock_id}
                  to={`/stocks/${s.stock_id}`}
                  className="rounded-lg border border-[var(--color-line)] px-3 py-2.5 hover:border-teal-600 transition"
                >
                  <div className="flex justify-between items-start gap-2">
                    <span className="font-semibold text-sm">{s.symbol}</span>
                    <Badge tone={s.expected_direction === 'Bullish' ? 'bull' : s.expected_direction === 'Bearish' ? 'bear' : 'neutral'}>
                      {s.next_day_probability}%
                    </Badge>
                  </div>
                  <div className="text-xs text-[var(--color-ink-muted)] mt-1 truncate">{s.company_name}</div>
                  <div className={`text-xs mt-1 ${Number(s.change_pct) >= 0 ? 'gain' : 'loss'}`}>
                    {s.price != null ? money(s.price) : ''} {s.change_pct != null ? pct(s.change_pct) : ''}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Panel>
      )}

      <div className="grid lg:grid-cols-2 gap-4 mb-4">
        <Panel>
          <h3 className="font-semibold mb-3">Top gainers</h3>
          <MoverTable rows={data.top_gainers} />
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">Top losers</h3>
          <MoverTable rows={data.top_losers} />
        </Panel>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <Panel>
          <h3 className="font-semibold mb-3">Watchlist</h3>
          {data.watchlist.length === 0 ? (
            <Empty text="Add symbols from the Watchlist page" />
          ) : (
            <ul className="space-y-2">
              {data.watchlist.map((w) => (
                <li key={w.stock_id} className="flex justify-between text-sm">
                  <Link className="font-medium hover:text-teal-700" to={`/stocks/${w.stock_id}`}>{w.symbol}</Link>
                  <span className={Number(w.change_pct) >= 0 ? 'gain' : 'loss'}>{pct(w.change_pct)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">Today&apos;s signals</h3>
          {data.todays_signals.length === 0 ? <Empty text="No signals yet — refresh data from Admin" /> : (
            <ul className="space-y-2">
              {data.todays_signals.map((s) => (
                <li key={s.stock_id} className="flex items-center justify-between text-sm gap-2">
                  <Link to={`/stocks/${s.stock_id}`} className="font-medium hover:text-teal-700">{s.symbol}</Link>
                  <Badge tone={s.expected_direction === 'Bullish' ? 'bull' : s.expected_direction === 'Bearish' ? 'bear' : 'neutral'}>
                    {s.expected_direction} {s.bullish_probability}%
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">AI recommendations</h3>
          {data.ai_recommendations.length === 0 ? <Empty text="Run analysis to generate predictions" /> : (
            <ul className="space-y-3">
              {data.ai_recommendations.map((r) => (
                <li key={r.stock_id} className="text-sm border-b border-[var(--color-line)] pb-2 last:border-0">
                  <div className="flex justify-between">
                    <Link to={`/stocks/${r.stock_id}`} className="font-medium hover:text-teal-700">{r.symbol}</Link>
                    <span>{r.bullish_probability}%</span>
                  </div>
                  <div className="text-xs text-[var(--color-ink-muted)] mt-0.5">
                    {r.expected_direction} · {r.confidence} · Risk {r.risk}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {data.upcoming_breakouts.length > 0 && (
        <Panel className="mt-4">
          <h3 className="font-semibold mb-3">Momentum / breakout candidates</h3>
          <div className="flex flex-wrap gap-2">
            {data.upcoming_breakouts.map((b) => (
              <Link key={b.stock_id} to={`/stocks/${b.stock_id}`} className="rounded-md border border-[var(--color-line)] px-3 py-1.5 text-sm hover:border-teal-600">
                {b.symbol} <span className="gain">{pct(b.change_pct)}</span>
              </Link>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function MoverTable({ rows }: { rows: Array<{ stock_id: number; symbol: string; company_name: string; price: number; change_pct: number }> }) {
  if (!rows.length) return <Empty text="No price data yet" />;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-[var(--color-ink-muted)] text-xs">
          <th className="pb-2">Symbol</th>
          <th className="pb-2">Price</th>
          <th className="pb-2 text-right">Change</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.stock_id} className="border-t border-[var(--color-line)]">
            <td className="py-2">
              <Link to={`/stocks/${r.stock_id}`} className="font-medium hover:text-teal-700">{r.symbol}</Link>
              <div className="text-xs text-[var(--color-ink-muted)] truncate max-w-[160px]">{r.company_name}</div>
            </td>
            <td>{money(r.price)}</td>
            <td className={`text-right ${r.change_pct >= 0 ? 'gain' : 'loss'}`}>{pct(r.change_pct)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
