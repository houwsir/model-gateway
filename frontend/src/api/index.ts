import client from './client';
import type {
  AlertItem,
  AlertRuleItem,
  BalancingGroupDetail,
  BalancingGroupItem,
  ChatRequest,
  ChatResponseData,
  CostItem,
  CredentialItem,
  InstanceNodeItem,
  InstanceWeight,
  ListData,
  MemoryMessageItem,
  MemoryPolicy,
  MemorySession,
  MemorySummary,
  ModelHealthItem,
  ModelInstanceItem,
  OverviewSummary,
  PriorityQueueItem,
  ProviderItem,
  RateLimitItem,
  ResiliencePolicyItem,
  RoutePolicyItem,
  RouteRuleItem,
  SettingsData,
  TenantQuotaItem,
  TrafficPoint,
  TrafficSummary,
} from '../types';

// axios 拦截器已解包 envelope，故此处返回值即 data

// ---------- 业务转发 ----------
export async function chatCompletions(body: ChatRequest, apiKey?: string): Promise<ChatResponseData> {
  const headers = apiKey ? { 'X-API-Key': apiKey } : undefined;
  return client.post('/chat/completions', body, { headers }) as unknown as Promise<ChatResponseData>;
}

// SSE 流式（原生 fetch，逐事件回调）
export async function chatCompletionsStream(
  body: ChatRequest,
  apiKey: string,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<void> {
  const resp = await fetch('/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
    },
    body: JSON.stringify({ ...body, stream: true }),
  });
  if (!resp.ok || !resp.body) {
    const text = await resp.text();
    throw new Error(text || `请求失败 (${resp.status})`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop() || '';
    for (const chunk of lines) {
      const line = chunk.trim();
      if (!line.startsWith('data:')) continue;
      const payload = line.slice(5).trim();
      if (payload === '[DONE]') continue;
      try {
        onEvent(JSON.parse(payload));
      } catch {
        // 忽略非 JSON 事件
      }
    }
  }
}

// ---------- 监控大盘 ----------
export const overview = {
  summary: () => client.get('/overview/summary') as unknown as Promise<OverviewSummary>,
  trafficTrend: (window = '24h') =>
    client.get('/overview/traffic-trend', { params: { window } }) as unknown as Promise<{
      points: TrafficPoint[];
    }>,
  modelHealth: () => client.get('/overview/model-health') as unknown as Promise<ListData<ModelHealthItem>>,
  recentAlerts: (limit = 3) =>
    client.get('/overview/recent-alerts', { params: { limit } }) as unknown as Promise<ListData<AlertItem>>,
  costDistribution: () => client.get('/overview/cost-distribution') as unknown as Promise<ListData<CostItem>>,
};

// ---------- 智能路由 ----------
export const routing = {
  policies: () => client.get('/routing/policies') as unknown as Promise<ListData<RoutePolicyItem>>,
  createPolicy: (body: Record<string, unknown>) => client.post('/routing/policies', body) as unknown as Promise<RoutePolicyItem>,
  updatePolicy: (id: number, body: Record<string, unknown>) =>
    client.put(`/routing/policies/${id}`, body) as unknown as Promise<RoutePolicyItem>,
  deletePolicy: (id: number) => client.delete(`/routing/policies/${id}`),
  rules: () => client.get('/routing/rules') as unknown as Promise<ListData<RouteRuleItem>>,
  createRule: (body: Record<string, unknown>) => client.post('/routing/rules', body) as unknown as Promise<RouteRuleItem>,
  updateRule: (id: number, body: Record<string, unknown>) =>
    client.put(`/routing/rules/${id}`, body) as unknown as Promise<RouteRuleItem>,
  deleteRule: (id: number) => client.delete(`/routing/rules/${id}`),
  preview: (body: Record<string, unknown>) =>
    client.post('/routing/preview', body) as unknown as Promise<{
      selected_model: string | null;
      candidates: { model: string; score: number }[];
      filtered_out: string[];
    }>,
};

// ---------- 供应商 ----------
export const providers = {
  list: () => client.get('/providers') as unknown as Promise<ListData<ProviderItem>>,
  create: (body: Record<string, unknown>) => client.post('/providers', body) as unknown as Promise<ProviderItem>,
  update: (id: number, body: Record<string, unknown>) =>
    client.put(`/providers/${id}`, body) as unknown as Promise<ProviderItem>,
  remove: (id: number) => client.delete(`/providers/${id}`),
  instances: (providerId?: number) =>
    client.get('/model-instances', { params: providerId ? { provider_id: providerId } : {} }) as unknown as Promise<
      ListData<ModelInstanceItem>
    >,
  createInstance: (body: Record<string, unknown>) =>
    client.post('/model-instances', body) as unknown as Promise<ModelInstanceItem>,
  updateInstance: (id: number, body: Record<string, unknown>) =>
    client.put(`/model-instances/${id}`, body) as unknown as Promise<ModelInstanceItem>,
  removeInstance: (id: number) => client.delete(`/model-instances/${id}`),
};

