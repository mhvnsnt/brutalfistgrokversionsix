import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-border bg-elevated px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-muted",
        className,
      )}
      {...props}
    />
  );
}
