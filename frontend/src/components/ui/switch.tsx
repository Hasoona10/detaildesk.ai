import * as React from "react";
import { cn } from "@/lib/utils";

type SwitchProps = {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  className?: string;
};

export function Switch({ checked, onCheckedChange, className }: SwitchProps) {
  const [internal, setInternal] = React.useState(!!checked);
  const isOn = checked ?? internal;
  const toggle = () => {
    const next = !isOn;
    setInternal(next);
    onCheckedChange?.(next);
  };
  return (
    <button
      type="button"
      onClick={toggle}
      className={cn(
        "relative inline-flex h-6 w-11 items-center rounded-full transition",
        isOn ? "bg-emerald-500" : "bg-slate-300",
        className
      )}
    >
      <span
        className={cn(
          "inline-block h-5 w-5 transform rounded-full bg-white shadow transition",
          isOn ? "translate-x-5" : "translate-x-1"
        )}
      />
    </button>
  );
}
