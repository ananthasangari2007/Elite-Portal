import { useCallback, useEffect, useState } from "react";
import { api, ApiError, fetchMeta } from "./api";

export function useApi<T = any>(path: string | null, params?: Record<string, any>) {
  const [data, setData] = useState<T | null>(null);
  const [meta, setMeta] = useState<{ page: number; per_page: number; total: number; pages: number } | null>(null);
  const [loading, setLoading] = useState(!!path);
  const [error, setError] = useState<string | null>(null);

  const key = params ? JSON.stringify(params) : "";

  const load = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      if (params) {
        const res = await fetchMeta<T>(path, params);
        setData(res.data);
        setMeta(res.meta);
      } else {
        setData(await api.get<T>(path));
        setMeta(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [path, key]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, meta, loading, error, reload: load, setData };
}