// ---------- 负载均衡 ----------
export const balancing = {
  groups: () => client.get('/balancing/groups') as unknown as Promise<ListData<BalancingGroupItem>>,
  group: (id: number) => client.get(`/balancing/groups/${id}`) as unknown as Promise<BalancingGroupDetail>,
  updateGroup: (id: number, body: { strategy?: string; provider_strategy?: string; instance_weights?: InstanceWeight[] }) =>
    client.put(`/balancing/groups/${id}`, body) as unknown as Promise<BalancingGroupDetail>,
  nodes: () => client.get('/balancing/nodes') as unknown as Promise<ListData<InstanceNodeItem>>,
  drain: (id: number) => client.post(`/balancing/nodes/${id}/drain`) as unknown as Promise<InstanceNodeItem>,
  recover: (id: number) => client.post(`/balancing/nodes/${id}/recover`) as unknown as Promise<InstanceNodeItem>,
};

// ---------- 流量控制 ----------
export const traffic = {
  summary: () => client.get('/traffic/summary') as unknown as Promise<TrafficSummary>,
  rateLimits: () => client.get('/traffic/rate-limits') as unknown as Promise<ListData<RateLimitItem>>,
  createRateLimit: (body: Record<string, unknown>) =>
    client.post('/traffic/rate-limits', body) as unknown as Promise<RateLimitItem>,
  updateRateLimit: (id: number, body: Record<string, unknown>) =>
    client.put(`/traffic/rate-limits/${id}`, body) as unknown as Promise<RateLimitItem>,
  deleteRateLimit: (id: number) => client.delete(`/traffic/rate-limits/${id}`),
  priorityQueues: () => client.get('/traffic/priority-queues') as unknown as Promise<ListData<PriorityQueueItem>>,
  tenantQuotas: () => client.get('/traffic/tenant-quotas') as unknown as Promise<ListData<TenantQuotaItem>>,
  updateTenantQuota: (tenantId: number, body: Record<string, unknown>) =>
    client.put(`/traffic/tenant-quotas/${tenantId}`, body) as unknown as Promise<TenantQuotaItem>,
};

// ---------- 持久记忆 ----------
export const memory = {
  summary: () => client.get('/memory/summary') as unknown as Promise<MemorySummary>,
  policy: () => client.get('/memory/policy') as unknown as Promise<MemoryPolicy>,
  updatePolicy: (body: Record<string, unknown>) => client.put('/memory/policy', body) as unknown as Promise<MemoryPolicy>,
  sessions: (search = '') =>
    client.get('/memory/sessions', { params: { search } }) as unknown as Promise<ListData<MemorySession>>,
  messages: (sessionId: string) =>
    client.get(`/memory/sessions/${sessionId}/messages`) as unknown as Promise<ListData<MemoryMessageItem>>,
  deleteSession: (sessionId: string) => client.delete(`/memory/sessions/${sessionId}`),
};

// ---------- 容灾 ----------
export const resilience = {
  policies: () => client.get('/resilience/policies') as unknown as Promise<ListData<ResiliencePolicyItem>>,
  createPolicy: (body: Record<string, unknown>) =>
    client.post('/resilience/policies', body) as unknown as Promise<ResiliencePolicyItem>,
  updatePolicy: (id: number, body: Record<string, unknown>) =>
    client.put(`/resilience/policies/${id}`, body) as unknown as Promise<ResiliencePolicyItem>,
};

// ---------- 告警 ----------
export const alerts = {
  list: (status = '', severity = '', limit = 100) =>
    client.get('/alerts', { params: { status, severity, limit } }) as unknown as Promise<ListData<AlertItem> & { total: number }>,
  ack: (id: number) => client.post(`/alerts/${id}/ack`) as unknown as Promise<AlertItem>,
  resolve: (id: number) => client.post(`/alerts/${id}/resolve`) as unknown as Promise<AlertItem>,
  readAll: () => client.post('/alerts/read-all'),
  rules: () => client.get('/alerts/rules') as unknown as Promise<ListData<AlertRuleItem>>,
  createRule: (body: Record<string, unknown>) => client.post('/alerts/rules', body) as unknown as Promise<AlertRuleItem>,
};

// ---------- 设置 ----------
export const settings = {
  get: () => client.get('/settings') as unknown as Promise<SettingsData>,
  update: (body: Record<string, unknown>) => client.put('/settings', body) as unknown as Promise<SettingsData>,
  credentials: () => client.get('/settings/credentials') as unknown as Promise<ListData<CredentialItem>>,
  updateCredential: (providerId: number, body: { api_key: string }) =>
    client.put(`/settings/credentials/${providerId}`, body) as unknown as Promise<CredentialItem>,
};

export const health = () => client.get('/health') as unknown as Promise<{ status: string; version: string }>;
