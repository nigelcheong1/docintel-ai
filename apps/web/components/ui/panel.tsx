import type { HTMLAttributes, ReactNode } from "react";

type PanelTone = "default" | "soft" | "accent";

const toneClasses: Record<PanelTone, string> = {
  default: "border-line bg-white",
  soft: "border-teal-100 bg-teal-50/60",
  accent: "border-teal-200 bg-white shadow-sm shadow-teal-900/5",
};

export function Panel({
  tone = "default",
  className,
  children,
  ...props
}: HTMLAttributes<HTMLElement> & { tone?: PanelTone; children: ReactNode }) {
  return (
    <section className={["rounded-lg border p-5", toneClasses[tone], className].filter(Boolean).join(" ")} {...props}>
      {children}
    </section>
  );
}
