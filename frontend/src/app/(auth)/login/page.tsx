import { LoginForm } from "@/features/auth/containers/login-form";
import { safeReturnPath } from "@/lib/auth/return-path";

export interface LoginRouteProps {
  searchParams: Promise<{ next?: string | string[]; reason?: string | string[] }>;
}

export default async function Page({ searchParams }: LoginRouteProps) {
  const { next, reason } = await searchParams;
  const returnTo = safeReturnPath(typeof next === "string" ? next : null);

  return <LoginForm returnTo={returnTo} sessionExpired={reason === "expired"} />;
}
