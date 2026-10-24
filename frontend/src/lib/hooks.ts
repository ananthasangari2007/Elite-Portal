import { useCallback, useEffect, useState } from "react";
import { api, ApiError, fetchMeta } from "./api";

type CacheEntry<T> = {
  data: T;
  meta: any;
  timestamp: number;
};

const apiCache = new Map<string, CacheEntry<any>>();

export function invalidateCache(prefix?: string) {
  if (!prefix) {
    apiCache.clear();
    return;
  }
  for (const key of apiCache.keys()) {
    if (key.startsWith(prefix)) {
      apiCache.delete(key);
    }
  }
}

export function useApi<T = any>(path: string | null, params?: Record<string, any>) {
  const cacheKey = path ? `${path}?${params ? JSON.stringify(params) : ""}` : null;
  const cached = cacheKey ? apiCache.get(cacheKey) : null;

  const [data, setData] = useState<T | null>(cached ? cached.data : null);
  const [meta, setMeta] = useState<{ page: number; per_page: number; total: number; pages: number } | null>(
    cached ? cached.meta : null
  );
  const [loading, setLoading] = useState(!!path && !cached);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (bypassCache = false) => {
      if (!path || !cacheKey) return;

      const entry = apiCache.get(cacheKey);
      if (!bypassCache && entry && Date.now() - entry.timestamp < 10_000) {
        setData(entry.data);
        setMeta(entry.meta);
        setLoading(false);
        return;
      }

      if (!entry) {
        setLoading(true);
      }
      setError(null);

      try {
        let nextData: T;
        let nextMeta: any = null;
        if (params) {
          const res = await fetchMeta<T>(path, params);
          nextData = res.data;
          nextMeta = res.meta;
        } else {
          nextData = await api.get<T>(path);
        }
        apiCache.set(cacheKey, { data: nextData, meta: nextMeta, timestamp: Date.now() });
        setData(nextData);
        setMeta(nextMeta);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    },
    [path, cacheKey]
  );

  useEffect(() => {
    if (cacheKey) {
      const existing = apiCache.get(cacheKey);
      if (existing) {
        setData(existing.data);
        setMeta(existing.meta);
        setLoading(false);
      } else {
        setLoading(true);
      }
    }
    load();
  }, [load, cacheKey]);

  const reload = useCallback(() => load(true), [load]);

  return { data, meta, loading, error, reload, setData };
}
