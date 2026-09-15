import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "outline";
};

export function Button({ className, variant = "primary", ...props }: Props) {
  return (
    <button
      className={cn(
        "inline-flex min-h-11 items-center justify-center rounded-[var(--radius-sm)] px-4 text-sm font-medium tracking-wide transition-opacity duration-[var(--motion-quick,150ms)] disabled:opacity-40",
        variant === "primary" && "bg-accent text-accent-fg",
        variant === "ghost" && "bg-transparent text-fg hover:bg-elevated",
        variant === "outline" && "border border-border bg-surface text-fg",
        className,
      )}
      {...props}
    />
  );
}
