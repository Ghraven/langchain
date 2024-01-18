"""Test VDMS Vector Search functionality."""
import logging
import os

import pytest
from langchain_core.documents import Document

from langchain_community.vectorstores import VDMSVectorSearch
from langchain_community.vectorstores.vdms import embedding2bytes
from tests.integration_tests.vectorstores.fake_embeddings import (
    ConsistentFakeEmbeddings,
    FakeEmbeddings,
)

logging.basicConfig(level=logging.DEBUG)

"""
cd tests/integration_tests/vectorstores/docker-compose
docker-compose -f vdms.yml up

By default runs against local docker instance of VDMS using port (VDMS_DBPORT) 55555.
Use the following to specify different port:
VDMS_DBPORT=<port> docker-compose -f vdms.yml up
"""


@pytest.mark.requires("vdms")
class TestVDMS:
    @classmethod
    def setup_class(cls) -> None:
        db_host = "localhost"
        db_port = os.getenv("VDMS_DBPORT", 55557)
        print(f"VDMS using {db_host} and {db_port}")
        cls.connection_args = {"host": db_host, "port": db_port}

    # @classmethod
    # def teardown_class(cls) -> None:
    #     cls.client.disconnect()
    #     print("Disconnected VDMS")

    def test_init_from_client(self) -> None:
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        _ = VDMSVectorSearch(
            embedding_function=embedding_function,
            embedding_dimension=embedding_dimension,
            connection_args=self.connection_args,
        )

    def test_from_texts_with_metadatas(self) -> None:
        """Test end to end construction and search."""
        collection_name = "test_from_texts_with_metadatas"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        texts = ["foo", "bar", "baz"]
        metadatas = [{"page": str(i)} for i in range(len(texts))]
        docsearch = VDMSVectorSearch.from_texts(
            texts=texts,
            embedding_function=embedding_function,
            metadatas=metadatas,
            embedding_dimension=embedding_dimension,
            collection_name=collection_name,
            connection_args=self.connection_args,
        )
        output = docsearch.similarity_search("foo", k=1)
        assert output == [Document(page_content="foo", metadata={"page": "0"})]

    def test_from_texts_with_metadatas_with_scores(self) -> None:
        """Test end to end construction and scored search."""
        collection_name = "test_from_texts_with_metadatas_with_scores"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        texts = ["foo", "bar", "baz"]
        metadatas = [{"page": str(i)} for i in range(len(texts))]
        docsearch = VDMSVectorSearch.from_texts(
            texts=texts,
            embedding_function=embedding_function,
            metadatas=metadatas,
            embedding_dimension=embedding_dimension,
            collection_name=collection_name,
            connection_args=self.connection_args,
        )
        output = docsearch.similarity_search_with_score("foo", k=1)
        assert output == [(Document(page_content="foo", metadata={"page": "0"}), 0.0)]

    def test_from_texts_with_metadatas_with_scores_using_vector(self) -> None:
        """Test end to end construction and scored search, using embedding vector."""
        collection_name = "test_from_texts_with_metadatas_with_scores_using_vector"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        texts = ["foo", "bar", "baz"]
        metadatas = [{"page": str(i)} for i in range(len(texts))]
        docsearch = VDMSVectorSearch.from_texts(
            texts=texts,
            embedding_function=embedding_function,
            metadatas=metadatas,
            embedding_dimension=embedding_dimension,
            collection_name=collection_name,
            connection_args=self.connection_args,
        )
        output = docsearch._similarity_search_with_relevance_scores("foo", k=1)
        assert output == [(Document(page_content="foo", metadata={"page": "0"}), 0.0)]

    def test_search_filter(self) -> None:
        """Test end to end construction and search with metadata filtering."""
        collection_name = "test_search_filter"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        texts = ["far", "bar", "baz"]
        metadatas = [{"first_letter": "{}".format(text[0])} for text in texts]
        docsearch = VDMSVectorSearch.from_texts(
            texts=texts,
            embedding_function=embedding_function,
            metadatas=metadatas,
            embedding_dimension=embedding_dimension,
            collection_name=collection_name,
            connection_args=self.connection_args,
        )
        output = docsearch.similarity_search(
            "far", k=1, filter={"first_letter": ["==", "f"]}
        )
        assert output == [Document(page_content="far", metadata={"first_letter": "f"})]
        output = docsearch.similarity_search(
            "far", k=2, filter={"first_letter": ["==", "b"]}
        )
        assert output == [Document(page_content="bar", metadata={"first_letter": "b"})]

    def test_search_filter_with_scores(self) -> None:
        """Test end to end construction and scored search with metadata filtering."""
        collection_name = "test_search_filter_with_scores"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        texts = ["far", "bar", "baz"]
        metadatas = [{"first_letter": "{}".format(text[0])} for text in texts]
        docsearch = VDMSVectorSearch.from_texts(
            texts=texts,
            embedding_function=embedding_function,
            metadatas=metadatas,
            embedding_dimension=embedding_dimension,
            collection_name=collection_name,
            connection_args=self.connection_args,
        )
        output = docsearch.similarity_search_with_score(
            "far", k=1, filter={"first_letter": ["==", "f"]}
        )
        assert output == [
            (Document(page_content="far", metadata={"first_letter": "f"}), 0.0)
        ]

        output = docsearch.similarity_search_with_score(
            "far", k=2, filter={"first_letter": ["==", "b"]}
        )
        assert output == [
            (Document(page_content="bar", metadata={"first_letter": "b"}), 1.0)
        ]

    def test_mmr(self) -> None:
        """Test end to end construction and search."""
        collection_name = "test_mmr"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        texts = ["foo", "bar", "baz"]
        docsearch = VDMSVectorSearch.from_texts(
            texts=texts,
            embedding_function=embedding_function,
            embedding_dimension=embedding_dimension,
            collection_name=collection_name,
            connection_args=self.connection_args,
        )
        output = docsearch.max_marginal_relevance_search("foo", k=1)
        assert output == [Document(page_content="foo")]

    def test_mmr_by_vector(self) -> None:
        """Test end to end construction and search."""
        collection_name = "test_mmr_by_vector"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        texts = ["foo", "bar", "baz"]
        docsearch = VDMSVectorSearch.from_texts(
            texts=texts,
            embedding_function=embedding_function,
            embedding_dimension=embedding_dimension,
            collection_name=collection_name,
            connection_args=self.connection_args,
        )
        embedded_query = embedding_function.embed_query("foo")
        output = docsearch.max_marginal_relevance_search_by_vector(embedded_query, k=1)
        assert output == [Document(page_content="foo")]

    def test_with_include_parameter(self) -> None:
        """Test end to end construction and include parameter."""
        collection_name = "test_with_include_parameter"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        texts = ["foo", "bar", "baz"]
        docsearch = VDMSVectorSearch.from_texts(
            texts=texts,
            embedding_function=embedding_function,
            embedding_dimension=embedding_dimension,
            collection_name=collection_name,
            connection_args=self.connection_args,
        )
        response, response_array = docsearch.get(
            collection_name, include=["embeddings"]
        )
        assert response_array != []
        response, response_array = docsearch.get(collection_name)
        assert response_array == []

    def test_update_document(self) -> None:
        """Test the update_document function in the VDMS class."""
        collection_name = "test_update_document"

        # Make a consistent embedding
        embedding_function = ConsistentFakeEmbeddings()
        embedding_dimension = 10

        # Initial document content and id
        initial_content = "foo"
        document_id = "doc1"

        # Create an instance of Document with initial content and metadata
        original_doc = Document(page_content=initial_content, metadata={"page": "0"})

        # Initialize a VDMS instance with the original document
        docsearch = VDMSVectorSearch.from_documents(
            connection_args=self.connection_args,
            collection_name=collection_name,
            documents=[original_doc],
            embedding_function=embedding_function,
            embedding_dimension=embedding_dimension,
            ids=[document_id],
        )
        response, old_embedding = docsearch.get(
            collection_name,
            constraints={"id": ["==", document_id]},
            include=["metadata", "embeddings"],
        )
        # old_embedding = response_array[0]

        # Define updated content for the document
        updated_content = "updated foo"

        # Create a new Document instance with the updated content and the same id
        updated_doc = Document(page_content=updated_content, metadata={"page": "0"})

        # Update the document in the VDMS instance
        docsearch.update_document(
            collection_name, document_id=document_id, document=updated_doc
        )

        # Perform a similarity search with the updated content
        output = docsearch.similarity_search(updated_content, k=1)

        # Assert that the updated document is returned by the search
        assert output == [
            Document(page_content=updated_content, metadata={"page": "0"})
        ]

        # Assert that the new embedding is correct
        response, new_embedding = docsearch.get(
            collection_name,
            constraints={"id": ["==", document_id]},
            include=["metadata", "embeddings"],
        )
        # new_embedding = response_array[0]

        assert new_embedding[0] == embedding2bytes(
            embedding_function.embed_documents([updated_content])[0]
        )
        assert new_embedding != old_embedding

    def test_with_relevance_score(self) -> None:
        """Test to make sure the relevance score is scaled to 0-1."""
        collection_name = "test_with_relevance_score"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        texts = ["foo", "bar", "baz"]
        metadatas = [{"page": str(i)} for i in range(len(texts))]
        docsearch = VDMSVectorSearch.from_texts(
            texts=texts,
            embedding_function=embedding_function,
            metadatas=metadatas,
            embedding_dimension=embedding_dimension,
            collection_name=collection_name,
            connection_args=self.connection_args,
        )
        output = docsearch.similarity_search_with_relevance_scores("foo", k=3)
        assert output == [
            (Document(page_content="foo", metadata={"page": "0"}), 0.0),
            (Document(page_content="bar", metadata={"page": "1"}), 0.25),
            (Document(page_content="baz", metadata={"page": "2"}), 1.0),
        ]

    def test_add_documents_no_metadata(self) -> None:
        collection_name = "test_add_documents_no_metadata"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        db = VDMSVectorSearch(
            collection_name=collection_name,
            embedding_function=embedding_function,
            embedding_dimension=embedding_dimension,
            connection_args=self.connection_args,
        )
        db.add_documents([Document(page_content="foo")])

    def test_add_documents_mixed_metadata(self) -> None:
        collection_name = "test_add_documents_mixed_metadata"
        embedding_function = FakeEmbeddings()
        embedding_dimension = 10
        db = VDMSVectorSearch(
            collection_name=collection_name,
            embedding_function=embedding_function,
            embedding_dimension=embedding_dimension,
            connection_args=self.connection_args,
        )

        docs = [
            Document(page_content="foo"),
            Document(page_content="bar", metadata={"baz": 1}),
        ]
        ids = ["10", "11"]
        actual_ids = db.add_documents(docs, ids=ids)
        assert actual_ids == ids

        search = db.similarity_search("foo bar", k=2)
        assert sorted(search, key=lambda d: d.page_content) == sorted(
            docs, key=lambda d: d.page_content
        )
