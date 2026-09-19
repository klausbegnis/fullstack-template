import { cn } from "@/lib/cn";

export interface SpinnerProps {
  label?: string;
  className?: string;
}

/**
 * A props-only loading indicator, announced to assistive technology through
 * `role="status"`.
 */
export function Spinner({ label = "Loading", className }: SpinnerProps) {
  return (
    <span
      role="status"
      className={cn(
        "inline-block h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600",
        className,
      )}
    >
      <span className="sr-only">{label}</span>
    </span>
  );
}
