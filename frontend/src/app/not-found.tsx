import { Alert } from "@/components/ui/alert";

export default function NotFound() {
  return (
    <Alert tone="warning" title="Page not found">
      The page you are looking for does not exist.
    </Alert>
  );
}
