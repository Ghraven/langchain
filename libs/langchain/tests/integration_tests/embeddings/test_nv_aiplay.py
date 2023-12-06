"""Test NVIDIA AI Playground Embeddings.

Note: These tests are designed to validate the functionality of NVAIPlayEmbeddings.
"""
from langchain.embeddings import NVAIPlayEmbeddings


def test_nvai_play_embedding_documents() -> None:
    """Test NVAIPlay embeddings for documents."""
    documents = ["foo bar"]
    embedding = NVAIPlayEmbeddings()
    output = embedding.embed_documents(documents)
    assert len(output) == 1
    assert len(output[0]) == 1024  # Assuming embedding size is 2048


def test_nvai_play_embedding_documents_multiple() -> None:
    """Test NVAIPlay embeddings for multiple documents."""
    documents = ["foo bar", "bar foo", "foo"]
    embedding = NVAIPlayEmbeddings()
    output = embedding.embed_documents(documents)
    assert len(output) == 3
    assert all(len(doc) == 1024 for doc in output)


def test_nvai_play_embedding_query() -> None:
    """Test NVAIPlay embeddings for a single query."""
    query = "foo bar"
    embedding = NVAIPlayEmbeddings()
    output = embedding.embed_query(query)
    assert len(output) == 1024


async def test_nvai_play_embedding_async_query() -> None:
    """Test NVAIPlay async embeddings for a single query."""
    query = "foo bar"
    embedding = NVAIPlayEmbeddings()
    output = await embedding.aembed_query(query)
    assert len(output) == 1024


async def test_nvai_play_embedding_async_documents() -> None:
    """Test NVAIPlay async embeddings for multiple documents."""
    documents = ["foo bar", "bar foo", "foo"]
    embedding = NVAIPlayEmbeddings()
    output = await embedding.aembed_batch_documents(documents)
    assert len(output) == 3
    assert all(len(doc) == 1024 for doc in output)


async def test_nvai_play_embedding_async_queries() -> None:
    """Test NVAIPlay async embeddings for multiple queries."""
    queries = ["What's the weather like?", "Tell me a joke."]
    embedding = NVAIPlayEmbeddings()
    output = await embedding.aembed_batch_queries(queries)
    assert len(output) == 2
    assert all(len(query) == 1024 for query in output)
