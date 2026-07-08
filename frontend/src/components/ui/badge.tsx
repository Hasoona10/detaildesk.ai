import * as React from "react";
import { cn } from "@/lib/utils";

type BadgeProps = React.HTMLAttributes<HTMLDivElement> & {
  variant?: "outline" | "default";
};

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium border",
        variant === "outline"
          ? "bg-white text-slate-700 border-slate-200"
          : "bg-slate-900 text-white border-slate-900",
        className
      )}
      {...props}
    />
  );
}
