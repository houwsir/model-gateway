import type { ReactNode } from 'react';

type Tone = 'accent' | 'info' | 'ok' | 'warn';

const TONE_MAP: Record<Tone, { mc: string; miBg: string; mi: string }> = {
  accent: { mc: 'var(--accent)', miBg: 'var(--accent-soft)', mi: 'var(--accent)' },
  info: { mc: 'var(--info)', miBg: 'var(--info-soft)', mi: 'var(--info)' },
  ok: { mc: 'var(--ok)', miBg: 'var(--ok-soft)', mi: 'var(--ok)' },
  warn: { mc: 'var(--warn)', miBg: 'var(--warn-soft)', mi: 'var(--warn)' },
};

interface MetricCardProps {
  label: string;
  value: string | number;
  unit?: string;
  delta?: string;
  deltaUp?: boolean;
  tone?: Tone;
  icon?: ReactNode;
}

export default function MetricCard({ label, value, unit, delta, deltaUp = true, tone = 'accent', icon }: MetricCardProps) {
  const t = TONE_MAP[tone];
  return (
    <div className="metric" style={{ '--mc': t.mc, '--mi-bg': t.miBg, '--mi': t.mi } as React.CSSProperties}>
      <div className="metric-top">
        <span className="metric-label">{label}</span>
        <div className="metric-ic">{icon}</div>
      </div>
      <div className="metric-value">
        <span className="num">{value}</span>
        {unit && <span className="unit">{unit}</span>}
      </div>
      {delta && (
        <div className={`metric-delta ${deltaUp ? 'up' : 'down'}`}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
            {deltaUp ? <path d="M7 17L17 7M17 7H8M17 7v9" /> : <path d="M7 7l10 10M17 7H8M17 7v9" />}
          </svg>
          {delta}
        </div>
      )}
    </div>
  );
}
