import axios, { AxiosError } from 'axios';

// axios 实例：统一响应 envelope 解析
// 后端 Base URL /api/v1，前端经 Vite 代理 /api -> http://localhost:8000
const client = axios.create({
  baseURL: '/api/v1',
  timeout: 20000,
});

client.interceptors.response.use(
  (response) => {
    const body = response.data;
    // 统一响应包 {code, message, data}
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) {
        return body.data;
      }
      const err = new Error(body.message || '请求失败') as Error & { code?: number };
      err.code = body.code;
      return Promise.reject(err);
    }
    return body;
  },
  (error: AxiosError) => {
    const data = error.response?.data as { message?: string; code?: number } | undefined;
    const message = data?.message || error.message || '网络请求失败';
    const err = new Error(message) as Error & { code?: number };
    err.code = data?.code;
    return Promise.reject(err);
  },
);

export default client;
