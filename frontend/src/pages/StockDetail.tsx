import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../lib/api';
import PriceChart, { type Candle } from '../charts/PriceChart';
import { Badge, Button, Empty, Loading, PageHeader, Panel, money, pct } from '../components/ui';

type Analysis = {
  error?: string;
  needs_download?: boolean;
  symbol: string;
  company_name: string;
  latest_price: number;
  change_pct: number;
  indicators: Record<string, number | boolean | string>;
  candlestick_patterns: Array<{ pattern_name: string; signal: string; strength: number; description?: string }>;
  chart_patterns: Array<{ pattern_name: string; signal: string; strength: number; target_price?: number; stop_loss?: number }>;
  trend: { trend: string; score: number; strength: number };
  support_resistance: Array<{ level_type: string; price: number; strength: number }>;
  nearest_levels: {
    nearest_support?: { price: number };
    nearest_resistance?: { price: number };
    support_distance_pct?: number;
    resistance_distance_pct?: number;
  };
  volume: Record<string, number | boolean>;
  prediction: {
    bullish_probability: number;
    bearish_probability: number;
    expected_direction: string;
    confidence: string;
    holding_period: string;
    risk: string;
    scores?: Record<string, number>;
    disclaimer: string;
    model_version: string;
  };
};

export default function StockDetailPage() {
  const { id } = useParams();
  const [prices, setPrices] = useState<Candle[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [meta, setMeta] = useState<{ symbol: string; company_name: string } | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('Loading…');

  const load = useCallback(async () => {
    if (!id) return;
    setError('');
    setLoading(true);
    setStatus('Fetching prices and running analysis…');
    try {
      const stockMeta = await api<{ symbol: string; company_name: string }>(`/api/stocks/${id}`);
      setMeta(stockMeta);
      setStatus(`Loading ${stockMeta.symbol} — downloading history if needed…`);

      // Analysis endpoint auto-downloads missing Yahoo history
      const a = await api<Analysis>(`/api/stocks/${id}/analysis`);
      const p = await api<Candle[]>(`/api/stocks/${id}/prices?limit=365`);

      setPrices((p || []).map((x) => ({ ...x, date: String(x.date).slice(0, 10) })));
      setAnalysis(a);
      if (a?.error) setError(a.error);
    } catch (e) {
      setAnalysis(null);
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
      setStatus('');
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const refresh = async () => {
    setBusy(true);
    setError('');
    setStatus('Refreshing latest market data…');
    try {
      await api(`/api/stocks/${id}/download?period=2y`, { method: 'POST' });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Refresh failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div>
        <PageHeader title={meta?.symbol || `Stock #${id}`} subtitle={meta?.company_name || status} />
        <Panel>
          <Loading />
          <p className="text-center text-sm text-[var(--color-ink-muted)] -mt-4 pb-4">{status}</p>
        </Panel>
      </div>
    );
  }

  const title = analysis?.symbol || meta?.symbol || `Stock #${id}`;
  const company = analysis?.company_name || meta?.company_name || '';

  if (error || !analysis?.prediction) {
    return (
      <div>
        <PageHeader
          title={title}
          subtitle={company}
          action={<Button onClick={refresh} disabled={busy}>{busy ? 'Retrying…' : 'Retry'}</Button>}
        />
        <Panel>
          <p className="text-sm text-[var(--color-loss)]">
            {error || 'Could not load analysis for this symbol.'}
          </p>
        </Panel>
      </div>
    );
  }

  const pred = analysis.prediction;
  const scores = pred.scores || {};

  return (
    <div>
      <PageHeader
        title={analysis.symbol}
        subtitle={`${analysis.company_name} · ${money(analysis.latest_price)} · ${pct(analysis.change_pct)}`}
        action={<Button onClick={refresh} disabled={busy}>{busy ? 'Refreshing…' : 'Refresh'}</Button>}
      />

      <div className="grid xl:grid-cols-3 gap-4 mb-4">
        <Panel className="xl:col-span-2">
          {prices.length ? <PriceChart data={prices} /> : <Empty text="No candles available" />}
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-2">AI probability</h3>
          <div className="flex items-end gap-3">
            <div className="text-4xl font-semibold gain">{pred.bullish_probability}%</div>
            <div className="text-sm text-[var(--color-ink-muted)] pb-1">bullish</div>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge tone={pred.expected_direction === 'Bullish' ? 'bull' : pred.expected_direction === 'Bearish' ? 'bear' : 'neutral'}>
              {pred.expected_direction}
            </Badge>
            <Badge>{pred.confidence} confidence</Badge>
            <Badge>Risk {pred.risk}</Badge>
          </div>
          <p className="text-xs mt-3 text-[var(--color-ink-muted)]">{pred.holding_period}</p>
          <p className="text-xs mt-2 text-[var(--color-ink-muted)]">{pred.disclaimer}</p>
          <p className="text-[10px] mt-1 text-[var(--color-ink-muted)]">Model {pred.model_version}</p>

          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            {Object.entries(scores).map(([k, v]) => (
              <div key={k} className="rounded-md bg-[var(--color-paper)] px-2 py-1.5">
                <div className="text-[var(--color-ink-muted)] capitalize">{k.replaceAll('_', ' ')}</div>
                <div className="font-semibold">{typeof v === 'number' ? v : String(v)}</div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-4 mb-4">
        <Panel>
          <h3 className="font-semibold mb-2">Trend</h3>
          <div className="text-lg capitalize">{analysis.trend.trend}</div>
          <div className="text-sm text-[var(--color-ink-muted)]">Score {analysis.trend.score} · Strength {analysis.trend.strength}</div>
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-2">Volume</h3>
          <div className="text-sm space-y-1">
            <div>Spike: {String(analysis.volume.volume_spike)}</div>
            <div>Buy pressure: {String(analysis.volume.buying_pressure)}</div>
            <div>Sell pressure: {String(analysis.volume.selling_pressure)}</div>
            <div>Score: {String(analysis.volume.volume_score)}</div>
          </div>
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-2">Nearest S/R</h3>
          <div className="text-sm space-y-1">
            <div>Support: {analysis.nearest_levels.nearest_support?.price ?? '—'} ({analysis.nearest_levels.support_distance_pct ?? '—'}%)</div>
            <div>Resistance: {analysis.nearest_levels.nearest_resistance?.price ?? '—'} ({analysis.nearest_levels.resistance_distance_pct ?? '—'}%)</div>
          </div>
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-2">Key indicators</h3>
          <div className="text-sm space-y-1">
            <div>RSI: {fmt(analysis.indicators.rsi_14)}</div>
            <div>MACD: {fmt(analysis.indicators.macd)}</div>
            <div>ADX: {fmt(analysis.indicators.adx)}</div>
            <div>ATR: {fmt(analysis.indicators.atr_14)}</div>
          </div>
        </Panel>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel>
          <h3 className="font-semibold mb-3">Chart patterns</h3>
          {(analysis.chart_patterns || []).length === 0 ? <Empty text="No chart patterns detected" /> : (
            <ul className="space-y-2">
              {analysis.chart_patterns.map((p, i) => (
                <li key={i} className="flex items-center justify-between text-sm border-b border-[var(--color-line)] pb-2">
                  <div>
                    <div className="font-medium">{p.pattern_name}</div>
                    {(p.target_price || p.stop_loss) && (
                      <div className="text-xs text-[var(--color-ink-muted)]">
                        Target {p.target_price ?? '—'} · SL {p.stop_loss ?? '—'}
                      </div>
                    )}
                  </div>
                  <Badge tone={p.signal === 'bullish' ? 'bull' : p.signal === 'bearish' ? 'bear' : 'neutral'}>
                    {p.signal} · {p.strength}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel>
          <h3 className="font-semibold mb-3">Candlestick patterns</h3>
          {(analysis.candlestick_patterns || []).length === 0 ? <Empty text="No candlestick patterns on latest bars" /> : (
            <ul className="space-y-2">
              {analysis.candlestick_patterns.map((p, i) => (
                <li key={i} className="text-sm border-b border-[var(--color-line)] pb-2">
                  <div className="flex justify-between">
                    <span className="font-medium">{p.pattern_name}</span>
                    <Badge tone={p.signal === 'bullish' ? 'bull' : p.signal === 'bearish' ? 'bear' : 'neutral'}>{p.signal}</Badge>
                  </div>
                  <p className="text-xs text-[var(--color-ink-muted)] mt-1">{p.description}</p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel className="mt-4">
        <h3 className="font-semibold mb-3">Support & resistance levels</h3>
        <div className="flex flex-wrap gap-2">
          {(analysis.support_resistance || []).slice(0, 12).map((l, i) => (
            <span key={i} className="rounded-md border border-[var(--color-line)] px-2.5 py-1 text-xs">
              {l.level_type}: <strong>{money(l.price)}</strong>
            </span>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function fmt(v: unknown) {
  if (typeof v === 'number') return v.toFixed(2);
  if (v === undefined || v === null) return '—';
  return String(v);
}
