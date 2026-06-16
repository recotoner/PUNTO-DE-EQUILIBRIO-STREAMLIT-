"""Manual n8n webhook transport for the structured agent payload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class N8NWebhookResponse:
    status_code: int
    texto: str
    json_data: Any | None


def enviar_payload_n8n(
    webhook_url: str,
    payload: dict[str, Any],
    *,
    timeout: float = 75,
) -> N8NWebhookResponse:
    response = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    try:
        json_data = response.json()
    except requests.exceptions.JSONDecodeError:
        json_data = None
    return N8NWebhookResponse(
        status_code=response.status_code,
        texto=response.text,
        json_data=json_data,
    )
