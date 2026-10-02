import { useCallback, useEffect, useState } from 'react';
import { settings } from '../api';
import type { CredentialItem, SettingsData } from '../types';
import Panel from '../components/Panel';
import Switch from '../components/Switch';

export default function Settings() {
  const [data, setData] = useState<SettingsData | null>(null);
  const [credentials, setCredentials] = useState<CredentialItem[]>([]);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [editingCred, setEditingCred] = useState<CredentialItem | null>(null);
  const [credKey, setCredKey] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([settings.get(), settings.credentials()]);
      setData(s);
      setCredentials(c.items);
      setForm({
        default_timeout_s: s.default_timeout_s,
        first_token_timeout_s: s.first_token_timeout_s,
        billing_cycle: s.billing_cycle,
        tls_enabled: s.tls_enabled,
        prompt_injection_guard: s.prompt_injection_guard,
        audit_log_enabled: s.audit_log_enabled,
        exchange_rate_usd_cny: s.exchange_rate_usd_cny,
      });
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    try {
      await settings.update({
        default_timeout_s: Number(form.default_timeout_s),
        first_token_timeout_s: Number(form.first_token_timeout_s),
        billing_cycle: String(form.billing_cycle),
        tls_enabled: Boolean(form.tls_enabled),
        prompt_injection_guard: Boolean(form.prompt_injection_guard),
        audit_log_enabled: Boolean(form.audit_log_enabled),
        exchange_rate_usd_cny: Number(form.exchange_rate_usd_cny),
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    }
  };

  const saveCred = async () => {
    if (!editingCred) return;
    try {
      await settings.updateCredential(editingCred.provider_id, { api_key: credKey });
      setEditingCred(null);
      setCredKey('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    }
  };

  return (
    <div className="content">
      <div className="page-head">
        <div>
          <div className="page-title">系统设置</div>
          <div className="page-desc">网关全局配置、密钥托管与安全设置。</div>
        </div>
      </div>

      {error && <div className="badge badge-danger" style={{ alignSelf: 'flex-start' }}>{error}</div>}

      <div className="grid-2">
        <Panel title="密钥与凭据" sub="集中托管供应商 API 密钥">
          {credentials.map((c) => (
            <div className="field" key={c.provider_id}>
              <div className="field-label">{c.provider_name} API Key</div>
              <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
                <input className="input num" value={c.api_key_masked} disabled />
                <button className="btn btn-ghost" style={{ flex: 'none' }} onClick={() => { setEditingCred(c); setCredKey(''); }}>更新</button>
              </div>
              <div className="field-hint">已加密存储 · 仅网关后端可解密调用</div>
            </div>
          ))}
          <div className="field" style={{ marginBottom: 0 }}>
            <div className="field-label">安全策略</div>
            <div className="weight-row" style={{ marginBottom: 'var(--sp-2)' }}><span className="weight-label" style={{ width: 'auto', flex: 1 }}>传输加密（TLS）</span><Switch checked={Boolean(form.tls_enabled)} onChange={(v) => setForm({ ...form, tls_enabled: v })} /></div>
            <div className="weight-row" style={{ marginBottom: 'var(--sp-2)' }}><span className="weight-label" style={{ width: 'auto', flex: 1 }}>Prompt 注入防护</span><Switch checked={Boolean(form.prompt_injection_guard)} onChange={(v) => setForm({ ...form, prompt_injection_guard: v })} /></div>
            <div className="weight-row"><span className="weight-label" style={{ width: 'auto', flex: 1 }}>审计日志</span><Switch checked={Boolean(form.audit_log_enabled)} onChange={(v) => setForm({ ...form, audit_log_enabled: v })} /></div>
          </div>
        </Panel>

        <Panel title="全局参数" sub="网关运行的关键参数">
          <div className="field"><div className="field-label">默认超时时间（秒）</div>
            <input className="input num" type="number" value={Number(form.default_timeout_s ?? 30)} onChange={(e) => setForm({ ...form, default_timeout_s: Number(e.target.value) })} />
          </div>
          <div className="field"><div className="field-label">流式首 Token 超时（秒）</div>
            <input className="input num" type="number" value={Number(form.first_token_timeout_s ?? 5)} onChange={(e) => setForm({ ...form, first_token_timeout_s: Number(e.target.value) })} />
          </div>
          <div className="field"><div className="field-label">计量计费周期</div>
            <select className="select" value={String(form.billing_cycle ?? 'daily')} onChange={(e) => setForm({ ...form, billing_cycle: e.target.value })}>
              <option value="daily">每日对账</option>
              <option value="realtime">实时计量</option>
            </select>
          </div>
          <div className="field"><div className="field-label">USD/CNY 汇率</div>
            <input className="input num" type="number" step="0.1" value={Number(form.exchange_rate_usd_cny ?? 7.2)} onChange={(e) => setForm({ ...form, exchange_rate_usd_cny: Number(e.target.value) })} />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <button className="btn btn-primary" onClick={save}>保存设置</button>
          </div>
        </Panel>
      </div>

      {editingCred && (
        <div className="modal-mask" onClick={() => setEditingCred(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="page-title" style={{ fontSize: 18, marginBottom: 'var(--sp-4)' }}>更新 {editingCred.provider_name} API Key</div>
            <div className="field"><div className="field-label">新 API Key</div>
              <input className="input" value={credKey} onChange={(e) => setCredKey(e.target.value)} />
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-2)', justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setEditingCred(null)}>取消</button>
              <button className="btn btn-primary" onClick={saveCred}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
