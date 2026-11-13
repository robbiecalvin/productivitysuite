import os
from urllib.parse import urlparse

import requests


class OllamaClient:
    def __init__(
        self,
        model=None,
        base_url=None,
    ):
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("OLLAMA_BASE_URL must be an HTTP(S) URL without credentials, query, or fragment.")

    def chat(self, prompt, system="You are a precise coding assistant.", json_mode=False, generation_options=None):
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {
                        "num_ctx": 8192,
                        "temperature": 0,
                        **(generation_options or {}),
                    },
                    **(
                        {"format": json_mode}
                        if isinstance(json_mode, dict)
                        else ({"format": "json"} if json_mode else {})
                    ),
                },
                timeout=(5, 600),
            )
        except requests.exceptions.Timeout as error:
            raise RuntimeError("Ollama timed out while generating a response.") from error
        except requests.exceptions.ConnectionError as error:
            raise RuntimeError(
                "Cannot connect to Ollama. Start the service or configure OLLAMA_BASE_URL."
            ) from error
        except requests.exceptions.RequestException as error:
            raise RuntimeError("Ollama request failed.") from error

        if not response.ok:
            raise RuntimeError(
                f"Ollama HTTP {response.status_code}: {response.text[:500]}"
            )

        try:
            data = response.json()
        except ValueError as error:
            raise RuntimeError("Ollama returned invalid JSON.") from error

        if not isinstance(data, dict):
            raise RuntimeError("Ollama returned an unexpected response.")

        if data.get("done_reason") == "length":
            raise RuntimeError(
                "Model reached its output limit. Generate a smaller component."
            )

        message = data.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama response is missing its message.")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama returned no usable text.")

        return content


if __name__ == "__main__":
    client = OllamaClient()
    print("Connecting to Ollama. The first response may take a while...")
    try:
        print(client.chat("Reply with exactly: Model connection successful"))
    except RuntimeError as error:
        raise SystemExit(f"Error: {error}")
