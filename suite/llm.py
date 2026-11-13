import requests


class OllamaClient:
    def __init__(
        self,
        model="qwen2.5-coder:7b",
        base_url="http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")

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
        except requests.exceptions.ConnectionError as error:
            raise RuntimeError(
                "Cannot connect to Ollama. Open the Ollama app."
            ) from error
        except requests.exceptions.Timeout as error:
            raise RuntimeError(
                "Ollama timed out while generating a response."
            ) from error

        if not response.ok:
            raise RuntimeError(
                f"Ollama HTTP {response.status_code}: {response.text}"
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
