import os
from openai import OpenAI


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY must be configured")

client = OpenAI(api_key=OPENAI_API_KEY)

def create_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float",
    )

    return response.data[0].embedding

def create_embeddings(text: str) -> list[float]:

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float",
    )
    item = response.data[0]

    return item.embedding
