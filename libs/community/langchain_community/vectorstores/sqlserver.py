from enum import Enum
from typing import Any, Iterable, List, Optional, Tuple, Type, Union

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VST, VectorStore
from sqlalchemy import Column, Uuid, asc, bindparam, create_engine, text
from sqlalchemy.dialects.mssql import JSON, NVARCHAR, VARBINARY, VARCHAR
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session

try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

import json
import logging
import uuid


class DistanceStrategy(str, Enum):
    """Enumerator of the distance strategies for calculating distances
    between vectors.
    """

    EUCLIDEAN = "euclidean"
    COSINE = "cosine"
    DOT = "dot"


Base = declarative_base()  # type: Any

_embedding_store: Any = None

DEFAULT_DISTANCE_STRATEGY = DistanceStrategy.COSINE
DEFAULT_EMBEDDING_LENGTH = 8000
VECTOR_DISTANCE_QUERY = """
VECTOR_DISTANCE(:distancestrategy, JSON_ARRAY_TO_VECTOR(:embedding), embeddings) 
AS distance"""
EMBEDDING = "embedding"
DISTANCE_STRATEGY = "distancestrategy"


class SQLServer_VectorStore(VectorStore):
    """SQL Server Vector Store.

    This class provides a vector store interface for adding texts and performing
        similarity searches on the texts in SQL Server.

    """

    def __init__(
        self,
        *,
        connection: Optional[Connection] = None,
        connection_string: str,
        distance_strategy: DistanceStrategy = DEFAULT_DISTANCE_STRATEGY,
        embedding_function: Embeddings,
        embedding_length: int = DEFAULT_EMBEDDING_LENGTH,
        table_name: str,
    ) -> None:
        """Initialize the SQL Server vector store.

        Args:
            connection: Optional SQLServer connection.
            connection_string: SQLServer connection string.
            distance_strategy: The distance strategy to use for comparing embeddings.
                Default value is COSINE. Available options are:
                - COSINE
                - DOT
                - EUCLIDEAN
            embedding_function: Any embedding function implementing
                `langchain.embeddings.base.Embeddings` interface.
            embedding_length: The length of the vectors to be stored in the table
                Defaults to 8000 if not specified.
            table_name: The name of the table to use for storing embeddings.

        """

        self.connection_string = connection_string
        self._distance_strategy = distance_strategy
        self.embedding_function = embedding_function
        self._embedding_length = embedding_length
        self.table_name = table_name
        self._bind: Union[Connection, Engine] = (
            connection if connection else self._create_engine()
        )
        self.EmbeddingStore = self._get_embedding_store(table_name)
        self._create_table_if_not_exists()

    def _create_engine(self) -> Engine:
        return create_engine(url=self.connection_string, echo=True)

    def _create_table_if_not_exists(self) -> None:
        logging.info(f"Creating table {self.table_name}.")
        with Session(self._bind) as session:
            Base.metadata.create_all(session.get_bind())

    def _get_embedding_store(self, name: str) -> Any:
        global _embedding_store
        if _embedding_store is not None:
            return _embedding_store

        class EmbeddingStore(Base):
            """This is the base model for SQL vector store."""

            __tablename__ = name
            id = Column(Uuid, primary_key=True, default=uuid.uuid4)
            custom_id = Column(VARCHAR, nullable=True)  # column for user defined ids.
            query_metadata = Column(JSON, nullable=True)
            query = Column(NVARCHAR, nullable=False)  # defaults to NVARCHAR(MAX)
            embeddings = Column(VARBINARY(self._embedding_length), nullable=False)

        _embedding_store = EmbeddingStore
        return _embedding_store

    @property
    def embeddings(self) -> Embeddings:
        return self.embedding_function

    @property
    def distance_strategy(self) -> str:
        # Value of distance strategy passed in should be one of the supported values.
        if isinstance(self._distance_strategy, DistanceStrategy):
            return self._distance_strategy.value

        # Match string value with appropriate enum value, if supported.
        distance_strategy_lower = str.lower(self._distance_strategy)

        if distance_strategy_lower == DistanceStrategy.EUCLIDEAN.value:
            return DistanceStrategy.EUCLIDEAN.value
        elif distance_strategy_lower == DistanceStrategy.COSINE.value:
            return DistanceStrategy.COSINE.value
        elif distance_strategy_lower == DistanceStrategy.DOT.value:
            return DistanceStrategy.DOT.value
        else:
            raise ValueError(f"{self._distance_strategy} is not supported.")

    @classmethod
    def from_texts(
        cls: Type[VST],
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> VST:
        """Return VectorStore initialized from texts and embeddings."""
        return super().from_texts(texts, embedding, metadatas, **kwargs)

    def similarity_search(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> List[Document]:
        """Return docs most similar to given query.

        Args:
            query: Text to look up the most similar embedding to.
            k: Number of Documents to return. Defaults to 4.
            **kwargs: Values for filtering on metadata during similarity search.

        Returns:
            List of Documents most similar to the query provided.
        """
        embedded_query = self.embedding_function.embed_query(query)
        return self.similarity_search_by_vector(embedded_query, k, **kwargs)

    def similarity_search_by_vector(
        self, embedding: List[float], k: int = 4, **kwargs: Any
    ) -> List[Document]:
        """Return docs most similar to the embedding vector.

        Args:
            embedding: Embedding to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            **kwargs: Values for filtering on metadata during similarity search.

        Returns:
            List of Documents most similar to the embedding provided.
        """
        similar_docs_with_scores = self.similarity_search_by_vector_with_score(
            embedding, k, **kwargs
        )
        return self._docs_from_result(similar_docs_with_scores)

    def similarity_search_with_score(
        self, query: str, k: int = 4, **kwargs: Any
    ) -> List[Tuple[Document, float]]:
        """Run similarity search with distance and
            return docs most similar to the embedding vector.

        Args:
            query: Text to look up the most similar embedding to.
            k: Number of Documents to return. Defaults to 4.
            **kwargs: Values for filtering on metadata during similarity search.

        Returns:
            List of tuple of Document and an accompanying score in order of
            similarity to the query provided.
            Note that, a smaller score implies greater similarity.
        """
        embedded_query = self.embedding_function.embed_query(query)
        return self.similarity_search_by_vector_with_score(embedded_query, k, **kwargs)

    def similarity_search_by_vector_with_score(
        self, embedding: List[float], k: int = 4, **kwargs: Any
    ) -> List[Tuple[Document, float]]:
        """Run similarity search with distance, given an embedding
            and return docs most similar to the embedding vector.

        Args:
            embedding: Embedding to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            **kwargs: Values for filtering on metadata during similarity search.

        Returns:
            List of tuple of Document and an accompanying score in order of
            similarity to the embedding provided.
            Note that, a smaller score implies greater similarity.
        """
        similar_docs = self._search_store(embedding, k, **kwargs)
        docs_and_scores = self._docs_and_scores_from_result(similar_docs)
        return docs_and_scores

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Compute the embeddings for the input texts and store embeddings
            in the vectorstore.

        Args:
            texts: Iterable of strings to add into the vectorstore.
            metadatas: List of metadatas (python dicts) associated with the input texts.
            ids: List of IDs for the input texts.
            **kwargs: vectorstore specific parameters.

        Returns:
            List of IDs generated from adding the texts into the vectorstore.
        """

        # Embed the texts passed in.
        embedded_texts = self.embedding_function.embed_documents(list(texts))

        # Insert the embedded texts in the vector store table.
        return self._insert_embeddings(texts, embedded_texts, metadatas, ids)

    def drop(self) -> None:
        """Drops every table created during initialization of vector store."""
        logging.info(f"Dropping vector store: {self.table_name}")
        try:
            with Session(bind=self._bind) as session:
                # Drop all the tables associated with the session bind.
                Base.metadata.drop_all(session.get_bind())
            logging.info(f"Vector store `{self.table_name}` dropped successfully.")
        except ProgrammingError as e:
            logging.error(f"Unable to drop vector store.\n {e.__cause__}.")

    def _search_store(
        self, embedding: List[float], k: int, filter: Optional[dict] = None
    ) -> List[Any]:
        try:
            with Session(self._bind) as session:
                results = (
                    session.query(
                        _embedding_store,
                        text(VECTOR_DISTANCE_QUERY).bindparams(
                            bindparam(
                                DISTANCE_STRATEGY,
                                self.distance_strategy,
                                literal_execute=True,
                            ),
                            bindparam(
                                EMBEDDING, json.dumps(embedding), literal_execute=True
                            ),
                        ),
                    )
                    .filter()
                    .order_by(asc(text("distance")))
                    .limit(k)
                    .all()
                )
        except ProgrammingError as e:
            logging.error(f"An error has occurred during the search.\n {e.__cause__}")
        return results

    def _create_filter_clause(self, filter: dict) -> None:
        """TODO: parse filter and create a sql clause."""

    def _docs_from_result(self, results: Any) -> List[Document]:
        """Formats the input into a result of type List[Document]."""
        docs = [result[0] for result in results]
        return docs

    def _docs_and_scores_from_result(
        self, results: Any
    ) -> List[Tuple[Document, float]]:
        """Formats the input into a result of type Tuple[Document, float]."""
        docs_and_scores = [
            (
                Document(
                    page_content=result[0].query, metadata=result[0].query_metadata
                ),
                result[1],
            )
            for result in results
        ]
        return docs_and_scores

    def _insert_embeddings(
        self,
        texts: Iterable[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Insert the embeddings and the texts in the vectorstore.

        Args:
            texts: Iterable of strings to add into the vectorstore.
            embeddings: List of list of embeddings.
            metadatas: List of metadatas (python dicts) associated with the input texts.
            ids: List of IDs for the input texts.
            **kwargs: vectorstore specific parameters.

        Returns:
            List of IDs generated from adding the texts into the vectorstore.
        """

        if metadatas is None:
            metadatas = [{} for _ in texts]

        try:
            if ids is None:
                ids = [metadata.pop("id", uuid.uuid4()) for metadata in metadatas]

            with Session(self._bind) as session:
                documents = []
                for idx, query in enumerate(texts):
                    # For a query, if there is no corresponding ID,
                    # we generate a uuid and add it to the list of IDs to be returned.
                    if idx < len(ids):
                        id = ids[idx]
                    else:
                        ids.append(str(uuid.uuid4()))
                        id = ids[-1]
                    embedding = embeddings[idx]
                    metadata = metadatas[idx] if idx < len(metadatas) else None

                    # Construct text, embedding, metadata as EmbeddingStore model
                    # to be inserted into the table.
                    sqlquery = text(
                        "select JSON_ARRAY_TO_VECTOR (:embeddingvalues)"
                    ).bindparams(
                        bindparam(
                            "embeddingvalues",
                            json.dumps(embedding),
                            # render the value of the parameter into SQL statement
                            # at statement execution time
                            literal_execute=True,
                        )
                    )
                    result = session.scalar(sqlquery)
                    embedding_store = self.EmbeddingStore(
                        custom_id=id,
                        query_metadata=metadata,
                        query=query,
                        embeddings=result,
                    )
                    documents.append(embedding_store)
                session.bulk_save_objects(documents)
                session.commit()
        except DBAPIError as e:
            logging.error(f"Add text failed:\n {e.__cause__}")
            raise
        except AttributeError:
            logging.error("Metadata must be a list of dictionaries.")
            raise
        return ids
