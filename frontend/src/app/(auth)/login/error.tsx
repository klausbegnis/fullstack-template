"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export interface LoginErrorProps {
  error: Error & { digest?: string };
  retry: () => void;
}

export default function Error({ error, retry }: LoginErrorProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6">
      <Alert tone="danger" title="Could not load the sign-in page">
        {error.message}
      </Alert>
      <Button onClick={retry}>Try again</Button>
    </div>
  );
}
