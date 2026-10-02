import { useCallback, useEffect, useState } from 'react';
import { resilience } from '../api';
import type { ResiliencePolicyItem } from '../types';
import Panel from '../components/Panel';
import Badge from '../components/Badge';
import Switch from '../components/Switch';

const FAILOVER_LABELS: Record<string, string> = {
  auto_switch: '自动切换至备用模型',
  alert_only: '仅告警不切换',
};

const BACKUP_LABELS: Record<string, string> = {
  same_capability_lowest_cost: '同能力 · 次低成本',
  fixed_list: '固定备用清单',
};

const DEGRADE_LABELS: Record<string, string> = {
  downgrade_model: '降级到低档模型',
  cache_fallback: '返回缓存/兜底话术',
  error: '直接报错',
};

export default function Resilience() {
  const [policies, setPolicies] = useState<ResiliencePolicyItem[]>([]);
  const [editing, setEditing] = useState<ResiliencePolicyItem | null>(null);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const r = await resilience.policies();
      setPolicies(r.items);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openEdit = (p: ResiliencePolicyItem) => {
    setEditing(p);
    setForm({
      failure_rate_threshold: p.failure_rate_threshold,
      cooldown_seconds: p.cooldown_seconds,
      half_open_enabled: p.half_open_enabled,
      failover_mode: p.failover_mode,
      backup_selection: p.backup_selection,
      degrade_mode: p.degrade_mode,
      backup_chain: p.backup_chain.join(','),
      retry_count: p.retry_count,
    });
  };

  const save = async () => {
    if (!editing) return;
    try {
      await resilience.updatePolicy(editing.id, {
        failure_rate_threshold: Number(form.failure_rate_threshold),
        cooldown_seconds: Number(form.cooldown_seconds),
        half_open_enabled: Boolean(form.half_open_enabled),
        failover_mode: String(form.failover_mode),
        backup_selection: String(form.backup_selection),
        degrade_mode: String(form.degrade_mode),
        backup_chain: String(form.backup_chain).split(',').map((s) => s.trim()).filter(Boolean),
        retry_count: Number(form.retry_count),
      });
      setEditing(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    }
  };

  return (
    <div className="content">
      <div className="page-head">
        <div>
          <div className="page-title">容灾策略</div>
          <div className="page-desc">故障自动切换与降级，保障高可用。健康检查、熔断、故障切换、降级、重试。</div>
        </div>
        <div className="head-actions">
          <button className="btn btn-ghost" onClick={load}>刷新</button>
        </div>
      </div>

      {error && <div className="badge badge-danger" style={{ alignSelf: 'flex-start' }}>{error}</div>}

      <Panel title="容灾策略清单" sub="各供应商的容灾策略配置">
        <div style={{ paddingTop: 0 }}>
          <table className="table">
            <thead><tr><th>供应商</th><th>备用链路</th><th>重试次数</th><th>当前状态</th><th>切换记录</th><th>操作</th></tr></thead>
            <tbody>
              {policies.map((p) => (
                <tr key={p.id}>
                  <td className="cell-hi">{p.provider_name}</td>
                  <td>→ {p.backup_chain.join(' → ') || '—'}</td>
                  <td className="num">{p.retry_count}</td>
                  <td><Badge status={p.status} /></td>
                  <td className="num">{p.switch_count} 次</td>
                  <td><button className="btn btn-ghost" style={{ padding: '5px 10px', fontSize: 12 }} onClick={() => openEdit(p)}>编辑</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {editing && (
        <div className="modal-mask" onClick={() => setEditing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="page-title" style={{ fontSize: 18, marginBottom: 'var(--sp-4)' }}>编辑容灾策略：{editing.provider_name}</div>

            <div className="field">
              <div className="field-label">失败率阈值</div>
              <div className="weight-row">
                <div className="weight-track"><div className="weight-fill" style={{ width: `${Number(form.failure_rate_threshold ?? 0) * 100}%` }} /></div>
                <span className="weight-val">{Math.round(Number(form.failure_rate_threshold ?? 0) * 100)}%</span>
              </div>
              <input className="input num" type="number" step="0.05" min="0" max="1" value={Number(form.failure_rate_threshold ?? 0)} onChange={(e) => setForm({ ...form, failure_rate_threshold: Number(e.target.value) })} style={{ marginTop: 'var(--sp-2)' }} />
            </div>

            <div className="grid-2" style={{ gap: 'var(--sp-3)' }}>
              <div className="field"><div className="field-label">熔断冷却时间（秒）</div>
                <input className="input num" type="number" value={Number(form.cooldown_seconds ?? 30)} onChange={(e) => setForm({ ...form, cooldown_seconds: Number(e.target.value) })} />
              </div>
              <div className="field"><div className="field-label">重试次数</div>
                <input className="input num" type="number" value={Number(form.retry_count ?? 2)} onChange={(e) => setForm({ ...form, retry_count: Number(e.target.value) })} />
              </div>
            </div>

            <div className="field"><div className="field-label">主模型失败后</div>
              <select className="select" value={String(form.failover_mode ?? 'auto_switch')} onChange={(e) => setForm({ ...form, failover_mode: e.target.value })}>
                {Object.entries(FAILOVER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="field"><div className="field-label">备用模型选择</div>
              <select className="select" value={String(form.backup_selection ?? 'same_capability_lowest_cost')} onChange={(e) => setForm({ ...form, backup_selection: e.target.value })}>
                {Object.entries(BACKUP_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div className="field"><div className="field-label">全部不可用时降级</div>
              <select className="select" value={String(form.degrade_mode ?? 'downgrade_model')} onChange={(e) => setForm({ ...form, degrade_mode: e.target.value })}>
                {Object.entries(DEGRADE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>

            <div className="field">
              <div className="field-label">备用链路（供应商名，逗号分隔）</div>
              <input className="input" value={String(form.backup_chain ?? '')} onChange={(e) => setForm({ ...form, backup_chain: e.target.value })} />
            </div>

            <div className="weight-row" style={{ marginBottom: 'var(--sp-4)' }}>
              <span className="weight-label" style={{ width: 'auto', flex: 1 }}>半开试探</span>
              <Switch checked={Boolean(form.half_open_enabled)} onChange={(v) => setForm({ ...form, half_open_enabled: v })} />
            </div>

            <div style={{ display: 'flex', gap: 'var(--sp-2)', justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button>
              <button className="btn btn-primary" onClick={save}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
