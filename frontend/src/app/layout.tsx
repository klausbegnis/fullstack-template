import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Providers } from "@/lib/query/providers";
import { readRequestNonce } from "@/lib/security/request-nonce";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Fullstack Template",
  description: "FastAPI and Next.js fullstack template",
};

export interface RootLayoutProps {
  children: ReactNode;
}

/**
 * The framework-owned root layout: `html`/`body` and the app-wide client
 * providers only. Authenticated chrome (header, nav) lives in
 * `(app)/layout.tsx` so unauthenticated screens such as `/login` render
 * without it. It reads the request's CSP nonce, so every page renders per
 * request and carries that nonce on its scripts.
 */
export default async function RootLayout({ children }: RootLayoutProps) {
  await readRequestNonce();
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
