import { FormEvent, KeyboardEvent, RefObject } from "react";

import type { AgentMode } from "../api/types";

type Props = {
  landing?: boolean;
  draft: string;
  mode: AgentMode;
  loading: boolean;
  boxRef: RefObject<HTMLTextAreaElement | null>;
  onDraft: (value: string) => void;
  onMode: (value: AgentMode) => void;
  onKey: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: (event: FormEvent) => void;
};

export function AskBox({
  landing = false,
  draft,
  mode,
  loading,
  boxRef,
  onDraft,
  onMode,
  onKey,
  onSubmit,
}: Props) {
  return (
    <form
      className={landing ? "ask-box landing" : "ask-box"}
      onSubmit={onSubmit}
    >
      <textarea
        ref={boxRef}
        value={draft}
        onChange={(event) => onDraft(event.target.value)}
        onKeyDown={onKey}
        placeholder="Ask anything"
        aria-label="Research question"
        disabled={loading}
        rows={landing ? 2 : 1}
      />
      <span className="plus" aria-hidden="true">
        +
      </span>
      <select
        className="budget"
        value={mode}
        onChange={(event) => onMode(event.target.value as AgentMode)}
        aria-label="Research budget"
        disabled={loading}
      >
        <option value="quick">Quick</option>
        <option value="standard">Standard</option>
        <option value="deep">Deep</option>
      </select>
    </form>
  );
}
