import os

from openai import OpenAI, OpenAIError

from schemas.api_request_errors import ApiRequestError


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY must be configured")

client = OpenAI(api_key=OPENAI_API_KEY)


def create_embedding(text: str) -> list[float]:
    return create_embeddings([text])[0]


def create_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    try:
        response = client.embeddings.create(
            model=OPENAI_EMBEDDING_MODEL,
            input=texts,
            encoding_format="float",
        )
    except OpenAIError as exc:
        raise ApiRequestError(f"OpenAI embedding request failed: {exc}") from exc

    return [item.embedding for item in response.data]
