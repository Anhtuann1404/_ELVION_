"""Bounded numeric-loopback Ollama vision transport, separate from text planning."""
import base64
from http.client import HTTPException
import json
from math import isfinite
import re
import socket
from time import perf_counter_ns
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from elvion.models.structured import strict_json

MAX_RESPONSE = 32 * 1024
MAX_REQUEST = 7 * 1024 * 1024 + 16 * 1024


class VisionProviderError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OllamaVisionProvider:
    def __init__(self, *, model: str, base_url: str = "http://127.0.0.1:11434", timeout: float = 45,
                 max_tokens: int = 128):
        if (type(model) is not str or len(model) > 128 or
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9._-]+)?", model) or
                "cloud" in model.casefold()):
            raise ValueError("Choose an installed local model")
        if type(timeout) not in (int, float) or not isfinite(timeout) or not 1 <= timeout <= 120:
            raise ValueError("Timeout must be 1..120 seconds")
        if type(max_tokens) is not int or not 64 <= max_tokens <= 1024:
            raise ValueError("Token budget must be 64..1024")
        try:
            url = urlsplit(base_url)
            port = url.port or 11434
            if (url.scheme != "http" or url.hostname != "127.0.0.1" or url.username is not None or
                    url.password is not None or url.path not in ("", "/") or url.query or url.fragment or
                    not 1 <= port <= 65535):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Endpoint must be numeric loopback HTTP") from None
        self.base_url = f"http://127.0.0.1:{port}"
        self.model, self.timeout = model, timeout
        self.max_tokens = max_tokens
        self.last_inference_ms = None
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _request(self, path, payload):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(body) > MAX_REQUEST:
            raise VisionProviderError("MODEL_INVALID_RESPONSE")
        request = Request(self.base_url + path, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise VisionProviderError("MODEL_INVALID_RESPONSE")
            envelope = strict_json(raw.decode("utf-8"))
            if type(envelope) is not dict:
                raise ValueError
            return envelope
        except VisionProviderError:
            raise
        except (TimeoutError, socket.timeout):
            raise VisionProviderError("MODEL_TIMEOUT") from None
        except HTTPError as error:
            error.close()
            raise VisionProviderError("MODEL_UNAVAILABLE") from None
        except URLError as error:
            code = "MODEL_TIMEOUT" if isinstance(error.reason, (TimeoutError, socket.timeout)) else "MODEL_UNAVAILABLE"
            raise VisionProviderError(code) from None
        except OSError:
            raise VisionProviderError("MODEL_UNAVAILABLE") from None
        except (ValueError, TypeError, UnicodeError, RecursionError, HTTPException):
            raise VisionProviderError("MODEL_INVALID_RESPONSE") from None

    def check_local(self):
        info = self._request("/api/show", {"model": self.model})
        capabilities = info.get("capabilities")
        if (info.get("remote_host") or info.get("remote_model") or
                type(info.get("model_info")) is not dict or not info["model_info"] or
                type(capabilities) is not list or "vision" not in capabilities):
            raise VisionProviderError("MODEL_UNAVAILABLE")

    def complete(self, *, image_png: bytes, target: str, role: str, schema: dict, system: str,
                 candidates=None) -> str:
        self.last_inference_ms = None
        self.check_local()
        started = perf_counter_ns()
        content = f"Find the {role} matching this goal: {target}"
        if candidates is not None:
            content = json.dumps({'target':target, 'role':role, 'ocr_candidates':candidates}, ensure_ascii=False)
        envelope = self._request("/api/chat", {
            "model": self.model, "stream": False, "think": False, "format": schema,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": content,
                          "images": [base64.b64encode(image_png).decode("ascii")]}],
            "options": {"temperature": 0, "num_predict": self.max_tokens, "num_ctx": 4096},
        })
        self.last_inference_ms = round((perf_counter_ns() - started) / 1_000_000, 3)
        message = envelope.get("message")
        if (envelope.get("done") is not True or envelope.get("remote_host") or envelope.get("remote_model") or
                envelope.get("done_reason") == "length" or type(message) is not dict or
                message.get("role") != "assistant" or message.get("tool_calls") or
                type(message.get("content")) is not str or
                not message["content"].strip() or len(message["content"].encode("utf-8")) > 8192):
            raise VisionProviderError("MODEL_INVALID_RESPONSE")
        return message["content"]
