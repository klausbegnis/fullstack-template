import { Spinner } from "@/components/ui/spinner";

export default function Loading() {
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <Spinner label="Loading sign-in" />
    </div>
  );
}
