export type DocumentSummary = {
  id: string;
  filename: string;
  mime_type: string;
  status: string;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type SearchHit = {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  page_number: number;
  chunk_index: number;
  score: number;
  snippet: string;
};

export type SearchResponse = {
  query: string;
  hits: SearchHit[];
};

export type EvalRunSummary = {
  id: string;
  name: string;
  model_name: string;
  metrics: Record<string, number>;
  created_at: string;
};
