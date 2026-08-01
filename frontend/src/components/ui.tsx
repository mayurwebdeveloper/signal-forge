import type { ReactNode } from 'react';

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 mb-6 animate-rise">
      <div>
        <h1 className="font-display text-4xl tracking-tight text-[var(--color-ink)]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-[var(--color-ink-muted)]">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`card-surface rounded-xl p-4 ${className}`}>{children}</div>;
}

export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: 'gain' | 'loss' | 'neutral' }) {
  const cls = tone === 'gain' ? 'gain' : tone === 'loss' ? 'loss' : '';
  return (
    <div className="card-surface rounded-xl p-4 animate-rise">
      <div className="text-xs uppercase tracking-wide text-[var(--color-ink-muted)]">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${cls}`}>{value}</div>
    </div>
  );
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'bull' | 'bear' | 'neutral' }) {
  const colors =
    tone === 'bull'
      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
      : tone === 'bear'
        ? 'bg-rose-50 text-rose-800 border-rose-200'
        : 'bg-slate-50 text-slate-700 border-slate-200';
  return <span className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${colors}`}>{children}</span>;
}

export function Button({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  disabled,
  className = '',
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit';
  variant?: 'primary' | 'ghost' | 'danger';
  disabled?: boolean;
  className?: string;
}) {
  const base =
    variant === 'primary'
      ? 'bg-[var(--color-teal)] hover:bg-[var(--color-teal-dark)] text-white'
      : variant === 'danger'
        ? 'bg-[var(--color-loss)] text-white hover:opacity-90'
        : 'bg-white/70 border border-[var(--color-line)] hover:bg-white text-[var(--color-ink)]';
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`rounded-md px-3.5 py-2 text-sm font-medium transition disabled:opacity-50 ${base} ${className}`}
    >
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-md border border-[var(--color-line)] bg-white/80 px-3 py-2 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-600/20 ${props.className || ''}`}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`w-full rounded-md border border-[var(--color-line)] bg-white/80 px-3 py-2 text-sm outline-none focus:border-teal-600 ${props.className || ''}`}
    />
  );
}

export function Empty({ text }: { text: string }) {
  return <div className="text-sm text-[var(--color-ink-muted)] py-8 text-center">{text}</div>;
}

export function Loading() {
  return <div className="text-sm text-[var(--color-ink-muted)] animate-pulse-soft py-10 text-center">Loading…</div>;
}

export function pct(n?: number | null) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

export function money(n?: number | null, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return n.toLocaleString(undefined, { maximumFractionDigits: digits });
}
