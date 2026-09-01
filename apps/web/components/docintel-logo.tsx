import { FileText } from "lucide-react";

export function DocIntelLogo() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative grid h-10 w-10 place-items-center rounded-lg bg-teal-700 text-white shadow-sm shadow-teal-950/20">
        <FileText className="h-5 w-5" aria-hidden="true" />
        <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-amber-400" />
        <span className="absolute bottom-2 right-2 h-1 w-3 rounded-full bg-teal-200" />
      </div>
      <div className="leading-tight">
        <p className="text-base font-black tracking-normal text-ink">
          <span>DocIntel</span> <span className="text-teal-700">AI</span>
        </p>
        <p className="text-xs font-medium text-slate-500">Cited document intelligence</p>
      </div>
    </div>
  );
}
