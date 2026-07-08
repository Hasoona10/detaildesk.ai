import * as React from "react";
import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "outline" | "ghost";
};

export function Button({ className, variant = "default", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-lg px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2",
        variant === "outline"
          ? "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50 focus:ring-emerald-200"
          : variant === "ghost"
          ? "text-slate-900 hover:bg-slate-100"
          : "bg-slate-900 text-white hover:bg-slate-800 focus:ring-emerald-200",
        className
      )}
      {...props}
    />
  );
}
