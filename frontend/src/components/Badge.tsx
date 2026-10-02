import type { ReactNode } from 'react';

type Tone = 'ok' | 'warn' | 'danger' | 'info' | 'muted';

const LABELS: Record<string, string> = {
  healthy: '健康',
  online: '在线',
  active: '活跃',
  normal: '正常',
  enabled: '已启用',
  high_load: '高负载',
  degraded: '降级中',
  idle: '空闲',
  acknowledged: '已确认',
  recovered: '已恢复',
  offline: '离线',
  circuit_open: '已熔断',
  open: '未处理',
  draining: '摘流中',
  critical: '严重',
  warning: '警告',
  info: '提示',
};

export function statusLabel(status: string): string {
  return LABELS[status] || status;
}

export function statusTone(status: string): Tone {
  if (['healthy', 'online', 'active', 'normal', 'enabled', 'recovered', 'success'].includes(status)) return 'ok';
  if (['high_load', 'degraded', 'warning', 'idle', 'acknowledged', 'draining'].includes(status)) return 'warn';
  if (['offline', 'circuit_open', 'critical', 'danger', 'failed'].includes(status)) return 'danger';
  if (['info', 'open'].includes(status)) return 'info';
  return 'muted';
}

export default function Badge({ status, children }: { status?: string; children?: ReactNode }) {
  const tone = status ? statusTone(status) : 'muted';
  const label = children ?? (status ? statusLabel(status) : '');
  return (
    <span className={`badge badge-${tone}`}>
      <span className="bdot" />
      {label}
    </span>
  );
}
