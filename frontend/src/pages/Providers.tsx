import { useCallback, useEffect, useState } from 'react';
import { providers } from '../api';
import type { ModelInstanceItem, ProviderItem } from '../types';
import Panel from '../components/Panel';
import Badge from '../components/Badge';
import ProgressBar from '../components/ProgressBar';

const LOGO_COLORS: Record<string, string> = {
  OpenAI: 'oklch(30% 0.12 245)',
  Anthropic: 'oklch(30% 0.12 20)',
  自建集群: 'oklch(30% 0.12 155)',
  智谱: 'oklch(30% 0.12 80)',
};

const fmt = (n: number) => n.toLocaleString('en-US');

export default function Providers() {
  const [providerList, setProviderList] = useState<ProviderItem[]>([]);
  const [instances, setInstances] = useState<ModelInstanceItem[]>([]);
  const [showProviderForm, setShowProviderForm] = useState(false);
  const [editing, setEditing] = useState<ModelInstanceItem | null>(null);
  const [error, setError] = useState('');

  const [providerForm, setProviderForm] = useState({ name: '', provider_type: 'mock', base_url: '', api_key: '' });
  const [instanceForm, setInstanceForm] = useState<Record<string, unknown>>({});

  const load = useCallback(async () => {
    try {
      const [p, m] = await Promise.all([providers.list(), providers.instances()]);
      setProviderList(p.items);
      setInstances(m.items);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const createProvider = async () => {
    try {
      await providers.create({ ...providerForm, base_url: providerForm.base_url || null });
      setShowProviderForm(false);
      setProviderForm({ name: '', provider_type: 'mock', base_url: '', api_key: '' });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建失败');
    }
  };

  const saveInstance = async () => {
    if (!editing) return;
    try {
      await providers.updateInstance(editing.id, instanceForm);
      setEditing(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    }
  };

  const openEdit = (m: ModelInstanceItem) => {
    setEditing(m);
    setInstanceForm({
      name: m.name,
      capabilities: m.capabilities,
      input_price: m.input_price,
      output_price: m.output_price,
      currency: m.currency,
      max_context_tokens: m.max_context_tokens,
      tier: m.tier,
      status: m.status,
      quality_score: m.quality_score,
    });
  };

  return (
    <div className="content">
      <div className="page-head">
        <div>
          <div className="page-title">供应商管理</div>
          <div className="page-desc">统一管理接入的模型供应商与模型实例，配置密钥、能力标签与定价。</div>
        </div>
        <div className="head-actions">
          <button className="btn btn-primary" onClick={() => setShowProviderForm(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg>
            接入供应商
          </button>
        </div>
      </div>

      {error && <div className="badge badge-danger" style={{ alignSelf: 'flex-start' }}>{error}</div>}

      <div className="grid-3">
        {providerList.map((p) => (
          <Panel key={p.id}>
            <div className="provider-row" style={{ marginBottom: 'var(--sp-4)' }}>
              <div className="provider-logo" style={{ background: LOGO_COLORS[p.name] || 'var(--surface-3)' }}>
                {p.name.slice(0, 2)}
              </div>
              <div>
                <div className="route-name" style={{ fontSize: 14.5 }}>{p.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-faint)' }}>{p.model_summary || '—'}</div>
              </div>
              <div className="spacer" style={{ marginLeft: 'auto' }}>
                <Badge status={p.status} />
              </div>
            </div>
            <div className="weight-row"><span className="weight-label" style={{ width: 'auto', flex: 1 }}>今日请求</span><span className="weight-val num" style={{ width: 'auto' }}>{fmt(p.today_requests)}</span></div>
            <div className="weight-row"><span className="weight-label" style={{ width: 'auto', flex: 1 }}>成功率</span><span className="weight-val num" style={{ width: 'auto' }}>{p.success_rate}%</span></div>
            <div className="weight-row"><span className="weight-label" style={{ width: 'auto', flex: 1 }}>配额余量</span><span className="weight-val num" style={{ width: 'auto' }}>{100 - p.quota_used_pct}%</span></div>
            <ProgressBar value={p.quota_used_pct} tone={p.quota_used_pct >= 80 ? 'warn' : 'ok'} style={{ marginTop: 'var(--sp-2)' }} />
          </Panel>
        ))}
      </div>

      <Panel title="模型实例清单" sub="网关可调度的全部模型实例">
        <div style={{ paddingTop: 0 }}>
          <table className="table">
            <thead><tr><th>模型</th><th>供应商</th><th>能力</th><th>输入价</th><th>输出价</th><th>状态</th><th></th></tr></thead>
            <tbody>
              {instances.map((m) => (
                <tr key={m.id}>
                  <td className="cell-hi">{m.name}</td>
                  <td>{m.provider_name}</td>
                  <td>
                    {m.capabilities.map((c) => (
                      <span className="badge badge-muted" key={c} style={{ marginRight: 4 }}>{c}</span>
                    ))}
                  </td>
                  <td className="num">{m.currency === 'USD' ? '$' : '¥'}{m.input_price}/M</td>
                  <td className="num">{m.currency === 'USD' ? '$' : '¥'}{m.output_price}/M</td>
                  <td><Badge status={m.status} /></td>
                  <td><button className="btn btn-ghost" style={{ padding: '5px 10px', fontSize: 12 }} onClick={() => openEdit(m)}>配置</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {showProviderForm && (
        <div className="modal-mask" onClick={() => setShowProviderForm(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="page-title" style={{ fontSize: 18, marginBottom: 'var(--sp-4)' }}>接入供应商</div>
            <div className="field"><div className="field-label">名称</div>
              <input className="input" value={providerForm.name} onChange={(e) => setProviderForm({ ...providerForm, name: e.target.value })} />
            </div>
            <div className="field"><div className="field-label">类型（demo 用 mock）</div>
              <select className="select" value={providerForm.provider_type} onChange={(e) => setProviderForm({ ...providerForm, provider_type: e.target.value })}>
                <option value="mock">mock</option><option value="openai">openai</option>
                <option value="anthropic">anthropic</option><option value="zhipu">zhipu</option>
              </select>
            </div>
            <div className="field"><div className="field-label">Base URL（可选）</div>
              <input className="input" value={providerForm.base_url} onChange={(e) => setProviderForm({ ...providerForm, base_url: e.target.value })} />
            </div>
            <div className="field"><div className="field-label">API Key（后端掩码存储）</div>
              <input className="input" value={providerForm.api_key} onChange={(e) => setProviderForm({ ...providerForm, api_key: e.target.value })} />
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-2)', justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setShowProviderForm(false)}>取消</button>
              <button className="btn btn-primary" onClick={createProvider}>接入</button>
            </div>
          </div>
        </div>
      )}

      {editing && (
        <div className="modal-mask" onClick={() => setEditing(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="page-title" style={{ fontSize: 18, marginBottom: 'var(--sp-4)' }}>配置模型：{editing.name}</div>
            <div className="grid-2" style={{ gap: 'var(--sp-3)' }}>
              <div className="field"><div className="field-label">名称</div>
                <input className="input" value={String(instanceForm.name ?? '')} onChange={(e) => setInstanceForm({ ...instanceForm, name: e.target.value })} />
              </div>
              <div className="field"><div className="field-label">档位</div>
                <select className="select" value={String(instanceForm.tier ?? 'mid')} onChange={(e) => setInstanceForm({ ...instanceForm, tier: e.target.value })}>
                  <option value="high">high</option><option value="mid">mid</option>
                  <option value="low">low</option><option value="fallback">fallback</option>
                </select>
              </div>
            </div>
            <div className="grid-3" style={{ gap: 'var(--sp-3)' }}>
              <div className="field"><div className="field-label">输入价</div>
                <input className="input num" type="number" value={Number(instanceForm.input_price ?? 0)} onChange={(e) => setInstanceForm({ ...instanceForm, input_price: Number(e.target.value) })} />
              </div>
              <div className="field"><div className="field-label">输出价</div>
                <input className="input num" type="number" value={Number(instanceForm.output_price ?? 0)} onChange={(e) => setInstanceForm({ ...instanceForm, output_price: Number(e.target.value) })} />
              </div>
              <div className="field"><div className="field-label">币种</div>
                <select className="select" value={String(instanceForm.currency ?? 'USD')} onChange={(e) => setInstanceForm({ ...instanceForm, currency: e.target.value })}>
                  <option value="USD">USD</option><option value="CNY">CNY</option>
                </select>
              </div>
            </div>
            <div className="field"><div className="field-label">状态</div>
              <select className="select" value={String(instanceForm.status ?? 'healthy')} onChange={(e) => setInstanceForm({ ...instanceForm, status: e.target.value })}>
                <option value="healthy">healthy</option><option value="high_load">high_load</option>
                <option value="circuit_open">circuit_open</option><option value="offline">offline</option>
              </select>
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-2)', justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setEditing(null)}>取消</button>
              <button className="btn btn-primary" onClick={saveInstance}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
