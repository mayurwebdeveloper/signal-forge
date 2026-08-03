import { useEffect, useRef } from 'react';
import { createChart, type IChartApi, type ISeriesApi, type Time } from 'lightweight-charts';

export type Candle = {
  /** YYYY-MM-DD for daily, or ISO datetime for intraday */
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type Props = {
  data: Candle[];
  intraday?: boolean;
  height?: number;
};

function toChartTime(raw: string, intraday: boolean): Time {
  if (!intraday && /^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    return raw as Time;
  }
  const ms = Date.parse(raw.includes('T') ? `${raw}Z` : raw);
  if (Number.isNaN(ms)) {
    // Fallback: date-only
    return raw.slice(0, 10) as Time;
  }
  return Math.floor(ms / 1000) as Time;
}

export default function PriceChart({ data, intraday = false, height = 420 }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart: IChartApi = createChart(ref.current, {
      height,
      layout: {
        background: { color: 'transparent' },
        textColor: '#3d524c',
        fontFamily: 'DM Sans, sans-serif',
      },
      grid: {
        vertLines: { color: 'rgba(197, 212, 205, 0.45)' },
        horzLines: { color: 'rgba(197, 212, 205, 0.45)' },
      },
      rightPriceScale: { borderColor: '#c5d4cd' },
      timeScale: {
        borderColor: '#c5d4cd',
        timeVisible: intraday,
        secondsVisible: false,
      },
      crosshair: { mode: 1 },
    });

    const candleSeries: ISeriesApi<'Candlestick'> = chart.addCandlestickSeries({
      upColor: '#0d7a4f',
      downColor: '#b42318',
      borderUpColor: '#0d7a4f',
      borderDownColor: '#b42318',
      wickUpColor: '#0d7a4f',
      wickDownColor: '#b42318',
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
    });
    chart.priceScale('vol').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    const candles = data
      .filter((d) => [d.open, d.high, d.low, d.close].every((v) => Number.isFinite(v)))
      .map((d) => ({
        time: toChartTime(d.time, intraday),
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }));
    const vols = data
      .filter((d) => [d.open, d.high, d.low, d.close].every((v) => Number.isFinite(v)))
      .map((d) => ({
        time: toChartTime(d.time, intraday),
        value: Number.isFinite(d.volume) ? d.volume : 0,
        color: d.close >= d.open ? 'rgba(13,122,79,0.35)' : 'rgba(180,35,24,0.35)',
      }));

    if (candles.length) {
      candleSeries.setData(candles);
      volumeSeries.setData(vols);
      chart.timeScale().fitContent();
    }
    const onResize = () => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    };
    onResize();
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      chart.remove();
    };
  }, [data, height, intraday]);

  return <div ref={ref} className="w-full" style={{ height }} />;
}
