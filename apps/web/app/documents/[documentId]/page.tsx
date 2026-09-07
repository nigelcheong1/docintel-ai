import { DocumentWorkbenchPage } from "@/components/document-workbench-page";
import { parseInitialChunk, parseInitialPage } from "@/lib/document-deep-link";

type DocumentDetailPageProps = {
  params: Promise<{ documentId: string }> | { documentId: string };
  searchParams?:
    | Promise<{ page?: string | string[]; chunk?: string | string[] }>
    | { page?: string | string[]; chunk?: string | string[] };
};

export default async function DocumentDetailPage({ params, searchParams }: DocumentDetailPageProps) {
  const resolvedParams = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;

  return (
    <DocumentWorkbenchPage
      documentId={resolvedParams.documentId}
      initialPageNumber={parseInitialPage(resolvedSearchParams?.page)}
      initialChunkId={parseInitialChunk(resolvedSearchParams?.chunk)}
    />
  );
}
