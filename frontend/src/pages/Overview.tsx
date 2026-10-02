import { useState } from 'react';
import { overview } from '../api';
import { usePolling } from '../hooks/usePolling';
import MetricCard from '../components/MetricCard';
import Panel from '../components/Panel';
import Badge from '../components/Badge';
import ProgressBar from '../components/ProgressBar';
import LineChart from '../components/LineChart';
import TestRequestModal from '../components/TestRequestModal';

const fmt = (n: number) => n.toLocaleString('en-US');

export default function Overview() {
  const [modalOpen, setModalOpen] = useState(false);
  const summary = usePolling(overview.summary, 3000);
  const trend = usePolling(() => overview.trafficTrend('24h'), 3000);
  const health = usePolling(overview.modelHealth, 3000);
  const recentAlerts = usePolling(() => overview.recentAlerts(3), 3000);
  const cost = usePolling(overview.costDistribution, 3000);

  const s = summary.data;
  const alertItems = recentAlerts.data?.items ?? [];
  const costItems = cost.data?.items ?? [];

  return (
    <div className="content">
      <div className="page-head">
        <div>
          <div className="page-title">监控大盘</div>
          <div className="page-desc">实时掌握网关运行状态、模型健康度与成本消耗，一眼看清全局。</div>
        </div>
        <div className="head-actions">
          <button className="btn btn-ghost" onClick={summary.refresh}>
            刷新
          </button>
          <button className="btn btn-primary" onClick={() => setModalOpen(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 5v14M5 12h14" />
            </svg>
            新建请求
          </button>
        </div>
      </div>

      <div className="metrics">
        <MetricCard
          label="今日请求量"
          value={s ? fmt(s.today_requests) : '—'}
          unit="次"
          delta={`${s?.requests_delta_pct ?? 0}% 较昨日`}
          deltaUp={(s?.requests_delta_pct ?? 0) >= 0}
          tone="accent"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M3 12h4l3-8 4 16 3-8h4" />
            </svg>
          }
        />
        <MetricCard
          label="平均延迟 P50"
          value={s ? s.latency_p50_ms : '—'}
          unit="ms"
          delta="5.8% 劣化"
          deltaUp={false}
          tone="info"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7v5l3 3" />
            </svg>
          }
        />
        <MetricCard
          label="服务可用性"
          value={s ? s.availability : '—'}
          unit="%"
          delta="目标 ≥ 99.95%"
          deltaUp
          tone="ok"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          }
        />
        <MetricCard
          label="今日成本估算"
          value={`$${s ? s.today_cost_usd.toFixed(2) : '—'}`}
          delta={`预算使用 ${s?.cost_budget_pct ?? 0}%`}
          deltaUp={false}
          tone="warn"
          icon={
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
          }
        />
      </div>

      <div className="grid-2">
        <Panel
          title="请求流量趋势"
          sub="近 24 小时 · 请求数（次/分钟）"
          actions={
            <div className="legend">
              <span className="legend-item"><span className="legend-dot" style={{ background: 'var(--accent)' }} />总请求</span>
              <span className="legend-item"><span className="legend-dot" style={{ background: 'var(--info)' }} />成功</span>
              <span className="legend-item"><span className="legend-dot" style={{ background: 'var(--danger)' }} />失败</span>
            </div>
          }
        >
          <LineChart points={trend.data?.points ?? []} />
        </Panel>

        <Panel title="模型健康状态" sub="路由候选模型的实时健康与负载">
          <div style={{ paddingTop: 0 }}>
            <table className="table">
              <thead>
                <tr><th>模型</th><th>状态</th><th>延迟</th><th>负载</th></tr>
              </thead>
              <tbody>
                {(health.data?.items ?? []).map((m) => (
                  <tr key={m.model}>
                    <td className="cell-hi">{m.model}</td>
                    <td><Badge status={m.status} /></td>
                    <td className="num">{m.latency_ms}ms</td>
                    <td style={{ width: 120 }}>
                      <ProgressBar value={m.load} tone={m.load >= 80 ? 'warn' : 'ok'} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <div className="grid-2">
        <Panel title="实时告警" sub="需要关注的事件">
          <div className="alert-list">
            {alertItems.map((a) => (
              <div className="alert-item" key={a.id}>
                <div className={`alert-ic ${a.severity === 'critical' ? 'crit' : a.severity === 'warning' ? 'warn' : 'info'}`}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 9v4M12 17h.01" />
                    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
                  </svg>
                </div>
                <div className="alert-body">
                  <div className="alert-title">{a.title}</div>
                  <div className="alert-desc">{a.description}</div>
                </div>
                <div className="alert-time">{a.created_at.slice(11, 19)}</div>
              </div>
            ))}
            {alertItems.length === 0 && <div className="empty">暂无告警</div>}
          </div>
        </Panel>

        <Panel title="成本分布" sub="按供应商 · 今日累计">
          {costItems.map((c) => (
            <div className="field" key={c.provider} style={{ marginBottom: 'var(--sp-5)' }}>
              <div className="weight-row">
                <span className="weight-label" style={{ width: 'auto', flex: 1 }}>{c.provider}</span>
                <span className="weight-val num" style={{ width: 'auto' }}>${c.cost_usd.toFixed(2)}</span>
              </div>
              <ProgressBar value={c.ratio} tone="accent" style={{ marginTop: 6 }} />
            </div>
          ))}
        </Panel>
      </div>

      {modalOpen && <TestRequestModal onClose={() => setModalOpen(false)} />}
    </div>
  );
}
