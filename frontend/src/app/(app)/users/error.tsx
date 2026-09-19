"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export interface UsersErrorProps {
  error: Error & { digest?: string };
  retry: () => void;
}

export default function Error({ error, retry }: UsersErrorProps) {
  return (
    <div className="flex flex-col items-start gap-4">
      <Alert tone="danger" title="Could not load users">
        {error.message}
      </Alert>
      <Button onClick={retry}>Try again</Button>
    </div>
  );
}
