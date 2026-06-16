import unittest
from unittest.mock import Mock, patch

import requests

from src.integrations.n8n_client import enviar_payload_n8n


class N8NClientTests(unittest.TestCase):
    @patch("src.integrations.n8n_client.requests.post")
    def test_sends_exact_received_payload(self, post_mock):
        payload = {
            "metadata": {"nombre_empresa": "DAG"},
            "punto_equilibrio": {"pe_mensual": 46_812_550},
            "instrucciones_agente": ["Usar exclusivamente los datos del payload."],
        }
        response = Mock()
        response.status_code = 200
        response.text = '{"ok": true}'
        response.json.return_value = {"ok": True}
        post_mock.return_value = response

        result = enviar_payload_n8n(
            "https://n8n.example/webhook/test",
            payload,
            timeout=75,
        )

        post_mock.assert_called_once_with(
            "https://n8n.example/webhook/test",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=75,
        )
        self.assertIs(post_mock.call_args.kwargs["json"], payload)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.texto, '{"ok": true}')
        self.assertEqual(result.json_data, {"ok": True})

    @patch("src.integrations.n8n_client.requests.post")
    def test_preserves_text_response_when_body_is_not_json(self, post_mock):
        response = Mock()
        response.status_code = 202
        response.text = "accepted"
        response.json.side_effect = requests.exceptions.JSONDecodeError(
            "invalid json",
            "accepted",
            0,
        )
        post_mock.return_value = response

        result = enviar_payload_n8n(
            "https://n8n.example/webhook/test",
            {"payload": True},
        )

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.texto, "accepted")
        self.assertIsNone(result.json_data)


if __name__ == "__main__":
    unittest.main()
