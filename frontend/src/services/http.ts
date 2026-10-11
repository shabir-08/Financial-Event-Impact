/** Shared HTTP helper for the live backend. Failures throw ApiError; there is no silent demo fallback. */

export const BASE_URL: string = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(message: string, public status: number | null, public details: string[] = []) {
    super(message);
  }
}

export async function request<T>(path: string, init?: RequestInit, timeoutMs = 20000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...init, signal: controller.signal });
  } catch {
    throw new ApiError(
      controller.signal.aborted
        ? `The backend did not respond within ${timeoutMs / 1000}s (${BASE_URL}).`
        : `Cannot reach the backend at ${BASE_URL}. Is it running, and does CORS allow this origin?`,
      null,
    );
  } finally {
    clearTimeout(timer);
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error;
    const details: string[] = (err?.details?.errors ?? []).map((e: any) =>
      [e.field ?? (Array.isArray(e.loc) ? e.loc.join('.') : ''), e.error ?? e.msg, e.accepted_range ? `accepted ${e.accepted_range.join(' to ')}` : '']
        .filter(Boolean).join(': '),
    );
    throw new ApiError(err?.message || body?.detail || `Request failed (HTTP ${res.status})`, res.status, details);
  }
  return body as T;
}

export const errorMessage = (e: unknown): string => (e instanceof Error ? e.message : String(e));
