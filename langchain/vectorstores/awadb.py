"""Wrapper around AwaDB for embedding vectors"""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Set, Tuple, Type

import numpy as np

from langchain.docstore.document import Document
from langchain.embeddings.base import Embeddings
from langchain.vectorstores.base import VectorStore
from langchain.vectorstores.utils import maximal_marginal_relevance

# from pydantic import BaseModel, Field, root_validator


if TYPE_CHECKING:
    import awadb

logger = logging.getLogger()
DEFAULT_TOPN = 4


class AwaDB(VectorStore):
    """Interface implemented by AwaDB vector stores."""

    _DEFAULT_TABLE_NAME = "langchain_awadb"

    def __init__(
        self,
        table_name: str = _DEFAULT_TABLE_NAME,
        embedding: Optional[Embeddings] = None,
        log_and_data_dir: Optional[str] = None,
        client: Optional[awadb.Client] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with AwaDB client.
        Args:
            table_name: Iterable of strings to add to the vectorstore.
            embedding: Optional list of metadatas associated with the texts.
            log_and_data_dir: Optional whether to duplicate texts.
            client: Optional AwaDB client.
            kwargs: any possible extend parameters in the future.

        Returns:
            None.
        """
        try:
            import awadb
        except ImportError:
            raise ValueError(
                "Could not import awadb python package. "
                "Please install it with `pip install awadb`."
            )

        if client is not None:
            self.awadb_client = client
        else:
            if log_and_data_dir is not None:
                self.awadb_client = awadb.Client(log_and_data_dir)
            else:
                self.awadb_client = awadb.Client()

        if table_name == self._DEFAULT_TABLE_NAME:
            table_name += "_"
            table_name += str(uuid.uuid4()).split("-")[-1]

        self.awadb_client.Create(table_name)
        self.table2embeddings: dict[str, Embeddings] = {}
        if embedding is not None:
            self.table2embeddings[table_name] = embedding
        self.using_table_name = table_name

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        is_duplicate_texts: Optional[bool] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Run more texts through the embeddings and add to the vectorstore.
        Args:
            texts: Iterable of strings to add to the vectorstore.
            metadatas: Optional list of metadatas associated with the texts.
            is_duplicate_texts: Optional whether to duplicate texts.
            kwargs: any possible extend parameters in the future.

        Returns:
            List of ids from adding the texts into the vectorstore.
        """
        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        embeddings = None
        if self.using_table_name in self.table2embeddings:
            embeddings = self.table2embeddings[self.using_table_name].embed_documents(
                list(texts)
            )

        return self.awadb_client.AddTexts(
            "embedding_text",
            "text_embedding",
            texts,
            embeddings,
            metadatas,
            is_duplicate_texts,
        )

    def load_local(
        self,
        table_name: str,
        **kwargs: Any,
    ) -> bool:
        """Load the local specified table.

        Args:
            table_name: Table name
            kwargs: Any possible extend parameters in the future.

        Returns:
            Success or failure of loading the local specified table
        """

        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        return self.awadb_client.Load(table_name)

    def similarity_search(
        self,
        query: str,
        k: int = DEFAULT_TOPN,
        **kwargs: Any,
    ) -> List[Document]:
        """The most k similar documents of the specified text query.

        Args:
            query: Text query
            k: The most k similar documents of the text query
            kwargs: Any possible extend parameters in the future.

        Returns:
            The most k similar documents of the specified text query
        """

        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        embedding = None
        if self.using_table_name in self.table2embeddings:
            embedding = self.table2embeddings[self.using_table_name].embed_query(query)
        else:
            from awadb import llm_embedding

            llm = llm_embedding.LLMEmbedding()
            embedding = llm.Embedding(query)

        not_include_fields: Set[str] = {"text_embedding", "_id", "score"}
        return self.similarity_search_by_vector(
            embedding, k, not_include_fields_in_metadata=not_include_fields
        )

    def similarity_search_with_score(
        self,
        query: str,
        k: int = DEFAULT_TOPN,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """The most k similar documents and scores of the specified query.

        Args:
            query: Text query
            k: The most k similar documents of the text query
            kwargs: Any possible extend parameters in the future.

        Returns:
            The most k similar documents of the specified text query
            0 is dissimilar, 1 is the most similar.
        """

        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        embedding = None
        if self.using_table_name in self.table2embeddings:
            embedding = self.table2embeddings[self.using_table_name].embed_query(query)
        else:
            from awadb import llm_embedding

            llm = llm_embedding.LLMEmbedding()
            embedding = llm.Embedding(query)

        results: List[Tuple[Document, float]] = []

        dists: List[float] = []
        not_include_fields: Set[str] = {"text_embedding", "_id", "score"}
        retrieval_docs = self.similarity_search_by_vector(
            embedding,
            k,
            scores=dists,
            not_include_fields_in_metadata=not_include_fields,
        )

        doc_no = 0
        for doc in retrieval_docs:
            doc_tuple = (doc, dists[doc_no])
            results.append(doc_tuple)
            doc_no = doc_no + 1

        return results

    def similarity_search_with_relevance_scores(
        self,
        query: str,
        k: int = DEFAULT_TOPN,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Return docs the most similar to the text query.

        Args:
            query: Text query.
            k: Number of the most similar documents to return. Defaults to 4.

        Returns:
            List of Documents the most similar to the text query.
        """

        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        embedding = None
        if self.using_table_name in self.table2embeddings:
            embedding = self.table2embeddings[self.using_table_name].embed_query(query)

        show_results = self.awadb_client.Search(embedding, k)

        results: List[Tuple[Document, float]] = []

        if show_results.__len__() == 0:
            return results

        dists: List[float] = []
        not_include_fields: Set[str] = {"text_embedding", "_id", "score"}
        retrieval_docs = self.similarity_search_by_vector(
            embedding,
            k,
            scores=dists,
            not_include_fields_in_metadata=not_include_fields,
        )

        doc_no = 0
        for doc in retrieval_docs:
            doc_tuple = (doc, dists[doc_no])
            results.append(doc_tuple)
            doc_no = doc_no + 1

        return results

    def similarity_search_by_vector(
        self,
        embedding: Optional[List[float]] = None,
        k: int = DEFAULT_TOPN,
        scores: Optional[list] = None,
        not_include_fields_in_metadata: Optional[Set[str]] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Return docs most similar to embedding vector.

        Args:
            embedding: Embedding to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            scores: Scores for retrieved docs.
            not_incude_fields_in_metadata: Not include meta fields of each document.

        Returns:
            List of Documents which are the most similar to the query vector.
        """

        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        results: List[Document] = []

        if embedding is None:
            return results

        show_results = self.awadb_client.Search(
            embedding, k, not_include_fields=not_include_fields_in_metadata
        )

        if show_results.__len__() == 0:
            return results

        for item_detail in show_results[0]["ResultItems"]:
            content = ""
            meta_data = {}
            for item_key in item_detail:
                if item_key == "embedding_text":
                    content = item_detail[item_key]
                    continue
                elif item_key == "score":
                    if scores is not None:
                        scores.append(item_detail[item_key])
                        continue
                elif not_include_fields_in_metadata is not None:
                    if item_key in not_include_fields_in_metadata:
                        continue
                meta_data[item_key] = item_detail[item_key]
            results.append(Document(page_content=content, metadata=meta_data))
        return results

    def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        **kwargs: Any,
    ) -> List[Document]:
        """Return docs selected using the maximal marginal relevance.

        Maximal marginal relevance optimizes for similarity to query AND diversity
        among selected documents.

        Args:
            query: Text to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            fetch_k: Number of Documents to fetch to pass to MMR algorithm.
            lambda_mult: Number between 0 and 1 that determines the degree
                        of diversity among the results with 0 corresponding
                        to maximum diversity and 1 to minimum diversity.
                        Defaults to 0.5.
        Returns:
            List of Documents selected by maximal marginal relevance.
        """
        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        embedding = None
        if self.using_table_name in self.table2embeddings:
            embedding = self.table2embeddings[self.using_table_name].embed_query(query)
        else:
            from awadb import llm_embedding

            llm = llm_embedding.LLMEmbedding()
            embedding = llm.Embedding(query)

        results = self.max_marginal_relevance_search_by_vector(
            embedding, k, fetch_k, lambda_mult=lambda_mult
        )
        return results

    def max_marginal_relevance_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        **kwargs: Any,
    ) -> List[Document]:
        """Return docs selected using the maximal marginal relevance.

        Maximal marginal relevance optimizes for similarity to query AND diversity
        among selected documents.

        Args:
            embedding: Embedding to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            fetch_k: Number of Documents to fetch to pass to MMR algorithm.
            lambda_mult: Number between 0 and 1 that determines the degree
                        of diversity among the results with 0 corresponding
                        to maximum diversity and 1 to minimum diversity.
                        Defaults to 0.5.
        Returns:
            List of Documents selected by maximal marginal relevance.
        """

        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        results: List[Document] = []

        if embedding is None:
            return results

        not_include_fields: set = {"_id", "score"}
        retrieved_docs = self.similarity_search_by_vector(
            embedding, fetch_k, not_include_fields_in_metadata=not_include_fields
        )

        top_embeddings = []

        for doc in retrieved_docs:
            top_embeddings.append(doc.metadata["text_embedding"])

        selected_docs = maximal_marginal_relevance(
            np.array(embedding, dtype=np.float32), embedding_list=top_embeddings
        )

        for s_id in selected_docs:
            if "text_embedding" in retrieved_docs[s_id].metadata:
                del retrieved_docs[s_id].metadata["text_embedding"]
                results.append(retrieved_docs[s_id])
        return results

    def get(
        self,
        ids: List[str],
        not_include_fields: Optional[Set[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Document]:
        """Return docs according ids.

        Args:
            ids: The ids of the embedding vectors.
        Returns:
            Documents which have the ids.
        """

        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        docs_detail = self.awadb_client.Get(ids, not_include_fields=not_include_fields)

        results: Dict[str, Document] = {}
        for doc_detail in docs_detail:
            content = ""
            meta_info = {}
            for field in doc_detail:
                if field == "embeddint_text":
                    content = doc_detail[field]
                    continue
                elif field == "text_embedding" or field == "_id":
                    continue

                meta_info[field] = doc_detail[field]

            doc = Document(page_content=content, metadata=meta_info)
            results[doc_detail["_id"]] = doc
        return results

    def delete(
        self,
        ids: List[str],
    ) -> bool:
        """Delete the documents which have the specified ids.

        Args:
            ids: The ids of the embedding vectors.
        Returns:
            True or False of the delete operations.
        """
        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        return self.awadb_client.Delete(ids)

    def update(
        self,
        ids: List[str],
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Update the documents which have the specified ids.

        Args:
            ids: The id list of the updating embedding vector.
            texts: The texts of the updating documents.
            metadatas: The metadatas of the updating documents.
        Returns:
            the ids of the updated documents.
        """

        if self.awadb_client is None:
            raise ValueError("AwaDB client is None!!!")

        return self.awadb_client.UpdateTexts(
            ids=ids, text_field_name="embedding_text", texts=texts, metadatas=metadatas
        )

    def create_table(
        self,
        table_name: str,
        **kwargs: Any,
    ) -> bool:
        """Create a new table."""

        if self.awadb_client is None:
            return False

        ret = self.awadb_client.Create(table_name)

        if ret:
            self.using_table_name = table_name
        return ret

    def use(
        self,
        table_name: str,
        **kwargs: Any,
    ) -> bool:
        """Use the specified table. Don't know the tables, please invoke list_tables."""

        if self.awadb_client is None:
            return False

        ret = self.awadb_client.Use(table_name)
        if ret:
            self.using_table_name = table_name

        return ret

    def list_tables(
        self,
        **kwargs: Any,
    ) -> List[str]:
        """List all the tables created by the client."""

        if self.awadb_client is None:
            return []

        return self.awadb_client.ListAllTables()

    def get_current_table(
        self,
        **kwargs: Any,
    ) -> str:
        """Get the current table."""

        return self.using_table_name

    @classmethod
    def from_texts(
        cls: Type[AwaDB],
        texts: List[str],
        embedding: Optional[Embeddings] = None,
        metadatas: Optional[List[dict]] = None,
        table_name: str = _DEFAULT_TABLE_NAME,
        log_and_data_dir: Optional[str] = None,
        client: Optional[awadb.Client] = None,
        **kwargs: Any,
    ) -> AwaDB:
        """Create an AwaDB vectorstore from a raw documents.

        Args:
            texts (List[str]): List of texts to add to the table.
            embedding (Optional[Embeddings]): Embedding function. Defaults to None.
            metadatas (Optional[List[dict]]): List of metadatas. Defaults to None.
            table_name (str): Name of the table to create.
            log_and_data_dir (Optional[str]): Directory of logging and persistence.
            client (Optional[awadb.Client]): AwaDB client

        Returns:
            AwaDB: AwaDB vectorstore.
        """
        awadb_client = cls(
            table_name=table_name,
            embedding=embedding,
            log_and_data_dir=log_and_data_dir,
            client=client,
        )
        awadb_client.add_texts(texts=texts, metadatas=metadatas)
        return awadb_client

    @classmethod
    def from_documents(
        cls: Type[AwaDB],
        documents: List[Document],
        embedding: Optional[Embeddings] = None,
        table_name: str = _DEFAULT_TABLE_NAME,
        log_and_data_dir: Optional[str] = None,
        client: Optional[awadb.Client] = None,
        **kwargs: Any,
    ) -> AwaDB:
        """Create an AwaDB vectorstore from a list of documents.

        If a log_and_data_dir specified, the table will be persisted there.

        Args:
            documents (List[Document]): List of documents to add to the vectorstore.
            embedding (Optional[Embeddings]): Embedding function. Defaults to None.
            table_name (str): Name of the table to create.
            log_and_data_dir (Optional[str]): Directory to persist the table.
            client (Optional[awadb.Client]): AwaDB client.
            Any: Any possible parameters in the future

        Returns:
            AwaDB: AwaDB vectorstore.
        """
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        return cls.from_texts(
            texts=texts,
            embedding=embedding,
            metadatas=metadatas,
            table_name=table_name,
            log_and_data_dir=log_and_data_dir,
            client=client,
        )
