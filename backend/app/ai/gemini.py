import httpx

from ..config import get_settings
from .provider import EmbedResult, GenerateResult, estimate_tokens, l2_normalize

BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    """Google Gemini over REST. The API key is sent in a header (never in the URL, so it
    cannot leak into logs) and is read only from the environment."""

    name = "gemini"

    def __init__(self) -> None:
        self._s = get_settings()
        self._headers = {"x-goog-api-key": self._s.gemini_api_key, "content-type": "application/json"}

    async def embed(self, texts: list[str], *, task: str = "document") -> EmbedResult:
        s = self._s
        model = s.gemini_embed_model
        task_type = "RETRIEVAL_QUERY" if task == "query" else "RETRIEVAL_DOCUMENT"
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=s.ai_timeout_seconds) as client:
            for i in range(0, len(texts), 50):  # batchEmbedContents limit
                chunk = texts[i:i + 50]
                body = {"requests": [{
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": t}]},
                    "taskType": task_type,
                    "outputDimensionality": s.embed_dim,
                } for t in chunk]}
                r = await client.post(f"{BASE}/models/{model}:batchEmbedContents", json=body, headers=self._headers)
                r.raise_for_status()
                # Truncated (Matryoshka) vectors must be re-normalised for cosine search.
                vectors += [l2_normalize(e["values"]) for e in r.json()["embeddings"]]
        tokens = sum(estimate_tokens(t) for t in texts)
        cost = int(tokens * s.embed_cost_per_mtok_usd)  # micro-USD: tokens/1e6 * $/Mtok * 1e6
        return EmbedResult(vectors, tokens, model, self.name, cost)

    async def generate(self, system: str, user: str, *, max_output_tokens: int = 512,
                       json_schema: dict | None = None) -> GenerateResult:
        s = self._s
        gen_cfg: dict = {"maxOutputTokens": max_output_tokens, "temperature": 0.2}
        if json_schema:
            gen_cfg |= {"responseMimeType": "application/json", "responseSchema": json_schema}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": gen_cfg,
        }
        async with httpx.AsyncClient(timeout=s.ai_timeout_seconds) as client:
            r = await client.post(f"{BASE}/models/{s.gemini_chat_model}:generateContent", json=body, headers=self._headers)
            r.raise_for_status()
        data = r.json()
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        usage = data.get("usageMetadata", {})
        return GenerateResult(text, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0),
                              s.gemini_chat_model, self.name, 0)
