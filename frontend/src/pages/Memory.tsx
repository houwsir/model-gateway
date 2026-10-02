import { useCallback, useEffect, useState } from 'react';
import { memory } from '../api';
import type { MemoryMessageItem, MemoryPolicy, MemorySession, MemorySummary } from '../types';
import Panel from '../components/Panel';
import Badge from '../components/Badge';
import Switch from '../components/Switch';
import MetricCard from '../components/MetricCard';

export default function Memory() {
  const [summary, setSummary] = useState<MemorySummary | null>(null);
  const [policy, setPolicy] = useState<MemoryPolicy | null>(null);
  const [sessions, setSessions] = useState<MemorySession[]>([]);
  const [messages, setMessages] = useState<MemoryMessageItem[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [s, p, sess] = await Promise.all([memory.summary(), memory.policy(), memory.sessions(search)]);
      setSummary(s);
      setPolicy(p);
      setSessions(sess.items);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    }
  }, [search]);

  useEffect(() => {
    load();
  }, [load]);

  const openSession = async (sessionId: string) => {
    setSelectedSession(sessionId);
    const m = await memory.messages(sessionId);
    setMessages(m.items);
  };

  const togglePolicy = async (patch: Record<string, unknown>) => {
    const updated = await memory.updatePolicy(patch);
    setPolicy(updated);
  };

  const deleteSession = async (sessionId: string) => {
    await memory.deleteSession(sessionId);
    setSelectedSession(null);
    setMessages([]);
    await load();
  };

  return (
    <div className="content">
      <div className="page-head">
        <div>
          <div className="page-title">持久记忆</div>
          <div className="page-desc">会话上下文与历史状态的存储与复用，支撑多轮对话与长期记忆。</div>
        </div>
      </div>

      {error && <div className="badge badge-danger" style={{ alignSelf: 'flex-start' }}>{error}</div>}

      <div className="metrics" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
        <MetricCard label="活跃会话数" value={summary?.active_sessions ?? '—'} delta={`${summary?.active_delta_pct ?? 0}% 较昨日`} deltaUp tone="accent" />
        <MetricCard label="记忆存储量" value={summary?.storage_gb ?? '—'} unit="GB" delta={`${summary?.storage_delta_gb ?? 0}GB 本周新增`} deltaUp tone="info" />
        <MetricCard label="上下文命中率" value={summary?.context_hit_rate ?? '—'} unit="%" delta="检索质量良好" deltaUp tone="ok" />
      </div>

      <div className="grid-2">
        <Panel title="记忆策略配置" sub="分层存储与生命周期管理">
          <div className="field">
            <div className="field-label">热数据存储</div>
            <select className="select" value={policy?.hot_storage ?? 'memory'} onChange={(e) => togglePolicy({ hot_storage: e.target.value })}>
              <option value="memory">内存（当前会话上下文）</option>
              <option value="redis">Redis</option>
            </select>
            <div className="field-hint">低延迟读写，跨请求、跨实例可用</div>
          </div>
          <div className="field">
            <div className="field-label">冷数据存储</div>
            <select className="select" value={policy?.cold_storage ?? 'sqlite+vector'} onChange={(e) => togglePolicy({ cold_storage: e.target.value })}>
              <option value="sqlite+vector">SQLite + 向量（长期记忆）</option>
              <option value="object_only">仅对象存储</option>
            </select>
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <div className="field-label">会话上下文 TTL</div>
            <div className="weight-row">
              <div className="weight-track"><div className="weight-fill" style={{ width: '60%' }} /></div>
              <span className="weight-val">{Math.round((policy?.context_ttl_seconds ?? 86400) / 3600)}h</span>
            </div>
          </div>
        </Panel>

        <Panel title="数据合规" sub="记忆数据的合规与生命周期">
          <div className="weight-row" style={{ marginBottom: 'var(--sp-3)' }}><span className="weight-label" style={{ width: 'auto', flex: 1 }}>支持用户主动删除</span><Switch checked={policy?.user_delete_enabled ?? true} onChange={(v) => togglePolicy({ user_delete_enabled: v })} /></div>
          <div className="weight-row" style={{ marginBottom: 'var(--sp-3)' }}><span className="weight-label" style={{ width: 'auto', flex: 1 }}>PII 自动脱敏</span><Switch checked={policy?.pii_mask_enabled ?? true} onChange={(v) => togglePolicy({ pii_mask_enabled: v })} /></div>
          <div className="weight-row" style={{ marginBottom: 'var(--sp-3)' }}><span className="weight-label" style={{ width: 'auto', flex: 1 }}>到期自动清理</span><Switch checked={policy?.auto_expire_enabled ?? true} onChange={(v) => togglePolicy({ auto_expire_enabled: v })} /></div>
          <div className="weight-row"><span className="weight-label" style={{ width: 'auto', flex: 1 }}>审计留痕</span><Switch checked={policy?.audit_enabled ?? true} onChange={(v) => togglePolicy({ audit_enabled: v })} /></div>
        </Panel>
      </div>

      <Panel
        title="会话上下文"
        sub="活跃会话的上下文状态"
        actions={<input className="input" style={{ width: 220, padding: '8px 12px', fontSize: 13 }} placeholder="搜索会话 ID…" value={search} onChange={(e) => setSearch(e.target.value)} />}
      >
        <div style={{ paddingTop: 0 }}>
          <table className="table">
            <thead><tr><th>会话 ID</th><th>租户</th><th>消息数</th><th>上下文长度</th><th>最后活跃</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.session_id}>
                  <td className="cell-hi num" style={{ cursor: 'pointer' }} onClick={() => openSession(s.session_id)}>{s.session_id}</td>
                  <td>{s.tenant_name}</td>
                  <td className="num">{s.message_count}</td>
                  <td className="num">{(s.context_tokens / 1000).toFixed(1)}K token</td>
                  <td className="num">{s.last_active_at.slice(11, 19)}</td>
                  <td><Badge status={s.status} /></td>
                  <td><button className="btn btn-danger" style={{ padding: '5px 10px', fontSize: 12 }} onClick={() => deleteSession(s.session_id)}>删除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {selectedSession && (
        <Panel title={`会话消息 · ${selectedSession}`} sub="历史消息明细" actions={<button className="btn btn-ghost" onClick={() => setSelectedSession(null)}>关闭</button>}>
          <div className="alert-list">
            {messages.map((m) => (
              <div className="alert-item" key={m.id}>
                <div className="alert-ic info">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="9" /><path d="M12 8h.01M12 11v5" />
                  </svg>
                </div>
                <div className="alert-body">
                  <div className="alert-title">{m.role} · <span className="num">{m.tokens} tokens · {m.storage_tier}</span></div>
                  <div className="alert-desc">{m.content}</div>
                </div>
                <div className="alert-time">{m.created_at.slice(11, 19)}</div>
              </div>
            ))}
            {messages.length === 0 && <div className="empty">暂无消息</div>}
          </div>
        </Panel>
      )}
    </div>
  );
}
