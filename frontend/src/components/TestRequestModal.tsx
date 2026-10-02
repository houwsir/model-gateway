import { useState } from 'react';
import { chatCompletions, chatCompletionsStream } from '../api';
import type { ChatResponseData } from '../types';

// 种子 API Key（README 同步列出），供测试 chat 接口
const DEFAULT_API_KEY = 'gw_a1b2c3d4e5f60718293a4b5c6d7e8f90';

interface TestRequestModalProps {
  onClose: () => void;
}

export default function TestRequestModal({ onClose }: TestRequestModalProps) {
  const [apiKey, setApiKey] = useState(DEFAULT_API_KEY);
  const [model, setModel] = useState('');
  const [content, setContent] = useState('你好，介绍一下你自己');
  const [scenario, setScenario] = useState('default');
  const [priority, setPriority] = useState('P1');
  const [sessionId, setSessionId] = useState('');
  const [stream, setStream] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string>('');
  const [meta, setMeta] = useState<string>('');
  const [error, setError] = useState<string>('');

  const run = async () => {
    setLoading(true);
    setResult('');
    setMeta('');
    setError('');
    try {
      const body = {
        model: model || undefined,
        messages: [{ role: 'user', content }],
        stream,
        session_id: sessionId || undefined,
        priority,
        scenario_tag: scenario,
        capabilities: ['text'],
        temperature: 0.7,
        max_tokens: 512,
      };
      if (stream) {
        const parts: string[] = [];
        await chatCompletionsStream(body, apiKey, (event) => {
          if (event.type === 'start') {
            setMeta(`模型 ${event.model} · 供应商 ${event.provider} · 实例 ${event.instance}`);
          } else if (event.type === 'delta') {
            parts.push(String(event.content || ''));
            setResult(parts.join(''));
          } else if (event.type === 'done') {
            setMeta((m) => `${m} · cost $${event.cost} · latency ${event.latency_ms}ms`);
          } else if (event.type === 'error') {
            setError(String(event.message || '流式错误'));
          }
        });
      } else {
        const data = (await chatCompletions(body, apiKey)) as ChatResponseData;
        setResult(data.content);
        setMeta(
          `模型 ${data.model} · 供应商 ${data.provider} · 策略 ${data.route_policy ?? '-'} · cost $${data.cost} · latency ${data.latency_ms}ms · memory_saved ${data.memory_saved}`,
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '请求失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-mask" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="page-head" style={{ marginBottom: 'var(--sp-4)' }}>
          <div>
            <div className="page-title" style={{ fontSize: 18 }}>
              新建请求
            </div>
            <div className="page-desc">调用网关统一入口 POST /chat/completions，走通全链路</div>
          </div>
          <button className="btn btn-ghost" onClick={onClose}>
            关闭
          </button>
        </div>

        <div className="field">
          <div className="field-label">API Key（X-API-Key）</div>
          <input className="input num" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
        </div>

        <div className="grid-2" style={{ gap: 'var(--sp-3)' }}>
          <div className="field">
            <div className="field-label">模型（留空自动路由）</div>
            <input className="input" placeholder="gpt-4o-mini" value={model} onChange={(e) => setModel(e.target.value)} />
          </div>
          <div className="field">
            <div className="field-label">会话 ID（可选，持久记忆）</div>
            <input className="input" placeholder="sess_9f2a1c" value={sessionId} onChange={(e) => setSessionId(e.target.value)} />
          </div>
        </div>

        <div className="grid-3" style={{ gap: 'var(--sp-3)' }}>
          <div className="field">
            <div className="field-label">场景标签</div>
            <select className="select" value={scenario} onChange={(e) => setScenario(e.target.value)}>
              <option value="default">default · 默认</option>
              <option value="realtime">realtime · 高优时延</option>
              <option value="quality">quality · 高优质量</option>
            </select>
          </div>
          <div className="field">
            <div className="field-label">优先级</div>
            <select className="select" value={priority} onChange={(e) => setPriority(e.target.value)}>
              <option value="P0">P0</option>
              <option value="P1">P1</option>
              <option value="P2">P2</option>
              <option value="P3">P3</option>
            </select>
          </div>
          <div className="field">
            <div className="field-label">流式（SSE）</div>
            <label className="switch" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={stream} onChange={(e) => setStream(e.target.checked)} />
              <span className="track">
                <span className="thumb" />
              </span>
            </label>
          </div>
        </div>

        <div className="field">
          <div className="field-label">消息内容</div>
          <textarea className="input" rows={3} value={content} onChange={(e) => setContent(e.target.value)} style={{ resize: 'vertical' }} />
        </div>

        <div style={{ display: 'flex', gap: 'var(--sp-2)', justifyContent: 'flex-end' }}>
          <button className="btn btn-primary" onClick={run} disabled={loading}>
            {loading ? '请求中…' : '发送请求'}
          </button>
        </div>

        {error && (
          <div className="alert-item" style={{ marginTop: 'var(--sp-4)' }}>
            <div className="alert-ic crit">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 9v4M12 17h.01" />
                <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
              </svg>
            </div>
            <div className="alert-body">
              <div className="alert-title">请求失败</div>
              <div className="alert-desc">{error}</div>
            </div>
          </div>
        )}

        {result && (
          <div className="panel" style={{ marginTop: 'var(--sp-4)' }}>
            <div className="panel-head">
              <div>
                <div className="panel-title">响应内容</div>
                {meta && <div className="panel-sub">{meta}</div>}
              </div>
            </div>
            <div className="panel-body">
              <div style={{ whiteSpace: 'pre-wrap', color: 'var(--text-mid)', fontSize: 13 }}>{result}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
