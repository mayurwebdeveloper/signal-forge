import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Badge, Button, Empty, Loading, PageHeader, Panel, money, pct } from '../components/ui';

type Suggestion = {
  id: number;
  rank: number;
  stock_id: number;
  symbol: string;
  company_name: string;
  sector?: string;
  exchange?: string;
  score: number;
  next_day_probability: number;
  expected_direction: string;
  confidence: string;
  risk: string;
  price?: number;
  change_pct?: number;
  reasons: string[];
  features?: Record<string, unknown>;
};

type DailyPayload = {
  enabled: boolean;
  date: string;
  count: number;
  suggestions: Suggestion[];
  disclaimer: string;
  settings?: {
    suggestions_min_count: number;
    suggestions_max_count: number;
  };
};

export default function SuggestionsPage() {
  const [data, setData] = useState<DailyPayload | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setError('');
    try {
      const res = await api<DailyPayload>('/api/suggestions/daily');
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load suggestions');
    }
  };

  useEffect(() => {
    load();
  }, []);

  const refresh = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await api<DailyPayload>('/api/suggestions/daily/refresh', { method: 'POST' });
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Refresh failed');
    } finally {
      setBusy(false);
    }
  };

  if (error && !data) return <p className="text-[var(--color-loss)]">{error}</p>;
  if (!data) return <Loading />;

  if (!data.enabled) {
    return (
      <div>
        <PageHeader title="Daily suggestions" subtitle="Next-session stock ideas from system analytics" />
        <Empty text="Daily suggestions are disabled in system settings. Ask an admin to enable them." />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Daily suggestions"
        subtitle={`At least ${data.settings?.suggestions_min_count ?? 10} ranked next-session setups for ${data.date}`}
        action={
          <Button onClick={refresh} disabled={busy}>
            {busy ? 'Refreshing…' : 'Refresh list'}
          </Button>
        }
      />
      {error && <p className="mb-3 text-sm text-[var(--color-loss)]">{error}</p>}
      <p className="mb-4 text-xs text-[var(--color-ink-muted)]">{data.disclaimer}</p>

      {data.suggestions.length === 0 ? (
        <Empty text="No suggestions yet — refresh data from Admin, then try again" />
      ) : (
        <Panel className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--color-ink-muted)]">
                <th className="pb-2">#</th>
                <th className="pb-2">Symbol</th>
                <th className="pb-2">Price</th>
                <th className="pb-2">Change</th>
                <th className="pb-2">Next-day score</th>
                <th className="pb-2">Bias</th>
                <th className="pb-2">Why suggested</th>
              </tr>
            </thead>
            <tbody>
              {data.suggestions.map((s) => (
                <tr key={s.stock_id} className="border-t border-[var(--color-line)] align-top">
                  <td className="py-3 text-[var(--color-ink-muted)]">{s.rank}</td>
                  <td className="py-3">
                    <Link to={`/stocks/${s.stock_id}`} className="font-semibold hover:text-teal-700">
                      {s.symbol}
                    </Link>
                    <div className="text-xs text-[var(--color-ink-muted)] max-w-[200px] truncate">{s.company_name}</div>
                    <div className="text-xs text-[var(--color-ink-muted)]">{s.sector || s.exchange || '—'}</div>
                  </td>
                  <td className="py-3">{s.price != null ? money(s.price) : '—'}</td>
                  <td className={`py-3 ${Number(s.change_pct) >= 0 ? 'gain' : 'loss'}`}>
                    {s.change_pct != null ? pct(s.change_pct) : '—'}
                  </td>
                  <td className="py-3 font-semibold">{s.next_day_probability}%</td>
                  <td className="py-3">
                    <Badge tone={s.expected_direction === 'Bullish' ? 'bull' : s.expected_direction === 'Bearish' ? 'bear' : 'neutral'}>
                      {s.expected_direction}
                    </Badge>
                    <div className="text-xs text-[var(--color-ink-muted)] mt-1">
                      {s.confidence} · Risk {s.risk}
                    </div>
                  </td>
                  <td className="py-3">
                    <ul className="text-xs text-[var(--color-ink-muted)] space-y-0.5 list-disc pl-4 max-w-md">
                      {(s.reasons || []).slice(0, 4).map((r) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
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
