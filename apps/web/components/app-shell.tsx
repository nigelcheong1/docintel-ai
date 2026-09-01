import Link from "next/link";
import type { ReactNode } from "react";
import { Database, FileSearch, Gauge, UploadCloud } from "lucide-react";

import { CursorSpotlight } from "@/components/cursor-spotlight";
import { DocIntelLogo } from "@/components/docintel-logo";

const navItems = [
  { href: "/", label: "Dashboard", icon: Database },
  { href: "/documents", label: "Documents", icon: UploadCloud },
  { href: "/search", label: "Search", icon: FileSearch },
  { href: "/evaluation", label: "Evaluation", icon: Gauge },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-panel text-ink">
      <CursorSpotlight />
      <aside className="fixed inset-y-0 left-0 z-10 hidden w-72 border-r border-white/10 bg-ink p-5 text-white shadow-xl shadow-teal-950/10 md:block">
        <Link
          href="/"
          aria-label="DocIntel AI home"
          className="mb-8 block rounded-lg bg-white/95 p-3 text-ink shadow-sm shadow-black/10 transition hover:-translate-y-0.5 hover:bg-teal-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
        >
          <DocIntelLogo />
        </Link>
        <nav aria-label="Desktop navigation" className="space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-slate-200 transition hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="absolute inset-x-5 bottom-5 rounded-lg border border-white/10 bg-white/5 p-4 text-xs text-slate-300">
          <p className="font-semibold text-white">Local-first workspace</p>
          <p className="mt-1 leading-5">Cited answers, quality checks, and document diagnostics stay close to your files.</p>
        </div>
      </aside>
      <header className="relative z-10 border-b border-line bg-white/95 shadow-sm shadow-teal-950/5 backdrop-blur md:hidden">
        <div className="px-4 py-3">
          <Link
            href="/"
            aria-label="DocIntel AI home"
            className="inline-flex rounded-lg transition hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600"
          >
            <DocIntelLogo />
          </Link>
        </div>
        <nav aria-label="Mobile navigation" className="flex overflow-x-auto border-t border-line px-2 md:hidden">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex min-w-fit items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-teal-50 hover:text-teal-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600"
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </Link>
          ))}
        </nav>
      </header>
      <main className="relative z-10 min-h-screen md:pl-72">
        <div className="mx-auto max-w-7xl p-4 md:p-8">{children}</div>
      </main>
    </div>
  );
}
