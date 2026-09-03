import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  ApiError,
  listChatThreads,
  loadChatHistory,
  runChat,
} from "../api/client";
import type {
  AgentMode,
  ChatHistoryMessage,
  ChatThreadSummary,
  Citation,
} from "../api/types";
import { AppTabs } from "../components/AppTabs";
import { AskBox } from "../components/AskBox";
import { ChatSidebar } from "../components/ChatSidebar";
import { ReportBody } from "../components/ReportBody";
import { useProfile } from "../prefs";

const IDEAS = [
  "Summarize indexed papers on retrieval-augmented generation",
  "How does QLoRA compare with full fine-tuning?",
  "What datasets are available for instruction tuning?",
];

export function ChatPage() {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const { profile, ready } = useProfile();
  const next = threadId ? `/chat/${threadId}` : "/chat";
  const [draft, setDraft] = useState("");
  const [mode, setMode] = useState<AgentMode>("quick");
  const [messages, setMessages] = useState<ChatHistoryMessage[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [threads, setThreads] = useState<ChatThreadSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(true);
  const [historyReady, setHistoryReady] = useState(!threadId);
  const endRef = useRef<HTMLDivElement | null>(null);
  const boxRef = useRef<HTMLTextAreaElement | null>(null);
  const turns = useMemo(() => pairTurns(messages), [messages]);

  useEffect(() => {
    if (!ready || profile) {
      return;
    }
    navigate(`/signin?next=${encodeURIComponent(next)}`, { replace: true });
  }, [navigate, next, profile, ready]);

  useEffect(() => {
    if (!profile) {
      return;
    }
    listChatThreads()
      .then(setThreads)
      .catch(() => setThreads([]));
  }, [threadId, messages.length, profile?.user_id, profile]);

  useEffect(() => {
    if (!threadId || !profile) {
      setMessages([]);
      setCitations([]);
      setHistoryReady(true);
      return;
    }
    let cancelled = false;
    setHistoryReady(false);
    loadChatHistory(threadId)
      .then((data) => {
        if (!cancelled) {
          setMessages(data.messages);
          if (
            data.mode === "quick" ||
            data.mode === "standard" ||
            data.mode === "deep"
          ) {
            setMode(data.mode);
          }
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load thread");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setHistoryReady(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [threadId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const box = boxRef.current;
    if (!box) {
      return;
    }
    box.style.height = "auto";
    box.style.height = `${Math.min(box.scrollHeight, 160)}px`;
  }, [draft]);

  async function submit(event?: FormEvent, text = draft) {
    event?.preventDefault();
    const query = text.trim();
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
      setCitations(report.citations);
      if (!threadId) {
        navigate(`/chat/${report.thread_id}`, { replace: true });
      }
      const history = await loadChatHistory(report.thread_id);
      setMessages(history.messages);
      setThreads(await listChatThreads());
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Research failed");
    } finally {
      setLoading(false);
    }
  }

  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  const empty = historyReady && turns.length === 0 && !loading;

  return (
    <div className={collapsed ? "aimode collapsed" : "aimode"}>
      <ChatSidebar
        open={sidebarOpen}
        collapsed={collapsed}
        threads={threads}
        onClose={() => setSidebarOpen(false)}
        onExpand={() => setCollapsed(false)}
        onCollapse={() => {
          setCollapsed(true);
          setSidebarOpen(false);
        }}
      />
      {sidebarOpen ? (
        <button
          type="button"
          className="scrim"
          aria-label="Close sidebar"
          onClick={() => setSidebarOpen(false)}
        />
      ) : null}
      <section className="aimode-main">
        <header className="aimode-head">
          <button
            type="button"
            className="menu"
            aria-label="Open sidebar"
            onClick={() => {
              setCollapsed(false);
              setSidebarOpen(true);
            }}
          >
            <MenuIcon />
          </button>
          <AppTabs active="research" />
        </header>
        <div className="aimode-frame">
          <div className="aimode-scroll">
          {empty ? (
            <div className="aimode-landing">
              <h1>What's on your mind?</h1>
              <AskBox
                landing
                draft={draft}
                mode={mode}
                loading={loading}
                boxRef={boxRef}
                onDraft={setDraft}
                onMode={setMode}
                onKey={onKey}
                onSubmit={submit}
              />
              <ul className="aimode-ideas">
                {IDEAS.map((idea) => (
                  <li key={idea}>
                    <button
                      type="button"
                      onClick={() => void submit(undefined, idea)}
                      disabled={loading}
                    >
                      <IdeaIcon />
                      {idea}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="aimode-split">
              <div className="aimode-col">
                {turns.map((turn, index) => (
                  <article key={`${turn.query}-${index}`} className="aimode-turn">
                    <p className="query-pill">{turn.query}</p>
                    {turn.answer ? <ReportBody text={turn.answer} /> : null}
                  </article>
                ))}
                {loading ? <p className="status">Researching…</p> : null}
                {error ? <p className="error">{error}</p> : null}
                <div ref={endRef} />
              </div>
              {citations.length > 0 ? (
                <aside className="source-panel" aria-label="Sources">
                  <p className="source-head">Sources</p>
                  {citations.slice(0, 3).map((item) => (
                    <Link
                      key={`${item.material_id}-${item.citation}`}
                      className="source-card"
                      to={`/materials/${item.material_id}`}
                    >
                      <span className="source-copy">
                        <strong>{item.title}</strong>
                        <span>{item.snippet || item.citation}</span>
                      </span>
                      <span className="source-thumb" aria-hidden="true">
                        {(item.title || "D").slice(0, 1)}
                      </span>
                    </Link>
                  ))}
                  {citations.length > 3 ? (
                    <p className="show-all">Show all {citations.length}</p>
                  ) : null}
                </aside>
              ) : null}
            </div>
          )}
        </div>
        {empty ? null : (
        <div className="aimode-dock">
          <AskBox
            draft={draft}
            mode={mode}
            loading={loading}
            boxRef={boxRef}
            onDraft={setDraft}
            onMode={setMode}
            onKey={onKey}
            onSubmit={submit}
          />
        </div>
        )}
        </div>
      </section>
    </div>
  );
}

function pairTurns(messages: ChatHistoryMessage[]) {
  const turns: { query: string; answer: string }[] = [];
  for (let index = 0; index < messages.length; index += 1) {
    const item = messages[index];
    if (!item) {
      continue;
    }
    if (item.role !== "user") {
      continue;
    }
    const next = messages[index + 1];
    turns.push({
      query: item.content,
      answer: next?.role === "assistant" ? next.content : "",
    });
  }
  return turns;
}

function IdeaIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" />
      <path d="M16 16.5 20 20.5" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 7h14M5 12h14M5 17h14" />
    </svg>
  );
}
