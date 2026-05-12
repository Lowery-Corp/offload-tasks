import os
from openai import OpenAI


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY must be configured")
if not OPENAI_EMBEDDING_MODEL:
    raise RuntimeError("OPENAI_EMBEDDING_MODEL must be configured")

client = OpenAI(api_key=OPENAI_API_KEY)

def create_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=text,
        encoding_format="float",
    )

    return response.data[0].embedding

def create_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    response = client.embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=texts,
        encoding_format="float",
    )

    return [item.embedding for item in response.data]