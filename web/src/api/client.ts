import type {
  AgentMode,
  ChatHistoryResponse,
  ChatResponse,
  ChatThreadSummary,
  MaterialDetail,
  MaterialType,
  SearchResponse,
} from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseError(response: Response): Promise<string> {
  const payload: unknown = await response.json().catch(() => null);
  if (typeof payload === "object" && payload !== null && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return response.statusText || "Request failed";
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }
  return (await response.json()) as T;
}

async function postJson<T>(path: string, body: object): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }
  return (await response.json()) as T;
}

export function searchMaterials(input: {
  query: string;
  page?: number;
  page_size?: number;
  material_type?: MaterialType | "";
}): Promise<SearchResponse> {
  return postJson<SearchResponse>("/search", {
    query: input.query,
    page: input.page ?? 1,
    page_size: input.page_size ?? 10,
    material_type: input.material_type || null,
  });
}

export function loadMaterial(materialId: string): Promise<MaterialDetail> {
  return getJson<MaterialDetail>(`/materials/${encodeURIComponent(materialId)}`);
}

export function runChat(input: {
  query: string;
  mode?: AgentMode;
  thread_id?: string;
}): Promise<ChatResponse> {
  return postJson<ChatResponse>("/chat", {
    query: input.query,
    mode: input.mode ?? "quick",
    thread_id: input.thread_id,
  });
}

export async function loadChatHistory(
  threadId: string,
): Promise<ChatHistoryResponse> {
  try {
    return await getJson<ChatHistoryResponse>(
      `/chat/${encodeURIComponent(threadId)}`,
    );
  } catch (err: unknown) {
    if (err instanceof ApiError && err.status === 404) {
      throw new ApiError(404, "thread not found");
    }
    throw err;
  }
}

export async function listChatThreads(): Promise<ChatThreadSummary[]> {
  const payload = await getJson<{ threads: ChatThreadSummary[] }>("/chats");
  return payload.threads;
}
