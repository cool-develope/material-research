from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OpenAICompatClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 120,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def complete_json(self, prompt: str) -> dict[str, object]:
        body = json.dumps(_chat_body(self._model, prompt)).encode()
        request = Request(
            self._url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read())
        except HTTPError as exc:
            raise RuntimeError(f"LLM HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("LLM request failed") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM response is not JSON") from exc
        content = _message_content(payload)
        return _parse_json(content)


def _chat_body(model: str, prompt: str) -> dict[str, object]:
    return {
        "model": model,
        "temperature": 0,
        "reasoning_effort": "none",
        "messages": [
            {
                "role": "system",
                "content": "Reply with a JSON object only. No markdown.",
            },
            {"role": "user", "content": prompt},
        ],
    }


def _message_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise RuntimeError("LLM response is not an object")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("LLM response has no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise RuntimeError("LLM choice is not an object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("LLM message is missing")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM content is empty")
    return content


def _parse_json(content: str) -> dict[str, object]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM content is not JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("LLM JSON is not an object")
    return parsed
