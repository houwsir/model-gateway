import { useCallback, useEffect, useState } from 'react';
import { alerts } from '../api';
import type { AlertItem, AlertRuleItem } from '../types';
import Panel from '../components/Panel';

type TabKey = 'open' | 'acknowledged' | 'recovered' | 'rules';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'open', label: '未处理' },
  { key: 'acknowledged', label: '已确认' },
  { key: 'recovered', label: '已恢复' },
  { key: 'rules', label: '告警规则' },
];

export default function Alerts() {
  const [tab, setTab] = useState<TabKey>('open');
  const [items, setItems] = useState<AlertItem[]>([]);
  const [rules, setRules] = useState<AlertRuleItem[]>([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [a, r] = await Promise.all([alerts.list(tab === 'rules' ? '' : tab), alerts.rules()]);
      setItems(a.items);
      setRules(r.items);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    }
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  const ack = async (id: number) => {
    await alerts.ack(id);
    await load();
  };
  const resolve = async (id: number) => {
    await alerts.resolve(id);
    await load();
  };
  const readAll = async () => {
    await alerts.readAll();
    await load();
  };

  return (
    <div className="content">
      <div className="page-head">
        <div>
          <div className="page-title">告警中心</div>
          <div className="page-desc">集中查看、确认与处理网关运行中的异常事件。</div>
        </div>
        <div className="head-actions">
          {tab === 'open' && (
            <button className="btn btn-ghost" onClick={readAll}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M9 12l2 2 4-4" /></svg>
              全部标记已读
            </button>
          )}
        </div>
      </div>

      {error && <div className="badge badge-danger" style={{ alignSelf: 'flex-start' }}>{error}</div>}

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.key} className={`tab${tab === t.key ? ' active' : ''}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab !== 'rules' ? (
        <div className="panel" style={{ marginTop: 'var(--sp-4)' }}>
          <div className="alert-list">
            {items.map((a) => (
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
                <span className={`badge badge-${a.severity === 'critical' ? 'danger' : a.severity === 'warning' ? 'warn' : 'info'}`} style={{ marginTop: 2 }}>
                  {a.severity === 'critical' ? '严重' : a.severity === 'warning' ? '警告' : '提示'}
                </span>
                {a.status === 'open' && (
                  <>
                    <button className="btn btn-ghost" style={{ padding: '5px 10px', fontSize: 12 }} onClick={() => ack(a.id)}>确认</button>
                    <button className="btn btn-primary" style={{ padding: '5px 10px', fontSize: 12 }} onClick={() => resolve(a.id)}>恢复</button>
                  </>
                )}
                <div className="alert-time">{a.created_at.slice(11, 19)}</div>
              </div>
            ))}
            {items.length === 0 && <div className="empty">暂无告警</div>}
          </div>
        </div>
      ) : (
        <Panel title="告警规则" sub="触发条件与告警级别" bodyStyle={{ paddingTop: 0 }}>
          <table className="table">
            <thead><tr><th>规则名</th><th>指标</th><th>阈值</th><th>级别</th></tr></thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id}>
                  <td className="cell-hi">{r.name}</td>
                  <td>{r.metric}</td>
                  <td className="num">{r.threshold}</td>
                  <td><span className={`badge badge-${r.severity === 'critical' ? 'danger' : r.severity === 'warning' ? 'warn' : 'info'}`}>{r.severity}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}
