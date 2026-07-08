"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchLeads } from "@/lib/api";

type NavItem = {
  href: string;
  label: string;
  icon: React.ReactNode;
  badge?: number;
};

function Icon({ path }: { path: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-[18px] w-[18px] shrink-0"
    >
      <path d={path} />
    </svg>
  );
}

const ICONS = {
  inbox:
    "M22 12h-6l-2 3h-4l-2-3H2 M5.5 5h13l3.5 7v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6l3.5-7z",
  phone:
    "M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.9a2 2 0 0 1-.4 2.1L8.1 10a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.9.6 2.9.7a2 2 0 0 1 1.6 2z",
  calendar:
    "M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
  training:
    "M22 10 12 5 2 10l10 5 10-5z M6 12v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5",
  sparkle:
    "M12 3v2 M12 19v2 M5.6 5.6l1.4 1.4 M17 17l1.4 1.4 M3 12h2 M19 12h2 M5.6 18.4 7 17 M17 7l1.4-1.4 M12 8l1.2 2.8L16 12l-2.8 1.2L12 16l-1.2-2.8L8 12l2.8-1.2L12 8z",
  gear:
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z",
};

export default function Sidebar() {
  const pathname = usePathname();
  const [newCount, setNewCount] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetchLeads()
        .then((leads) => {
          if (alive) setNewCount(leads.filter((l) => l.status === "new").length);
        })
        .catch(() => {});
    load();
    const id = setInterval(load, 15_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const nav: NavItem[] = [
    { href: "/inbox", label: "Lead Inbox", icon: <Icon path={ICONS.inbox} />, badge: newCount ?? undefined },
    { href: "/calls", label: "Calls", icon: <Icon path={ICONS.phone} /> },
    { href: "/appointments", label: "Appointments", icon: <Icon path={ICONS.calendar} /> },
    { href: "/business-settings", label: "AI Training", icon: <Icon path={ICONS.training} /> },
    { href: "/services", label: "Services", icon: <Icon path={ICONS.sparkle} /> },
    { href: "/settings", label: "Settings", icon: <Icon path={ICONS.gear} /> },
  ];

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col bg-[#0c1228] text-slate-300">
      {/* Logo — app icon + wordmark (lockup is for light backgrounds) */}
      <div className="flex items-center gap-2.5 px-5 pb-6 pt-5">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/logo-icon.png"
          alt=""
          aria-hidden
          className="h-9 w-9 shrink-0 rounded-xl"
        />
        <div className="text-[16px] font-bold tracking-tight text-white">
          DetailDesk <span className="text-[#3b9eff]">AI</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-1 px-3">
        {nav.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13.5px] font-medium transition-colors ${
                active
                  ? "bg-blue-600/90 text-white"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              }`}
            >
              {item.icon}
              <span className="flex-1">{item.label}</span>
              {item.badge != null && item.badge > 0 && (
                <span
                  className={`flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] font-semibold ${
                    active ? "bg-white/20 text-white" : "bg-blue-600 text-white"
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* AI number card */}
      <div className="mx-3 mt-auto mb-3 rounded-xl border border-white/10 bg-white/5 p-4">
        <div className="text-[11px] font-medium text-slate-400">Your AI Number</div>
        <div className="mt-0.5 text-[17px] font-bold text-sky-400">(714) 278-3407</div>
        <div className="mt-1 text-[11px] leading-snug text-slate-400">
          Forward missed calls to this number
        </div>
        <a
          href="https://support.google.com/voice/answer/115082"
          target="_blank"
          rel="noreferrer"
          className="mt-3 block rounded-lg bg-blue-600 px-3 py-2 text-center text-[11.5px] font-semibold text-white hover:bg-blue-500"
        >
          How to set up forwarding
        </a>
      </div>

      {/* User footer */}
      <div className="flex items-center gap-3 border-t border-white/10 px-5 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-[12px] font-bold text-white">
          H
        </div>
        <div className="min-w-0">
          <div className="truncate text-[13px] font-semibold text-white">Hasan</div>
          <div className="truncate text-[11px] text-slate-400">OC Elite Detailing</div>
        </div>
      </div>
    </aside>
  );
}
