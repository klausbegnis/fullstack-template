import { Spinner } from "@/components/ui/spinner";

export default function Loading() {
  return (
    <div className="flex items-center justify-center p-12">
      <Spinner label="Loading page" />
    </div>
  );
}
