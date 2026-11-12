import { cn } from "@/lib/cn";

export interface ProgressBarProps {
  value: number;
  max: number;
  label: string;
  className?: string;
}

/** A thin native progress bar in the brand color, named for assistive technology by `label`. */
export function ProgressBar({ value, max, label, className }: ProgressBarProps) {
  return (
    <progress
      value={value}
      max={Math.max(max, 1)}
      aria-label={label}
      className={cn(
        "block h-1.5 w-full appearance-none overflow-hidden rounded-full bg-gray-200 [&::-moz-progress-bar]:rounded-full [&::-moz-progress-bar]:bg-brand [&::-webkit-progress-bar]:bg-gray-200 [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-brand",
        className,
      )}
    />
  );
}
