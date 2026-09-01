import { Badge } from "@/components/ui/badge";

const LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  ocr_processing: "OCR running",
  indexed: "Indexed",
  deferred_ocr: "OCR deferred",
  failed: "Failed",
};

const TONES: Record<string, "neutral" | "teal" | "amber" | "success" | "danger"> = {
  uploaded: "neutral",
  processing: "teal",
  ocr_processing: "teal",
  indexed: "success",
  deferred_ocr: "amber",
  failed: "danger",
};

export function StatusBadge({ status }: { status: string }) {
  const label = LABELS[status] ?? status;
  return <Badge tone={TONES[status] ?? "neutral"} className="min-w-24 justify-center">{label}</Badge>;
}
