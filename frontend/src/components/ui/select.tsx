import * as React from "react";
import { cn } from "@/lib/utils";

type SelectContextType = {
  value: string;
  onChange: (val: string) => void;
  open: boolean;
  setOpen: (open: boolean) => void;
};

const SelectContext = React.createContext<SelectContextType | null>(null);

export function Select({ value, onValueChange, defaultValue, children }: {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  children: React.ReactNode;
}) {
  const [internal, setInternal] = React.useState(defaultValue || "");
  const [open, setOpen] = React.useState(false);
  const val = value ?? internal;
  const setVal = (v: string) => {
    setInternal(v);
    onValueChange?.(v);
  };
  return (
    <SelectContext.Provider value={{ value: val, onChange: setVal, open, setOpen }}>
      <div className="relative inline-block">{children}</div>
    </SelectContext.Provider>
  );
}

export function SelectTrigger({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLButtonElement>) {
  const ctx = React.useContext(SelectContext);
  return (
    <button
      type="button"
      className={cn(
        "inline-flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-200",
        className
      )}
      onClick={() => ctx?.setOpen(!ctx.open)}
      {...props}
    >
      {children}
    </button>
  );
}

export function SelectValue({ placeholder }: { placeholder?: string }) {
  const ctx = React.useContext(SelectContext);
  return <span className="text-left">{ctx?.value || placeholder || "Select"}</span>;
}

export function SelectContent({ children, className }: React.HTMLAttributes<HTMLDivElement>) {
  const ctx = React.useContext(SelectContext);
  if (!ctx?.open) return null;
  return (
    <div
      className={cn(
        "absolute z-10 mt-2 w-full rounded-lg border border-slate-200 bg-white p-1 shadow-lg",
        className
      )}
    >
      {children}
    </div>
  );
}

export function SelectItem({
  value,
  children,
  className,
}: {
  value: string;
  children: React.ReactNode;
  className?: string;
}) {
  const ctx = React.useContext(SelectContext);
  return (
    <div
      role="option"
      className={cn(
        "cursor-pointer rounded-md px-3 py-2 text-sm text-slate-800 hover:bg-emerald-50",
        className
      )}
      onClick={() => {
        ctx?.onChange(value);
        ctx?.setOpen(false);
      }}
    >
      {children}
    </div>
  );
}
