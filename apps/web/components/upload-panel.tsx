"use client";

import { useState, type ChangeEvent } from "react";
import { UploadCloud } from "lucide-react";

import { uploadDocument } from "@/lib/api";
import type { DocumentSummary } from "@/lib/types";

export function UploadPanel({ onUploaded }: { onUploaded?: (document: DocumentSummary) => void }) {
  const [message, setMessage] = useState<string>("PDF uploads are indexed; image uploads are stored for deferred OCR.");
  const [isUploading, setIsUploading] = useState(false);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setIsUploading(true);
    setMessage("Uploading and indexing document...");
    try {
      const document = await uploadDocument(file);
      setMessage(`${document.filename} is ${document.status.replace("_", " ")}.`);
      onUploaded?.(document);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  return (
    <label className="block rounded border border-dashed border-accent bg-white p-6">
      <div className="flex items-center gap-3">
        <UploadCloud className="h-5 w-5 text-accent" aria-hidden="true" />
        <div>
          <p className="text-sm font-semibold">Upload document</p>
          <p className="mt-1 text-xs text-slate-500">{message}</p>
        </div>
      </div>
      <input className="mt-4 block w-full text-sm" type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={handleFileChange} disabled={isUploading} />
    </label>
  );
}
