"use client";

import { useState, type ChangeEvent } from "react";
import { FileUp, UploadCloud } from "lucide-react";

import { Badge } from "@/components/ui/badge";
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
    <label className="group block rounded-lg border border-dashed border-teal-300 bg-white/90 p-6 shadow-sm shadow-teal-950/5 transition hover:-translate-y-0.5 hover:border-teal-600 hover:bg-teal-50/60">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center rounded-lg bg-teal-700 text-white shadow-sm shadow-teal-950/15 transition group-hover:scale-105">
            <UploadCloud className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-semibold">Upload document</p>
            <p className="mt-1 text-xs leading-5 text-slate-500">{message}</p>
          </div>
        </div>
        <Badge tone={isUploading ? "amber" : "teal"}>
          <FileUp className="h-3.5 w-3.5" aria-hidden="true" />
          {isUploading ? "Indexing" : "PDF, PNG, JPG"}
        </Badge>
      </div>
      <input
        className="mt-5 block w-full cursor-pointer rounded-md border border-line bg-white text-sm file:mr-4 file:border-0 file:bg-teal-700 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
        type="file"
        accept=".pdf,.png,.jpg,.jpeg"
        onChange={handleFileChange}
        disabled={isUploading}
      />
    </label>
  );
}
