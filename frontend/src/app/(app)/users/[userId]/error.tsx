"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export interface UserDetailErrorProps {
  error: Error & { digest?: string };
  retry: () => void;
}

export default function Error({ error, retry }: UserDetailErrorProps) {
  return (
    <div className="flex flex-col items-start gap-4">
      <Alert tone="danger" title="Could not load this user">
        {error.message}
      </Alert>
      <Button onClick={retry}>Try again</Button>
    </div>
  );
}
