from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def post_json(
    url: str,
    payload: dict[str, object],
    *,
    api_key: str,
    timeout: float,
) -> object:
    body = json.dumps(payload).encode()
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"request failed: {url}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"response is not JSON: {url}") from exc
