import { useCallback, useEffect, useState } from 'react';
import { balancing } from '../api';
import type { BalancingGroupDetail, InstanceNodeItem } from '../types';
import Panel from '../components/Panel';
import Badge from '../components/Badge';
import ProgressBar from '../components/ProgressBar';

const STRATEGY_LABELS: Record<string, string> = {
  weighted_least_conn: '加权最小连接',
  weighted_round_robin: '加权轮询',
  consistent_hash: '一致性哈希',
  random: '随机',
};

const PROVIDER_STRATEGY_LABELS: Record<string, string> = {
  quota_success_cost: '配额余量 + 成功率 + 成本',
  fixed_ratio: '固定比例',
  cost_first: '成本优先',
};

export default function Balancing() {
  const [detail, setDetail] = useState<BalancingGroupDetail | null>(null);
  const [nodes, setNodes] = useState<InstanceNodeItem[]>([]);
  const [strategy, setStrategy] = useState('weighted_least_conn');
  const [providerStrategy, setProviderStrategy] = useState('quota_success_cost');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [g, n] = await Promise.all([balancing.group(1), balancing.nodes()]);
      setDetail(g);
      setNodes(n.items);
      setStrategy(g.strategy);
      setProviderStrategy(g.provider_strategy);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const saveGroup = async () => {
    try {
      await balancing.updateGroup(1, { strategy, provider_strategy: providerStrategy });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    }
  };

  const drain = async (id: number) => {
    await balancing.drain(id);
    await load();
  };

  const recover = async (id: number) => {
    await balancing.recover(id);
    await load();
  };

  const totalWeight = (detail?.instance_weights ?? []).reduce((s, w) => s + w.weight, 0) || 1;

  return (
    <div className="content">
      <div className="page-head">
        <div>
          <div className="page-title">负载均衡</div>
          <div className="page-desc">在多个模型实例与可互换供应商间合理分配请求，均衡负载、避免单点过载。</div>
        </div>
        <div className="head-actions">
          <button className="btn btn-ghost" onClick={load}>刷新</button>
          <button className="btn btn-primary" onClick={saveGroup}>保存配置</button>
        </div>
      </div>

      {error && <div className="badge badge-danger" style={{ alignSelf: 'flex-start' }}>{error}</div>}

      <div className="grid-2">
        <Panel title="均衡组配置" sub="同一模型多实例的流量分配">
          <div className="field">
            <div className="field-label">均衡策略</div>
            <select className="select" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
              {Object.entries(STRATEGY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <div className="field-hint">根据实例实时连接数与健康度动态分配，优先负载低的实例</div>
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <div className="field-label">实例权重分配</div>
            {(detail?.instance_weights ?? []).map((w) => (
              <div className="weight-row" key={w.node}>
                <span className="weight-label">{w.node}</span>
                <div className="weight-track"><div className="weight-fill" style={{ width: `${(w.weight / totalWeight) * 100}%` }} /></div>
                <span className="weight-val">{Math.round((w.weight / totalWeight) * 100)}%</span>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="供应商级分流" sub="等价模型的跨供应商流量分配">
          <div className="field">
            <div className="field-label">分流依据</div>
            <select className="select" value={providerStrategy} onChange={(e) => setProviderStrategy(e.target.value)}>
              {Object.entries(PROVIDER_STRATEGY_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <div className="field-label">当前分流比例</div>
            {(detail?.provider_ratios ?? []).map((r) => (
              <div key={r.provider} style={{ marginBottom: 'var(--sp-2)' }}>
                <div className="weight-row">
                  <span className="weight-label" style={{ width: 'auto', flex: 1 }}>{r.provider}</span>
                  <span className="weight-val num" style={{ width: 'auto' }}>{r.ratio}%</span>
                </div>
                <ProgressBar value={r.ratio} tone="accent" style={{ marginTop: 4 }} />
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="实例健康与流量" sub="各实例实时接收的流量与健康状态">
        <div style={{ paddingTop: 0 }}>
          <table className="table">
            <thead><tr><th>实例</th><th>所属模型</th><th>当前连接</th><th>负载</th><th>健康</th><th>操作</th></tr></thead>
            <tbody>
              {nodes.map((n) => (
                <tr key={n.id}>
                  <td className="cell-hi num">{n.name}</td>
                  <td>{n.model}</td>
                  <td className="num">{n.current_connections}</td>
                  <td style={{ width: 120 }}>
                    <ProgressBar value={n.load} tone={n.load >= 80 ? 'warn' : 'ok'} />
                  </td>
                  <td><Badge status={n.status} /></td>
                  <td>
                    {n.status === 'draining' || n.status === 'circuit_open' ? (
                      <button className="btn btn-ghost" style={{ padding: '5px 10px', fontSize: 12 }} onClick={() => recover(n.id)}>恢复</button>
                    ) : (
                      <button className="btn btn-ghost" style={{ padding: '5px 10px', fontSize: 12 }} onClick={() => drain(n.id)}>摘流</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
