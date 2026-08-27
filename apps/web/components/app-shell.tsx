import Link from "next/link";
import type { ReactNode } from "react";
import { Database, FileSearch, Gauge, UploadCloud } from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: Database },
  { href: "/documents", label: "Documents", icon: UploadCloud },
  { href: "/search", label: "Search", icon: FileSearch },
  { href: "/evaluation", label: "Evaluation", icon: Gauge },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-panel text-ink">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-line bg-white p-4 md:block">
        <div className="mb-8">
          <p className="text-sm font-semibold">DocIntel AI</p>
          <p className="mt-1 text-xs text-slate-500">Local document intelligence</p>
        </div>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className="flex items-center gap-2 rounded px-3 py-2 text-sm hover:bg-panel">
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="min-h-screen md:pl-64">
        <div className="mx-auto max-w-6xl p-4 md:p-8">{children}</div>
      </main>
    </div>
  );
}
