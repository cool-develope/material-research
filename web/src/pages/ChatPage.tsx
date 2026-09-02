import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError, loadChatHistory, runChat } from "../api/client";
import type { AgentMode, ChatHistoryMessage } from "../api/types";
import { ReportBody } from "../components/ReportBody";

export function ChatPage() {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const [draft, setDraft] = useState("");
  const [mode, setMode] = useState<AgentMode>("quick");
  const [messages, setMessages] = useState<ChatHistoryMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!threadId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    loadChatHistory(threadId)
      .then((data) => {
        if (!cancelled) {
          setMessages(data.messages);
          if (data.mode === "quick" || data.mode === "standard" || data.mode === "deep") {
            setMode(data.mode);
          }
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load thread");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [threadId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const query = draft.trim();
    if (!query || loading) {
      return;
    }
    setDraft("");
    setError(null);
    setLoading(true);
    setMessages((current) => [
      ...current,
      {
        role: "user",
        content: query,
        summary: null,
        created_at: new Date().toISOString(),
        ordinal: current.length,
      },
    ]);
    try {
      const report = await runChat({
        query,
        mode,
        thread_id: threadId,
      });
      if (!threadId) {
        navigate(`/chat/${report.thread_id}`, { replace: true });
      }
      const history = await loadChatHistory(report.thread_id);
      setMessages(history.messages);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Chat failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="chat">
      <div className="chat-head">
        <div>
          <h1>Deep Research</h1>
          <p className="lede">
            Full transcript is stored. The agent plans from a compact working set.
          </p>
        </div>
        <Link className="ghost" to="/chat">
          New thread
        </Link>
      </div>
      {threadId ? <p className="thread">thread {threadId}</p> : null}
      <div className="transcript">
        {messages.length === 0 && !loading ? (
          <p className="status">Ask a research question about indexed materials.</p>
        ) : null}
        {messages.map((item) => (
          <article key={`${item.ordinal}-${item.role}`} className={`bubble ${item.role}`}>
            <span className="who">{item.role}</span>
            {item.role === "assistant" ? (
              <ReportBody text={item.content} />
            ) : (
              <p>{item.content}</p>
            )}
          </article>
        ))}
        {loading ? <p className="status">Researching… this can take a while.</p> : null}
        <div ref={endRef} />
      </div>
      {error ? <p className="error">{error}</p> : null}
      <form className="composer" onSubmit={submit}>
        <select
          value={mode}
          onChange={(event) => setMode(event.target.value as AgentMode)}
          aria-label="Agent mode"
          disabled={loading}
        >
          <option value="quick">quick</option>
          <option value="standard">standard</option>
          <option value="deep">deep</option>
        </select>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Compare authentication in these projects"
          aria-label="Research question"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !draft.trim()}>
          Ask
        </button>
      </form>
    </section>
  );
}
