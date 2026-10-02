import { useCallback, useEffect, useState } from 'react';
import { traffic } from '../api';
import type { RateLimitItem, TenantQuotaItem, TrafficSummary } from '../types';
import Panel from '../components/Panel';
import Badge from '../components/Badge';
import Switch from '../components/Switch';
import ProgressBar from '../components/ProgressBar';

const fmt = (n: number) => n.toLocaleString('en-US');

export default function Traffic() {
  const [summary, setSummary] = useState<TrafficSummary | null>(null);
  const [rateLimits, setRateLimits] = useState<RateLimitItem[]>([]);
  const [queues, setQueues] = useState<{ id: number; priority: string; scenario: string; queue_length: number; wait_ms: number }[]>([]);
  const [quotas, setQuotas] = useState<TenantQuotaItem[]>([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [s, r, q, t] = await Promise.all([
        traffic.summary(),
        traffic.rateLimits(),
        traffic.priorityQueues(),
        traffic.tenantQuotas(),
      ]);
      setSummary(s);
      setRateLimits(r.items);
      setQueues(q.items);
      setQuotas(t.items);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggleRule = async (r: RateLimitItem, enabled: boolean) => {
    await traffic.updateRateLimit(r.id, { enabled });
    await load();
  };

  const s = summary;

  return (
    <div className="content">
      <div className="page-head">
        <div>
          <div className="page-title">流量控制</div>
          <div className="page-desc">限流、配额与优先级管理，保护后端稳定并保障资源公平分配。</div>
        </div>
        <div className="head-actions">
          <button className="btn btn-ghost" onClick={load}>刷新</button>
        </div>
      </div>

      {error && <div className="badge badge-danger" style={{ alignSelf: 'flex-start' }}>{error}</div>}

      <div className="grid-3">
        <Panel>
          <div className="metric-label" style={{ marginBottom: 'var(--sp-3)' }}>今日请求配额</div>
          <div className="metric-value" style={{ fontSize: 24 }}>
            <span className="num">{s ? fmt(s.today_requests_used) : '—'}</span>
            <span className="unit">/ {s ? fmt(s.today_requests_quota) : '—'}</span>
          </div>
          <ProgressBar value={s?.today_used_pct ?? 0} tone="ok" style={{ marginTop: 'var(--sp-3)' }} />
          <div className="field-hint" style={{ marginTop: 'var(--sp-2)' }}>已使用 {s?.today_used_pct ?? 0}%</div>
        </Panel>
        <Panel>
          <div className="metric-label" style={{ marginBottom: 'var(--sp-3)' }}>本月 Token 用量</div>
          <div className="metric-value" style={{ fontSize: 24 }}>
            <span className="num">{s ? fmt(Math.round(s.month_tokens_used / 1e6)) : '—'}M</span>
            <span className="unit">/ {s ? fmt(Math.round(s.month_tokens_quota / 1e6)) : '—'}M</span>
          </div>
          <ProgressBar value={s?.month_used_pct ?? 0} tone="ok" style={{ marginTop: 'var(--sp-3)' }} />
          <div className="field-hint" style={{ marginTop: 'var(--sp-2)' }}>已使用 {s?.month_used_pct ?? 0}%</div>
        </Panel>
        <Panel>
          <div className="metric-label" style={{ marginBottom: 'var(--sp-3)' }}>当前 QPS 限流</div>
          <div className="metric-value" style={{ fontSize: 24 }}>
            <span className="num">{s?.current_qps_limit ?? '—'}</span>
            <span className="unit">/s</span>
          </div>
          <ProgressBar value={s?.current_qps_used_pct ?? 0} tone="warn" style={{ marginTop: 'var(--sp-3)' }} />
          <div className="field-hint" style={{ marginTop: 'var(--sp-2)' }}>峰值已触发 {s?.rate_limit_hits_today ?? 0} 次限流（今日）</div>
        </Panel>
      </div>

      <Panel title="限流规则" sub="按维度精细化限流，令牌桶算法">
        <div style={{ paddingTop: 0 }}>
          <table className="table">
            <thead><tr><th>维度</th><th>阈值</th><th>算法</th><th>超限动作</th><th>状态</th></tr></thead>
            <tbody>
              {rateLimits.map((r) => (
                <tr key={r.id}>
                  <td className="cell-hi">{r.name}</td>
                  <td className="num">{r.threshold} req/{r.window_seconds}s</td>
                  <td>{r.algorithm === 'token_bucket' ? '令牌桶' : '滑动窗口'}</td>
                  <td>{r.action}</td>
                  <td><Switch checked={r.enabled} onChange={(v) => toggleRule(r, v)} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid-2">
        <Panel title="优先级队列" sub="高优请求抢占，低优请求排队">
          <table className="table">
            <thead><tr><th>优先级</th><th>场景</th><th>队列长度</th><th>等待</th></tr></thead>
            <tbody>
              {queues.map((q) => (
                <tr key={q.id}>
                  <td><Badge status={q.priority === 'P0' ? 'critical' : q.priority === 'P1' ? 'warning' : q.priority === 'P2' ? 'info' : 'muted'}>{q.priority}</Badge></td>
                  <td className="cell-hi">{q.scenario}</td>
                  <td className="num">{q.queue_length}</td>
                  <td className="num">{q.wait_ms}ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="租户配额" sub="各租户的用量与配额状态">
          <table className="table">
            <thead><tr><th>租户</th><th>用量</th><th>配额</th><th>状态</th></tr></thead>
            <tbody>
              {quotas.map((t) => (
                <tr key={t.tenant_id}>
                  <td className="cell-hi">{t.name}</td>
                  <td className="num">{t.used_pct}%</td>
                  <td className="num">{fmt(t.quota_monthly)}</td>
                  <td><Badge status={t.status === 'danger' ? 'critical' : t.status === 'warning' ? 'warning' : 'normal'}>{t.status === 'danger' ? '即将耗尽' : t.status === 'warning' ? '接近上限' : '正常'}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}
