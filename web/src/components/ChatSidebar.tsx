import { Link, NavLink } from "react-router-dom";

import type { ChatThreadSummary } from "../api/types";
import { BrandMark } from "./BrandMark";

type Props = {
  open: boolean;
  collapsed: boolean;
  threads: ChatThreadSummary[];
  onClose: () => void;
  onExpand: () => void;
  onCollapse: () => void;
};

export function ChatSidebar({
  open,
  collapsed,
  threads,
  onClose,
  onExpand,
  onCollapse,
}: Props) {
  return (
    <aside className={open ? "gpt-side open" : "gpt-side"}>
      <div className="side-top">
        <BrandMark glyph />
        <button
          type="button"
          className="icon-btn side-toggle"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={collapsed ? onExpand : onCollapse}
        >
          <PanelIcon />
        </button>
      </div>
      <Link
        className="side-item side-new"
        to="/chat"
        onClick={onClose}
        title="New thread"
        aria-label="New thread"
      >
        <PenIcon />
        <span>New thread</span>
      </Link>
      <p className="side-label">Recents</p>
      <nav className="thread-list" aria-label="Chat history">
        {threads.length === 0 ? (
          <p className="side-empty">No chats yet</p>
        ) : null}
        {threads.map((item) => (
          <NavLink
            key={item.thread_id}
            to={`/chat/${item.thread_id}`}
            className="thread-link"
            onClick={onClose}
          >
            {item.title}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

function PanelIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
      <path d="M9.5 4.5v15" />
    </svg>
  );
}

function PenIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 19.5h4l10-10-4-4-10 10v4z" />
      <path d="M13.5 6.5 17.5 10.5" />
    </svg>
  );
}
