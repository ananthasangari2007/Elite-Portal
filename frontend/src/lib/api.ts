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

let csrfToken: string | null = null;

export async function ensureCsrf(): Promise<string> {
  if (csrfToken) return csrfToken;
  const res = await fetch(`${API_BASE}/auth/csrf`, { credentials: "include" });
  if (!res.ok) throw new ApiError("Could not initialise a secure session.", res.status, "csrf_init_failed");
  const body = await res.json();
  csrfToken = body.data.csrf_token as string;
  return csrfToken;
}

export function clearCsrf() {
  csrfToken = null;
}

type Options = {
  method?: string;
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined | null>;
  formData?: FormData;
  signal?: AbortSignal;
};

function buildUrl(path: string, params?: Options["params"]) {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
    });
  }
  return url.pathname + url.search;
}

export async function request<T = any>(path: string, options: Options = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;

  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (["POST", "PUT", "PATCH", "DELETE"].includes(method) && !path.startsWith("/auth/login") &&
      !path.startsWith("/auth/forgot-password") && !path.startsWith("/auth/reset-password") &&
      !path.startsWith("/auth/register")) {
    headers["X-CSRF-Token"] = await ensureCsrf();
  }

  const res = await fetch(buildUrl(path, options.params), {
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
    if (res.status === 401 && !path.startsWith("/auth/")) {
      window.dispatchEvent(new Event("elite:unauthorized"));
    }
    const error = payload?.error;
    throw new ApiError(
      error?.message || "Something went wrong. Please try again.",
      res.status,
      error?.code || "error",
      error?.details
    );
  }

  return (payload?.data ?? payload) as T;
}

export const api = {
  get: <T = any>(path: string, params?: Options["params"]) => request<T>(path, { params }),
  post: <T = any>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T = any>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  put: <T = any>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  del: <T = any>(path: string) => request<T>(path, { method: "DELETE" }),
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
  const res = await fetch(buildUrl(path, params), { credentials: "include" });
  const payload = await res.json();
  if (!res.ok) throw new ApiError(payload?.error?.message || "Request failed", res.status, payload?.error?.code || "error");
  return { data: payload.data as T, meta: payload.meta as { page: number; per_page: number; total: number; pages: number } };
}
