"use client";

import { useState, useEffect, useCallback } from "react";

interface UseApiResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refetch: () => void;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  autoRefreshMs?: number,
): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(() => {
    setLoading(true);
    setError(null);
    fetcher()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    refetch();
  }, [refetch]);

  useEffect(() => {
    if (!autoRefreshMs) return;
    const id = setInterval(refetch, autoRefreshMs);
    return () => clearInterval(id);
  }, [refetch, autoRefreshMs]);

  return { data, error, loading, refetch };
}
