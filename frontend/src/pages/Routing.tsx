import { useCallback, useEffect, useState } from 'react';
import { routing } from '../api';
import type { RoutePolicyItem, RouteRuleItem } from '../types';
import Panel from '../components/Panel';
import Switch from '../components/Switch';

export default function Routing() {
  const [policies, setPolicies] = useState<RoutePolicyItem[]>([]);
  const [rules, setRules] = useState<RouteRuleItem[]>([]);
  const [showPolicyForm, setShowPolicyForm] = useState(false);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [error, setError] = useState('');

  const [policyForm, setPolicyForm] = useState({
    name: '',
    scenario_tag: 'default',
    weight_cost: 0.4,
    weight_latency: 0.35,
    weight_quality: 0.25,
    exploration_rate: 0.05,
    is_default: false,
    status: 'enabled',
  });

  const [ruleForm, setRuleForm] = useState({
    name: '',
    rule_type: 'capability',
    action: 'exclude',
    priority: 1,
    field: 'p95_latency',
    operator: 'gt',
    value: '800',
  });

  const load = useCallback(async () => {
    try {
      const [p, r] = await Promise.all([routing.policies(), routing.rules()]);
      setPolicies(p.items);
      setRules(r.items);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const toggleRule = async (rule: RouteRuleItem, enabled: boolean) => {
    await routing.updateRule(rule.id, { enabled });
    await load();
  };

  const deleteRule = async (id: number) => {
    await routing.deleteRule(id);
    await load();
  };

  const createPolicy = async () => {
    try {
      await routing.createPolicy(policyForm as unknown as Record<string, unknown>);
      setShowPolicyForm(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建失败');
    }
  };

  const createRule = async () => {
    try {
      await routing.createRule({
        name: ruleForm.name,
        rule_type: ruleForm.rule_type,
        condition: { field: ruleForm.field, operator: ruleForm.operator, value: isNaN(Number(ruleForm.value)) ? ruleForm.value : Number(ruleForm.value) },
        action: ruleForm.action,
        priority: ruleForm.priority,
      });
      setShowRuleForm(false);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建失败');
    }
  };

  return (
    <div className="content">
      <div className="page-head">
        <div>
          <div className="page-title">智能路由</div>
          <div className="page-desc">按能力、成本、延迟动态选择最优模型。规则过滤 + 加权打分两段式策略，权重可按业务场景定制。</div>
        </div>
        <div className="head-actions">
          <button className="btn btn-primary" onClick={() => setShowPolicyForm(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg>
            新建路由策略
          </button>
        </div>
      </div>

      {error && <div className="badge badge-danger" style={{ alignSelf: 'flex-start' }}>{error}</div>}

      <div className="grid-3">
        {policies.map((p) => (
          <div className="route-card" key={p.id}>
            <div className="route-card-head">
              <span className="route-name">{p.name}</span>
              <span className="route-tag">{p.tag_label}</span>
              {p.is_default && <span className="badge badge-ok">默认</span>}
            </div>
            <div className="weight-row">
              <span className="weight-label">成本权重</span>
              <div className="weight-track"><div className="weight-fill" style={{ width: `${p.weight_cost * 100}%` }} /></div>
              <span className="weight-val">{p.weight_cost}</span>
            </div>
            <div className="weight-row">
              <span className="weight-label">延迟权重</span>
              <div className="weight-track"><div className="weight-fill" style={{ width: `${p.weight_latency * 100}%` }} /></div>
              <span className="weight-val">{p.weight_latency}</span>
            </div>
            <div className="weight-row">
              <span className="weight-label">质量权重</span>
              <div className="weight-track"><div className="weight-fill" style={{ width: `${p.weight_quality * 100}%` }} /></div>
              <span className="weight-val">{p.weight_quality}</span>
            </div>
            <div className="divider" />
            <div style={{ fontSize: 12, color: 'var(--text-low)' }}>
              候选模型 {p.candidate_count} 个 · 命中率 {p.hit_rate}% · 探索率 {p.exploration_rate}
            </div>
          </div>
        ))}
      </div>

      <Panel
        title="路由规则明细"
        sub="硬性过滤规则，不满足即排除候选"
        actions={
          <button className="btn btn-ghost" onClick={() => setShowRuleForm(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg>
            添加规则
          </button>
        }
      >
        <div style={{ paddingTop: 0 }}>
          <table className="table">
            <thead><tr><th>规则名</th><th>条件</th><th>动作</th><th>优先级</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id}>
                  <td className="cell-hi">{r.name}</td>
                  <td>{`${String(r.condition.field ?? '')} ${String(r.condition.operator ?? '')} ${String(r.condition.value ?? '')}`}</td>
                  <td>{r.action}</td>
                  <td className="num">{r.priority}</td>
                  <td><Switch checked={r.enabled} onChange={(v) => toggleRule(r, v)} /></td>
                  <td><button className="btn btn-danger" style={{ padding: '5px 10px', fontSize: 12 }} onClick={() => deleteRule(r.id)}>删除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {showPolicyForm && (
        <div className="modal-mask" onClick={() => setShowPolicyForm(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="page-title" style={{ fontSize: 18, marginBottom: 'var(--sp-4)' }}>新建路由策略</div>
            <div className="field"><div className="field-label">名称</div>
              <input className="input" value={policyForm.name} onChange={(e) => setPolicyForm({ ...policyForm, name: e.target.value })} />
            </div>
            <div className="field"><div className="field-label">场景标签</div>
              <select className="select" value={policyForm.scenario_tag} onChange={(e) => setPolicyForm({ ...policyForm, scenario_tag: e.target.value })}>
                <option value="default">default</option><option value="realtime">realtime</option><option value="quality">quality</option>
              </select>
            </div>
            <div className="grid-3" style={{ gap: 'var(--sp-3)' }}>
              {(['weight_cost', 'weight_latency', 'weight_quality'] as const).map((k) => (
                <div className="field" key={k}><div className="field-label">{k}</div>
                  <input className="input num" type="number" step="0.05" value={policyForm[k]} onChange={(e) => setPolicyForm({ ...policyForm, [k]: Number(e.target.value) })} />
                </div>
              ))}
            </div>
            <div className="field"><div className="field-label">探索率</div>
              <input className="input num" type="number" step="0.01" value={policyForm.exploration_rate} onChange={(e) => setPolicyForm({ ...policyForm, exploration_rate: Number(e.target.value) })} />
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-2)', justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setShowPolicyForm(false)}>取消</button>
              <button className="btn btn-primary" onClick={createPolicy}>创建</button>
            </div>
          </div>
        </div>
      )}

      {showRuleForm && (
        <div className="modal-mask" onClick={() => setShowRuleForm(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="page-title" style={{ fontSize: 18, marginBottom: 'var(--sp-4)' }}>添加路由规则</div>
            <div className="grid-2" style={{ gap: 'var(--sp-3)' }}>
              <div className="field"><div className="field-label">规则名</div>
                <input className="input" value={ruleForm.name} onChange={(e) => setRuleForm({ ...ruleForm, name: e.target.value })} />
              </div>
              <div className="field"><div className="field-label">类型</div>
                <select className="select" value={ruleForm.rule_type} onChange={(e) => setRuleForm({ ...ruleForm, rule_type: e.target.value })}>
                  <option value="capability">capability</option><option value="cost">cost</option>
                  <option value="quota">quota</option><option value="latency">latency</option>
                </select>
              </div>
            </div>
            <div className="grid-3" style={{ gap: 'var(--sp-3)' }}>
              <div className="field"><div className="field-label">条件字段</div>
                <input className="input" value={ruleForm.field} onChange={(e) => setRuleForm({ ...ruleForm, field: e.target.value })} />
              </div>
              <div className="field"><div className="field-label">操作符</div>
                <select className="select" value={ruleForm.operator} onChange={(e) => setRuleForm({ ...ruleForm, operator: e.target.value })}>
                  <option value="eq">eq</option><option value="gt">gt</option><option value="lt">lt</option>
                  <option value="gte">gte</option><option value="lte">lte</option>
                </select>
              </div>
              <div className="field"><div className="field-label">值</div>
                <input className="input" value={ruleForm.value} onChange={(e) => setRuleForm({ ...ruleForm, value: e.target.value })} />
              </div>
            </div>
            <div className="grid-2" style={{ gap: 'var(--sp-3)' }}>
              <div className="field"><div className="field-label">动作</div>
                <input className="input" value={ruleForm.action} onChange={(e) => setRuleForm({ ...ruleForm, action: e.target.value })} />
              </div>
              <div className="field"><div className="field-label">优先级</div>
                <input className="input num" type="number" value={ruleForm.priority} onChange={(e) => setRuleForm({ ...ruleForm, priority: Number(e.target.value) })} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-2)', justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setShowRuleForm(false)}>取消</button>
              <button className="btn btn-primary" onClick={createRule}>创建</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
