"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import {
  isNearExpiry,
  REFRESH_RETRY_DELAY_MS,
  refreshDelayMs,
} from "@/features/auth/model/refresh-schedule";
import { onLoggedOut, refreshSession, subscribeAuthChannel } from "@/lib/auth/refresh-session";
import type { AuthChannelMessage, RefreshOutcome } from "@/lib/auth/refresh-session";
import { expiredLoginPath } from "@/lib/auth/return-path";

export interface SessionKeeperProps {
  accessExpiresAt: number | null;
}

const WAKE_EVENTS = ["focus", "online"] as const;

function currentPath(): string {
  return `${window.location.pathname}${window.location.search}`;
}

/**
 * Keeps the session alive while the app is open and renders nothing. It
 * refreshes the access token ahead of its expiry (two minutes before, ±15 s,
 * or halfway for a short-lived token), reschedules from every refresh and
 * from what other tabs announce, and refreshes at once when the tab becomes
 * visible, regains focus or comes back online near or past expiry. When the
 * session ends, here or in another tab, it drops the query cache and
 * replaces the page with the login page's "session expired" notice,
 * returning to the current URL after sign-in.
 */
export function SessionKeeper({ accessExpiresAt }: SessionKeeperProps) {
  const queryClient = useQueryClient();
  const router = useRouter();

  useEffect(() => {
    let expiresAt = accessExpiresAt;
    let timer: ReturnType<typeof setTimeout> | undefined;

    function schedule(delayMs: number | null) {
      clearTimeout(timer);
      timer = delayMs === null ? undefined : setTimeout(renew, delayMs);
    }

    function scheduleFromExpiry() {
      schedule(expiresAt === null ? null : refreshDelayMs(expiresAt, Date.now()));
    }

    function adopt(outcome: RefreshOutcome) {
      if (outcome.status === "logged-out") {
        schedule(null);
        return;
      }
      if (outcome.status === "unavailable") {
        schedule(REFRESH_RETRY_DELAY_MS);
        return;
      }
      if (outcome.accessExpiresAt === null) {
        schedule(REFRESH_RETRY_DELAY_MS);
        return;
      }
      expiresAt = outcome.accessExpiresAt;
      scheduleFromExpiry();
    }

    function renew() {
      void refreshSession().then(adopt);
    }

    function renewIfNearExpiry() {
      if (document.visibilityState !== "visible") return;
      if (expiresAt !== null && isNearExpiry(expiresAt, Date.now())) renew();
    }

    function endSession() {
      schedule(null);
      queryClient.clear();
      router.replace(expiredLoginPath(currentPath()));
    }

    function receive(message: AuthChannelMessage) {
      if (message.type === "logged-out") {
        endSession();
        return;
      }
      if (!Number.isFinite(message.expiresAt)) return;
      expiresAt = message.expiresAt;
      scheduleFromExpiry();
    }

    scheduleFromExpiry();
    const stopLoggedOut = onLoggedOut(endSession);
    const stopChannel = subscribeAuthChannel(receive);
    document.addEventListener("visibilitychange", renewIfNearExpiry);
    for (const event of WAKE_EVENTS) window.addEventListener(event, renewIfNearExpiry);

    return () => {
      schedule(null);
      stopLoggedOut();
      stopChannel();
      document.removeEventListener("visibilitychange", renewIfNearExpiry);
      for (const event of WAKE_EVENTS) window.removeEventListener(event, renewIfNearExpiry);
    };
  }, [accessExpiresAt, queryClient, router]);

  return null;
}
