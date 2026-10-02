interface ProgressBarProps {
  value: number; // 0-100
  tone?: 'ok' | 'warn' | 'danger' | 'accent' | 'info';
  style?: React.CSSProperties;
}

const TONE_COLOR: Record<string, string> = {
  ok: 'var(--ok)',
  warn: 'var(--warn)',
  danger: 'var(--danger)',
  accent: 'var(--accent)',
  info: 'var(--info)',
};

export default function ProgressBar({ value, tone = 'accent', style }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="bar" style={style}>
      <i style={{ width: `${clamped}%`, ['--bar-c' as string]: TONE_COLOR[tone] || 'var(--accent)' }} />
    </div>
  );
}
