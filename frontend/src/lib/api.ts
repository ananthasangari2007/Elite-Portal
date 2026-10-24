export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;

  constructor(message: string, status: number, code: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const TOKEN_KEY = "elite_auth_token";

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token: string | null) {
  try {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    // Ignore localStorage availability errors
  }
}

let csrfToken: string | null = null;
let csrfPromise: Promise<string> | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
  csrfPromise = null;
}

export function clearCsrf() {
  csrfToken = null;
  csrfPromise = null;
}

type Options = {
  method?: string;
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined | null>;
  formData?: FormData;
  signal?: AbortSignal;
};

export function buildUrl(path: string, params?: Options["params"]): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  let url: URL;

  if (API_BASE.startsWith("http://") || API_BASE.startsWith("https://")) {
    url = new URL(`${API_BASE.replace(/\/+$/, "")}${cleanPath}`);
  } else {
    const cleanBase = API_BASE.startsWith("/") ? API_BASE : `/${API_BASE}`;
    url = new URL(`${cleanBase.replace(/\/+$/, "")}${cleanPath}`, window.location.origin);
  }

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }

  // If API_BASE is relative, return relative pathname + search for Vite proxy and direct SPA compatibility
  if (!API_BASE.startsWith("http://") && !API_BASE.startsWith("https://")) {
    return url.pathname + url.search;
  }
  return url.toString();
}

export async function ensureCsrf(force = false): Promise<string> {
  if (csrfToken && !force) return csrfToken;
  if (csrfPromise && !force) return csrfPromise;

  csrfPromise = (async () => {
    try {
      const headers: Record<string, string> = {};
      const token = getStoredToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const res = await fetch(buildUrl("/auth/csrf"), {
        credentials: "include",
        headers,
      });
      if (!res.ok) throw new ApiError("Could not initialise a secure session.", res.status, "csrf_init_failed");
      const body = await res.json();
      csrfToken = (body?.data?.csrf_token as string) || null;
      return csrfToken || "";
    } finally {
      csrfPromise = null;
    }
  })();

  return csrfPromise;
}

// In-flight GET promise deduplication cache to prevent duplicate network calls
const inFlightGets = new Map<string, Promise<any>>();

export async function request<T = any>(path: string, options: Options = {}, isRetry = false): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const url = buildUrl(path, options.params);

  // Deduplicate concurrent in-flight GET requests
  if (method === "GET" && !options.formData && !isRetry) {
    const existing = inFlightGets.get(url);
    if (existing) {
      return existing;
    }
  }

  const exec = async (): Promise<T> => {
    const headers: Record<string, string> = {};
    let body: BodyInit | undefined;

    const token = getStoredToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (options.formData) {
      body = options.formData;
    } else if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }

    const isMutating = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
    const isAuthExempt =
      path.startsWith("/auth/login") ||
      path.startsWith("/auth/logout") ||
      path.startsWith("/auth/forgot-password") ||
      path.startsWith("/auth/reset-password") ||
      path.startsWith("/auth/register");

    if (isMutating && !isAuthExempt) {
      headers["X-CSRF-Token"] = await ensureCsrf();
    }

    const res = await fetch(url, {
      method,
      headers,
      body,
      credentials: "include",
      signal: options.signal,
    });

    if (res.status === 204) return undefined as T;

    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("text/csv")) {
      return (await res.blob()) as unknown as T;
    }

    let payload: any = null;
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }

    if (!res.ok) {
      const error = payload?.error;
      if (res.status === 403 && error?.code === "csrf_failed" && !isRetry) {
        clearCsrf();
        await ensureCsrf(true);
        return request<T>(path, options, true);
      }
      if (res.status === 401) {
        setStoredToken(null);
        if (!path.startsWith("/auth/")) {
          window.dispatchEvent(new Event("elite:unauthorized"));
        }
      }
      throw new ApiError(
        error?.message || "Something went wrong. Please try again.",
        res.status,
        error?.code || "error",
        error?.details
      );
    }

    return (payload?.data ?? payload) as T;
  };

  if (method === "GET" && !options.formData && !isRetry) {
    const promise = exec().finally(() => {
      inFlightGets.delete(url);
    });
    inFlightGets.set(url, promise);
    return promise;
  }

  return exec();
}

export const api = {
  get: <T = any>(path: string, params?: Options["params"]) => request<T>(path, { params }),
  post: <T = any>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T = any>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  put: <T = any>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  del: <T = any>(path: string) => request<T>(path, { method: "DELETE" }),
  delete: <T = any>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T = any>(path: string, formData: FormData) => request<T>(path, { method: "POST", formData }),
  download: async (path: string, filename: string) => {
    const blob = await request<Blob>(path);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
};

export async function fetchMeta<T = any>(path: string, params?: Options["params"]) {
  const url = buildUrl(path, params);
  const headers: Record<string, string> = {};
  const token = getStoredToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, { credentials: "include", headers });
  const payload = await res.json();
  if (!res.ok) {
    if (res.status === 401) {
      setStoredToken(null);
      if (!path.startsWith("/auth/")) {
        window.dispatchEvent(new Event("elite:unauthorized"));
      }
    }
    throw new ApiError(payload?.error?.message || "Request failed", res.status, payload?.error?.code || "error");
  }
  return { data: payload.data as T, meta: payload.meta as { page: number; per_page: number; total: number; pages: number } };
}
