import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Providers } from "@/lib/query/providers";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Kitchen AI",
  description: "Kitchen AI frontend template",
};

export interface RootLayoutProps {
  children: ReactNode;
}

/**
 * The framework-owned root layout: `html`/`body` and the app-wide client
 * providers only. Authenticated chrome (header, nav) lives in
 * `(app)/layout.tsx` so unauthenticated screens such as `/login` render
 * without it.
 */
export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
