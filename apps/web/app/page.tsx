import { AppShell } from "@/components/app-shell";

export default function DashboardPage() {
  return (
    <AppShell>
      <section className="mb-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="mt-2 text-sm text-slate-600">Upload PDFs, index local embeddings, and search with cited evidence.</p>
      </section>
      <div className="grid gap-4 md:grid-cols-3">
        {["Documents", "Indexed chunks", "Evaluation runs"].map((label) => (
          <div key={label} className="rounded border border-line bg-white p-4">
            <p className="text-sm text-slate-500">{label}</p>
            <p className="mt-3 text-3xl font-semibold">0</p>
          </div>
        ))}
      </div>
    </AppShell>
  );
}
