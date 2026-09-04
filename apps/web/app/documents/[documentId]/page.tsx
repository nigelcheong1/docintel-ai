import { DocumentWorkbenchPage } from "@/components/document-workbench-page";

type DocumentDetailPageProps = {
  params: Promise<{ documentId: string }> | { documentId: string };
  searchParams?: Promise<{ page?: string | string[] }> | { page?: string | string[] };
};

function parseInitialPage(value?: string | string[]) {
  const rawValue = Array.isArray(value) ? value[0] : value;
  if (!rawValue) {
    return undefined;
  }
  const pageNumber = Number.parseInt(rawValue, 10);
  return Number.isFinite(pageNumber) && pageNumber > 0 ? pageNumber : undefined;
}

export default async function DocumentDetailPage({ params, searchParams }: DocumentDetailPageProps) {
  const resolvedParams = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;

  return (
    <DocumentWorkbenchPage
      documentId={resolvedParams.documentId}
      initialPageNumber={parseInitialPage(resolvedSearchParams?.page)}
    />
  );
}
