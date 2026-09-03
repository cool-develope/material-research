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
  snippet: string;
  keywords: string[];
};

export type SearchResponse = {
  query: string;
  page: number;
  page_size: number;
  has_more: boolean;
  page_count: number;
  total: number;
  results: SearchHit[];
  trace_url: string | null;
};

export type MaterialUnit = {
  unit_type: string;
  citation: string;
};

export type MaterialDetail = {
  material_id: string;
  title: string;
  material_type: string;
  material_subtype: string | null;
  root_path: string;
  status: string;
  summary: string;
  purpose: string | null;
  keywords: string[];
  topics: string[];
  technologies: string[];
  research_relevance: number | null;
  units: MaterialUnit[];
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

export type ChatThreadSummary = {
  thread_id: string;
  title: string;
  mode: string | null;
  updated_at: string;
  messages: number;
};

export type User = {
  user_id: string;
  name: string;
  email: string;
};
