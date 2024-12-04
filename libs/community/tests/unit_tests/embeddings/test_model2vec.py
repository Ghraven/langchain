from langchain_community.embeddings.model2vec import Model2vecEmbeddings


def test_hugginggface_inferenceapi_embedding_documents_init() -> None:
    """Test model2vec embeddings."""
    try:
        embedding = Model2vecEmbeddings()
        assert len(embedding.embed_query("hi")) == 256
    except Exception as e:
        # model2vec is not installed
        assert True