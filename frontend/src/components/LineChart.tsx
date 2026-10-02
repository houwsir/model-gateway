import type { TrafficPoint } from '../types';

interface LineChartProps {
  points: TrafficPoint[];
  height?: number;
}

// 内联 SVG 折线图：总请求(琥珀) / 成功(蓝) / 失败(红)
export default function LineChart({ points, height = 220 }: LineChartProps) {
  const width = 720;
  const padY = 12;
  const data = points.length > 0 ? points : [];
  const maxVal = Math.max(1, ...data.map((p) => Math.max(p.total, p.success, p.failed)));

  const x = (i: number) => (data.length <= 1 ? 0 : (i / (data.length - 1)) * width);
  const y = (v: number) => height - padY - (v / maxVal) * (height - padY * 2);

  const linePath = (key: 'total' | 'success' | 'failed') => {
    if (data.length === 0) return '';
    return data.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join(' ');
  };

  return (
    <svg className="chart-svg" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ display: 'block', width: '100%' }}>
      {[20, 80, 140, 200].map((gy) => (
        <line key={gy} className="grid-line" x1="0" y1={gy} x2={width} y2={gy} style={{ stroke: 'var(--border-soft)', strokeWidth: 1 }} />
      ))}
      {data.length > 0 && (
        <>
          <path d={linePath('failed')} fill="none" stroke="var(--danger)" strokeWidth="1.6" opacity="0.7" />
          <path d={linePath('success')} fill="none" stroke="var(--info)" strokeWidth="2" opacity="0.9" />
          <path d={linePath('total')} fill="none" stroke="var(--accent)" strokeWidth="2.4" />
        </>
      )}
    </svg>
  );
}
