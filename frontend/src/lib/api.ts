import { translate, translateServer } from "./i18n";

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
  }
}

const HINT = "gf_session_hint"; // non-sensitive flag: "this browser had a session" (tokens themselves are HttpOnly)
export const setSessionHint = (on: boolean) => {
  try { on ? localStorage.setItem(HINT, "1") : localStorage.removeItem(HINT); } catch { /* storage unavailable */ }
};
const hasHint = () => { try { return !!localStorage.getItem(HINT); } catch { return false; } };

const cookie = (name: string) =>
  document.cookie.split("; ").find((c) => c.startsWith(name + "="))?.slice(name.length + 1);

async function ensureCsrf() {
  if (!cookie("gf_csrf")) await fetch("/api/auth/csrf", { credentials: "same-origin" });
}

let refreshing: Promise<boolean> | null = null;
function refresh(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      await ensureCsrf();
      const r = await fetch("/api/auth/refresh", { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": cookie("gf_csrf") ?? "" } });
      return r.ok;
    } catch { return false; } finally { setTimeout(() => (refreshing = null), 0); }
  })();
  return refreshing;
}

type Query = Record<string, string | number | boolean | string[] | undefined | null>;
function qs(query?: Query) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x)); else p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function api<T = unknown>(path: string, opts: { method?: string; body?: unknown; query?: Query; signal?: AbortSignal } = {}): Promise<T> {
  const method = opts.method ?? "GET";
  const unsafe = method !== "GET";
  if (unsafe) await ensureCsrf();
  const send = () => fetch(`/api${path}${qs(opts.query)}`, {
    method, credentials: "same-origin", signal: opts.signal,
    headers: { ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}), ...(unsafe ? { "X-CSRF-Token": cookie("gf_csrf") ?? "" } : {}) },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  let res = await send();
  if (res.status === 401 && !path.startsWith("/auth/") && hasHint() && (await refresh())) res = await send();
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401) setSessionHint(false);
    throw new ApiError(res.status, data?.detail ?? "Request failed");
  }
  return data as T;
}

export const errorMessage = (e: unknown): string => {
  if (e instanceof ApiError) {
    if (Array.isArray(e.detail)) return e.detail.map((d) => translateServer(typeof d === "string" ? d : d.msg)).join(" ");
    return translateServer(String(e.detail));
  }
  return translate("err.generic");
};
