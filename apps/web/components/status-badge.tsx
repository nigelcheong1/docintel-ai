const LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  indexed: "Indexed",
  deferred_ocr: "OCR deferred",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: string }) {
  const label = LABELS[status] ?? status;
  return (
    <span className="inline-flex min-w-24 items-center justify-center rounded border border-line bg-white px-2 py-1 text-xs font-medium text-ink">
      {label}
    </span>
  );
}
