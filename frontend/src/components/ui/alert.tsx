import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type AlertTone = "info" | "success" | "warning" | "danger";

export interface AlertProps {
  tone?: AlertTone;
  title: string;
  children?: ReactNode;
}

const TONE_CLASSES: Record<AlertTone, string> = {
  info: "border-blue-200 bg-blue-50 text-blue-900",
  success: "border-green-200 bg-green-50 text-green-900",
  warning: "border-yellow-200 bg-yellow-50 text-yellow-900",
  danger: "border-red-200 bg-red-50 text-red-900",
};

/**
 * A props-only alert banner, announced to assistive technology through
 * `role="alert"`.
 */
export function Alert({ tone = "info", title, children }: AlertProps) {
  return (
    <div role="alert" className={cn("rounded-md border p-4 text-sm", TONE_CLASSES[tone])}>
      <p className="font-medium">{title}</p>
      {children ? <div className="mt-1">{children}</div> : null}
    </div>
  );
}
