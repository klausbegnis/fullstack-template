import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export type InputProps = InputHTMLAttributes<HTMLInputElement>;

/**
 * A props-only text input primitive with no validation logic of its own —
 * that lives in each feature's `model/` schema.
 */
export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500",
        className,
      )}
      {...props}
    />
  );
}
