import { useEffect, useRef } from 'react';
import { createChart, type IChartApi, type ISeriesApi } from 'lightweight-charts';

export type Candle = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type Props = {
  data: Candle[];
  height?: number;
};

export default function PriceChart({ data, height = 420 }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, {
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
      timeScale: { borderColor: '#c5d4cd' },
      crosshair: { mode: 1 },
    });
    chartRef.current = chart;

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

    const candles = data.map((d) => ({
      time: d.date as unknown as string,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    const vols = data.map((d) => ({
      time: d.date as unknown as string,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(13,122,79,0.35)' : 'rgba(180,35,24,0.35)',
    }));

    candleSeries.setData(candles as never);
    volumeSeries.setData(vols as never);
    chart.timeScale().fitContent();

    const onResize = () => {
      if (ref.current) chart.applyOptions({ width: ref.current.clientWidth });
    };
    onResize();
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [data, height]);

  return <div ref={ref} className="w-full" style={{ height }} />;
}
