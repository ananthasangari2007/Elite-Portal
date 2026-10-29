import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, fetchMeta } from "./api";

type Meta = { page: number; per_page: number; total: number; pages: number };

type CacheEntry<T> = {
  data: T;
  meta: Meta | null;
  timestamp: number;
};

const CACHE_TTL_MS = 10_000;
const apiCache = new Map<string, CacheEntry<any>>();

export function invalidateCache(prefix?: string) {
  if (!prefix) {
    apiCache.clear();
    return;
  }
  for (const key of apiCache.keys()) {
    if (key.startsWith(prefix)) apiCache.delete(key);
  }
}

export function useApi<T = any>(path: string | null, params?: Record<string, any>) {
  const cacheKey = path ? `${path}?${params ? JSON.stringify(params) : ""}` : null;
  const cached = cacheKey ? apiCache.get(cacheKey) : undefined;

  const [data, setData] = useState<T | null>(cached ? cached.data : null);
  const [meta, setMeta] = useState<Meta | null>(cached ? cached.meta : null);
  const [loading, setLoading] = useState(!!path && !cached);
  const [error, setError] = useState<string | null>(null);

  // Latest params without making `load` depend on a new object identity every render.
  const paramsRef = useRef(params);
  paramsRef.current = params;
  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback(
    async (bypassCache = false) => {
      if (!path || !cacheKey) {
        setLoading(false);
        return;
      }
      const entry = apiCache.get(cacheKey);
      if (!bypassCache && entry && Date.now() - entry.timestamp < CACHE_TTL_MS) {
        setData(entry.data);
        setMeta(entry.meta);
        setError(null);
        setLoading(false);
        return;
      }

      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      if (!entry) setLoading(true);
      setError(null);
      try {
        let nextData: T;
        let nextMeta: Meta | null = null;
        if (paramsRef.current) {
          const res = await fetchMeta<T>(path, paramsRef.current, controller.signal);
          nextData = res.data;
          nextMeta = res.meta ?? null;
        } else {
          nextData = await api.get<T>(path, undefined, controller.signal);
        }
        if (controller.signal.aborted) return;
        apiCache.set(cacheKey, { data: nextData, meta: nextMeta, timestamp: Date.now() });
        setData(nextData);
        setMeta(nextMeta);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "Failed to load data");
      } finally {
        // Always leave the loading state, even on failure (no permanent spinners).
        if (!controller.signal.aborted) setLoading(false);
      }
    },
    [path, cacheKey]
  );

  useEffect(() => {
    load();
    return () => controllerRef.current?.abort();
  }, [load]);

  const reload = useCallback(() => load(true), [load]);

  return { data, meta, loading, error, reload, setData };
}
