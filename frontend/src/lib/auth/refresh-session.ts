"use client";

import { refreshAuthRefreshPost } from "@/lib/api/generated/endpoints/auth/auth";
import { readBrowserCookie } from "@/lib/api/mutator";
import { CSRF_COOKIE_NAME } from "@/lib/api/request-config";
import { ApiError } from "@/lib/errors/api-error";

const AUTH_CHANNEL_NAME = "auth";
const REFRESH_LOCK_NAME = "auth-refresh";
const SUPERSEDED_CODE = "refresh_superseded";
const SESSION_ENDED_STATUSES = new Set([401, 403]);

/**
 * The result of one refresh attempt: a renewed session (with the new access
 * expiry when this tab learned it), a session that ended and needs a new
 * sign-in, or an API that could not be reached.
 */
export type RefreshOutcome =
  | { status: "refreshed"; accessExpiresAt: number | null }
  | { status: "logged-out" }
  | { status: "unavailable" };

/** What one tab tells the others on the `auth` BroadcastChannel. */
export type AuthChannelMessage = { type: "refreshed"; expiresAt: number } | { type: "logged-out" };

type LoggedOutHandler = () => void;
type AuthChannelListener = (message: AuthChannelMessage) => void;

const loggedOutHandlers = new Set<LoggedOutHandler>();
let inFlight: Promise<RefreshOutcome> | null = null;
let channel: BroadcastChannel | null = null;

function authChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === "undefined") return null;
  channel ??= new BroadcastChannel(AUTH_CHANNEL_NAME);
  return channel;
}

function broadcast(message: AuthChannelMessage): void {
  authChannel()?.postMessage(message);
}

function isAuthChannelMessage(value: unknown): value is AuthChannelMessage {
  if (typeof value !== "object" || value === null || !("type" in value)) return false;
  if (value.type === "logged-out") return true;
  return value.type === "refreshed" && "expiresAt" in value && typeof value.expiresAt === "number";
}

function notifyLoggedOut(): void {
  for (const handler of loggedOutHandlers) handler();
}

async function withRefreshLock(task: () => Promise<RefreshOutcome>): Promise<RefreshOutcome> {
  const locks = typeof navigator === "undefined" ? undefined : navigator.locks;
  return locks ? await locks.request(REFRESH_LOCK_NAME, task) : task();
}

function classifyFailure(error: unknown): RefreshOutcome {
  if (error instanceof ApiError && error.code === SUPERSEDED_CODE) {
    return { status: "refreshed", accessExpiresAt: null };
  }
  if (error instanceof ApiError && SESSION_ENDED_STATUSES.has(error.status)) {
    return { status: "logged-out" };
  }
  return { status: "unavailable" };
}

async function refreshUnlessRotated(csrfAtStart: string | undefined): Promise<RefreshOutcome> {
  const csrfNow = readBrowserCookie(CSRF_COOKIE_NAME);
  if (csrfNow && csrfNow !== csrfAtStart) {
    return { status: "refreshed", accessExpiresAt: null };
  }
  try {
    const expiry = await refreshAuthRefreshPost();
    const accessExpiresAt = Date.parse(expiry.access_expires_at);
    broadcast({ type: "refreshed", expiresAt: accessExpiresAt });
    return { status: "refreshed", accessExpiresAt };
  } catch (error) {
    return classifyFailure(error);
  }
}

async function runRefresh(): Promise<RefreshOutcome> {
  const csrfAtStart = readBrowserCookie(CSRF_COOKIE_NAME);
  const outcome = await withRefreshLock(() => refreshUnlessRotated(csrfAtStart));
  if (outcome.status === "logged-out") {
    broadcast({ type: "logged-out" });
    notifyLoggedOut();
  }
  return outcome;
}

/**
 * Renews the session through `POST /auth/refresh`, once per tab at a time:
 * concurrent callers share one in-flight promise. Across tabs the Web Locks
 * API (`auth-refresh`) serialises the call, and a tab that finds `app_csrf`
 * already rotated by another tab skips its own request. A renewed session is
 * announced on the `auth` BroadcastChannel; an ended one is announced there
 * too and handed to every handler registered with `onLoggedOut`.
 */
export function refreshSession(): Promise<RefreshOutcome> {
  inFlight ??= runRefresh().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

/**
 * Registers what this tab does when its session ends, such as clearing the
 * query cache and going to the login page. Returns the unregister function.
 */
export function onLoggedOut(handler: LoggedOutHandler): () => void {
  loggedOutHandlers.add(handler);
  return () => {
    loggedOutHandlers.delete(handler);
  };
}

/**
 * Listens to what other tabs announce on the `auth` BroadcastChannel; this
 * tab's own announcements are not echoed back. Returns the unsubscribe function.
 */
export function subscribeAuthChannel(listener: AuthChannelListener): () => void {
  const current = authChannel();
  if (!current) return () => undefined;
  const receive = (event: MessageEvent<unknown>) => {
    if (isAuthChannelMessage(event.data)) listener(event.data);
  };
  current.addEventListener("message", receive);
  return () => current.removeEventListener("message", receive);
}
