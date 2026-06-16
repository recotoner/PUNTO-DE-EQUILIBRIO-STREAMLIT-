"""External integration clients."""

from .n8n_client import N8NWebhookResponse, enviar_payload_n8n

__all__ = ["N8NWebhookResponse", "enviar_payload_n8n"]
