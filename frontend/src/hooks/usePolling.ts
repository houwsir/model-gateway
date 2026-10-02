import { useCallback, useEffect, useRef, useState } from 'react';

// 轮询 hook：监控类页面默认 3s 轮询；配置类页面可传 null 表示只加载一次
export function usePolling<T>(
  fn: () => Promise<T>,
  intervalMs: number | null = 3000,
): { data: T | null; loading: boolean; error: string | null; refresh: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const load = useCallback(async () => {
    try {
      const result = await fnRef.current();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const run = async () => {
      try {
        const result = await fnRef.current();
        if (active) {
          setData(result);
          setError(null);
          setLoading(false);
        }
      } catch (e) {
        if (active) {
          setError(e instanceof Error ? e.message : '加载失败');
          setLoading(false);
        }
      }
    };
    run();
    let id: ReturnType<typeof setInterval> | undefined;
    if (intervalMs !== null) {
      id = setInterval(run, intervalMs);
    }
    return () => {
      active = false;
      if (id) clearInterval(id);
    };
  }, [intervalMs]);

  return { data, loading, error, refresh: load };
}
