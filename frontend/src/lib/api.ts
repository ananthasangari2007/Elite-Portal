export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api/v1";

const DEFAULT_TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 180_000;
const MAX_GET_RETRIES = 2;
const RETRYABLE_STATUS = new Set([502, 503, 504]);

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
const SESSION_HINT_COOKIE = "elite_session";

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
    // localStorage unavailable (private mode); the HttpOnly cookie still carries the session.
  }
}

/** True when a session may exist (stored token or the server's non-secret session hint cookie). */
export function hasSessionCandidate(): boolean {
  if (getStoredToken()) return true;
  try {
    return document.cookie.split(";").some((c) => c.trim().startsWith(`${SESSION_HINT_COOKIE}=`));
  } catch {
    return false;
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
  timeoutMs?: number;
};

export function buildUrl(path: string, params?: Options["params"]): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const absolute = API_BASE.startsWith("http://") || API_BASE.startsWith("https://");
  const url = absolute
    ? new URL(`${API_BASE.replace(/\/+$/, "")}${cleanPath}`)
    : new URL(`${(API_BASE.startsWith("/") ? API_BASE : `/${API_BASE}`).replace(/\/+$/, "")}${cleanPath}`, window.location.origin);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return absolute ? url.toString() : url.pathname + url.search;
}

function authHeaders(): Record<string, string> {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** fetch with a hard timeout; an external AbortSignal (component unmount) also cancels. */
async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number, external?: AbortSignal) {
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener("abort", onAbort, { once: true });
  }
  let timedOut = false;
  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    if (timedOut) throw new ApiError("The server took too long to respond. Please try again.", 0, "timeout");
    if (external?.aborted) throw new ApiError("Request cancelled.", 0, "aborted");
    throw new ApiError("Could not reach the server. Check your connection and try again.", 0, "network_error");
  } finally {
    window.clearTimeout(timer);
    external?.removeEventListener("abort", onAbort);
  }
}

export async function ensureCsrf(force = false): Promise<string> {
  if (csrfToken && !force) return csrfToken;
  if (csrfPromise && !force) return csrfPromise;

  csrfPromise = (async () => {
    try {
      const res = await fetchWithTimeout(
        buildUrl("/auth/csrf"),
        { credentials: "include", headers: authHeaders() },
        DEFAULT_TIMEOUT_MS
      );
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

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

// In-flight GET de-duplication (identical concurrent GETs share one network call).
const inFlightGets = new Map<string, Promise<any>>();

const AUTH_EXEMPT = [
  "/auth/login",
  "/auth/logout",
  "/auth/forgot-password",
  "/auth/reset-password",
  "/auth/register",
  "/auth/roster-lookup",
];

/** Performs the request and returns the full JSON envelope ({data, meta}) or a Blob. */
async function requestRaw(path: string, options: Options = {}): Promise<any> {
  const method = (options.method || "GET").toUpperCase();
  const url = buildUrl(path, options.params);
  const isMutating = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
  const timeoutMs = options.timeoutMs ?? (options.formData ? UPLOAD_TIMEOUT_MS : DEFAULT_TIMEOUT_MS);

  const exec = async (csrfRetried: boolean, attempt: number): Promise<any> => {
    const headers: Record<string, string> = authHeaders();
    let body: BodyInit | undefined;
    if (options.formData) {
      body = options.formData;
    } else if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
    if (isMutating && !AUTH_EXEMPT.some((p) => path.startsWith(p))) {
      headers["X-CSRF-Token"] = await ensureCsrf();
    }

    let res: Response;
    try {
      res = await fetchWithTimeout(url, { method, headers, body, credentials: "include" }, timeoutMs, options.signal);
    } catch (err) {
      // Only idempotent GETs are retried, and only for network failures/timeouts.
      if (method === "GET" && attempt < MAX_GET_RETRIES && err instanceof ApiError && err.code !== "aborted") {
        await sleep(400 * 2 ** attempt);
        return exec(csrfRetried, attempt + 1);
      }
      throw err;
    }

    if (res.status === 204) return { data: undefined };

    const contentType = res.headers.get("content-type") || "";
    if (res.ok && !contentType.includes("application/json")) {
      return await res.blob();
    }

    let payload: any = null;
    try {
      payload = await res.json();
    } catch {
      payload = null;
    }

    if (!res.ok) {
      const error = payload?.error;
      if (res.status === 403 && error?.code === "csrf_failed" && !csrfRetried) {
        await ensureCsrf(true);
        return exec(true, attempt);
      }
      if (method === "GET" && RETRYABLE_STATUS.has(res.status) && attempt < MAX_GET_RETRIES) {
        await sleep(400 * 2 ** attempt);
        return exec(csrfRetried, attempt + 1);
      }
      if (res.status === 401) {
        setStoredToken(null);
        clearCsrf();
        if (!path.startsWith("/auth/")) {
          window.dispatchEvent(new Event("elite:unauthorized"));
        }
      }
      throw new ApiError(
        error?.message || (res.status >= 500 ? "The server ran into a problem. Please try again." : "Something went wrong. Please try again."),
        res.status,
        error?.code || "error",
        error?.details
      );
    }
    return payload;
  };

  if (method === "GET" && !options.signal) {
    const existing = inFlightGets.get(url);
    if (existing) return existing;
    const promise = exec(false, 0).finally(() => inFlightGets.delete(url));
    inFlightGets.set(url, promise);
    return promise;
  }
  return exec(false, 0);
}

export async function request<T = any>(path: string, options: Options = {}): Promise<T> {
  const payload = await requestRaw(path, options);
  if (payload instanceof Blob) return payload as unknown as T;
  return (payload?.data ?? payload) as T;
}

export const api = {
  get: <T = any>(path: string, params?: Options["params"], signal?: AbortSignal) => request<T>(path, { params, signal }),
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
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};

export async function fetchMeta<T = any>(path: string, params?: Options["params"], signal?: AbortSignal) {
  const payload = await requestRaw(path, { params, signal });
  return {
    data: payload?.data as T,
    meta: payload?.meta as { page: number; per_page: number; total: number; pages: number },
  };
}
