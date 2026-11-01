"""Vision transport rejects nonlocal endpoints, malformed replies and unsupported models."""
import io
import json
import socket
import unittest
from unittest.mock import Mock

from elvion.vision.ollama import OllamaVisionProvider, VisionProviderError


class Response(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


class ProviderTests(unittest.TestCase):
    def test_loopback_and_model_validation(self):
        for url in ("https://127.0.0.1:11434", "http://localhost:11434", "http://192.168.1.2:11434",
                    "http://127.0.0.1:11434/path", "http://user@127.0.0.1:11434"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OllamaVisionProvider(model="qwen3.5:4b", base_url=url)
        for model in ("", "vision.cloud", "../model", "bad name"):
            with self.subTest(model=model), self.assertRaises(ValueError):
                OllamaVisionProvider(model=model)
        for timeout in (0, 121, True, float("nan")):
            with self.assertRaises(ValueError):
                OllamaVisionProvider(model="qwen3.5:4b", timeout=timeout)
        for budget in (0, 1025, True, 128.0):
            with self.assertRaises(ValueError):
                OllamaVisionProvider(model='qwen3.5:4b', max_tokens=budget)

    def test_metadata_vision_and_local_required_before_image(self):
        provider = OllamaVisionProvider(model="qwen3.5:4b")
        provider._request = Mock(return_value={"model_info": {"arch": "qwen"}, "capabilities": ["completion", "vision"]})
        provider.check_local()
        provider._request.assert_called_once_with("/api/show", {"model": "qwen3.5:4b"})
        for info in ({"model_info": {"arch": "qwen"}, "capabilities": ["completion"]},
                     {"model_info": {"arch": "qwen"}, "capabilities": ["vision"], "remote_host": "private"},
                     {"model_info": {}, "capabilities": ["vision"]}):
            provider._request.return_value = info
            with self.assertRaises(VisionProviderError) as caught:
                provider.check_local()
            self.assertEqual(caught.exception.code, "MODEL_UNAVAILABLE")

    def test_image_only_in_chat_and_no_answer_or_action_fields(self):
        provider = OllamaVisionProvider(model="qwen3.5:4b")
        provider._request = Mock(side_effect=[{"model_info": {"arch": "qwen"}, "capabilities": ["vision"]},
                                               {"done": True, "message": {"role": "assistant", "content": '{"version":1,"status":"not_found","box":null}'}}])
        content = provider.complete(image_png=b"synthetic", target="Search", role="textbox", schema={"type": "object"}, system="Locate")
        self.assertIn("not_found", content)
        path, payload = provider._request.call_args_list[1].args
        self.assertEqual(path, "/api/chat")
        self.assertEqual(payload["messages"][1]["images"], ["c3ludGhldGlj"])
        self.assertNotIn("bbox", json.dumps(payload))
        self.assertNotIn("javascript", json.dumps(payload).lower())
        self.assertEqual(payload['options']['num_predict'], 128)

    def test_explicit_budget_and_metadata_failure_clear_old_latency(self):
        provider = OllamaVisionProvider(model='qwen3.5:4b', max_tokens=512)
        provider._request = Mock(side_effect=[{'model_info': {'arch':'qwen'}, 'capabilities':['vision']},
            {'done': True, 'message': {'role':'assistant', 'content':'{"version":2,"boxes":[]}'}}])
        provider.complete(image_png=b'x', target='Search', role='textbox', schema={}, system='Locate')
        self.assertEqual(provider._request.call_args.args[1]['options']['num_predict'], 512)
        provider._request.side_effect = VisionProviderError('MODEL_UNAVAILABLE')
        with self.assertRaises(VisionProviderError):
            provider.complete(image_png=b'x', target='Search', role='textbox', schema={}, system='Locate')
        self.assertIsNone(provider.last_inference_ms)

    def test_malformed_output_timeout_and_size_limit(self):
        provider = OllamaVisionProvider(model="qwen3.5:4b")
        for response in ({"done": False, "message": {"role": "assistant", "content": "{}"}},
                         {"done": True, "message": {"role": "assistant", "content": "{}", "tool_calls": [1]}},
                         {"done": True, "message": {"role": "assistant", "content": "{}"}, "remote_host": "private"}):
            provider._request = Mock(side_effect=[{"model_info": {"arch": "qwen"}, "capabilities": ["vision"]}, response])
            with self.assertRaises(VisionProviderError) as caught:
                provider.complete(image_png=b"x", target="Search", role="textbox", schema={}, system="Locate")
            self.assertEqual(caught.exception.code, "MODEL_INVALID_RESPONSE")
        class TimeoutOpener:
            def open(self, *args, **kwargs):
                raise socket.timeout
        provider = OllamaVisionProvider(model="qwen3.5:4b")
        provider._opener = TimeoutOpener()
        with self.assertRaises(VisionProviderError) as caught:
            provider.check_local()
        self.assertEqual(caught.exception.code, "MODEL_TIMEOUT")
        with self.assertRaises(VisionProviderError) as caught:
            provider._request("/api/chat", {"huge": "x" * (8 * 1024 * 1024)})
        self.assertEqual(caught.exception.code, "MODEL_INVALID_RESPONSE")


if __name__ == "__main__":
    unittest.main()
