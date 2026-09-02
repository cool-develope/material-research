export type MaterialType =
  | "document"
  | "project"
  | "dataset"
  | "code"
  | "image"
  | "presentation"
  | "spreadsheet"
  | "configuration"
  | "unknown";

export type AgentMode = "quick" | "standard" | "deep";

export type SearchHit = {
  material_id: string;
  title: string;
  material_type: string;
  root_path: string;
  score: number;
  siblings: string[];
};

export type SearchResponse = {
  query: string;
  page: number;
  page_size: number;
  has_more: boolean;
  results: SearchHit[];
  trace_url: string | null;
};

export type Citation = {
  material_id: string;
  title: string;
  citation: string;
  snippet: string;
  score: number;
};

export type ReportSection = {
  question_id: string;
  heading: string;
  body: string;
  citation_keys: string[];
};

export type ChatResponse = {
  objective: string;
  summary: string;
  text: string;
  sections: ReportSection[];
  citations: Citation[];
  mode: string;
  thread_id: string;
  trace_url: string | null;
};

export type ChatHistoryMessage = {
  role: string;
  content: string;
  summary: string | null;
  created_at: string;
  ordinal: number;
};

export type ChatHistoryResponse = {
  thread_id: string;
  mode: string | null;
  messages: ChatHistoryMessage[];
};
