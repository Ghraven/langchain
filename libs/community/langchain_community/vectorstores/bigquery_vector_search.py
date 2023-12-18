"""Vector search in Google Cloud BigQuery."""
from __future__ import annotations

from typing import (
    Any,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
)

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from langchain_community.vectorstores.utils import DistanceStrategy
from google.cloud import bigquery

DEFAULT_DISTANCE_STRATEGY = DistanceStrategy.EUCLIDEAN_DISTANCE


class BigQueryVectorSearch(VectorStore):
    """Google Cloud BigQuery vector store.

    To use, you need the following packages installed:
        google-cloud-bigquery
    """

    def __init__(
        self,
        project_id: str,
        dataset_name: str,
        table_name: str,
        content_field: str,
        vector_field: str,
        embedding: Embeddings,
        index_field: str = None,
        distance_strategy: DistanceStrategy = DEFAULT_DISTANCE_STRATEGY,
        location: str = "US",
        metadata: str = None,
        credentials: Optional[Any] = None,
    ):
        """Constructor for BigQueryVectorSearch.

        Args:
            project_id (str): GCP project.
            dataset_name (str): BigQuery dataset to store documents and embeddings.
            table_name (str): BigQuery table name.
            content_field (str): Specifies the column to store the content.
            vector_field (str): Specifies the column to store the vector.
            embedding (Embeddings): Embedding model to use.
            index_field (str, Optional): Specifies the column to store
                the vector index.

            distance_strategy (DistanceStrategy, optional):
                Determines the strategy employed for calculating
                the distance between vectors in the embedding space.
                Defaults to EUCLIDEAN_DISTANCE.
                Available options are:
                - COSINE: Measures the similarity between two vectors of an inner
                    product space.
                - EUCLIDEAN_DISTANCE: Computes the Euclidean distance between
                    two vectors. This metric considers the geometric distance in
                    the vector space, and might be more suitable for embeddings
                    that rely on spatial relationships. This is the default behavior

            location (str, optional): BigQuery region. Defaults to
                `US`(multi-region).
            credentials (Credentials, optional): Custom Google Cloud credentials
                to use. Defaults to None.
        """
        try:
            self.bqclient = bigquery.Client(
                project=project_id, location=location, credentials=credentials
            )
        except ModuleNotFoundError:
            raise ImportError(
                "Please, install or upgrade the google-cloud-bigquery library: "
                "pip install google-cloud-bigquery"
            )

        self.project_id = project_id
        self.dataset_name = dataset_name
        self.table_name = table_name
        self.content_field = content_field
        self.vector_field = vector_field
        self.embedding = embedding
        self.index_field = index_field
        self.distance_strategy = distance_strategy
        self.location = location
        self.metadata = metadata

        self._full_table_id = (
            f"{self.project_id}." f"{self.dataset_name}." f"{self.table_name}"
        )

        self.vectors_table = self._validate_table(self.full_table_id)

    @property
    def embeddings(self) -> Embeddings:
        return self.embedding

    @property
    def full_table_id(self) -> str:
        return self._full_table_id

    def _validate_table(self, full_table_id: str) -> Any:
        """Validate the BigQuery dataset and table."""
        from google.api_core.exceptions import NotFound

        table_ref = bigquery.table.TableReference.from_string(
            full_table_id, default_project=self.project_id
        )

        try:
            table = self.bqclient.get_table(table_ref)
            self._validate_columns(table)
            print("The table is valid.")
            return table
        except NotFound:
            raise NotFound(f"The dataset `{full_table_id}` is not found.")

    def _validate_columns(self, table=bigquery.Table) -> Any:
        """Validate the schema contains one embedding and one content column."""
        schema = table.schema
        content_qualified = False
        vector_qualified = False

        for table_field_schema in schema:
            if (
                table_field_schema.field_type == "STRING"
                and table_field_schema.name == self.content_field
            ):
                content_qualified = True
            elif (
                table_field_schema.field_type.startswith("FLOAT")
                and table_field_schema.name == self.vector_field
            ):
                vector_qualified = True

        if not content_qualified or not vector_qualified:
            raise ValueError(
                "The table schema should contain vector_filed column "
                "in FLOAT type and content_field column in STRING type."
            )
      
    def add_texts(
      self,
      texts: Union[str, Iterable[str]],
      metadatas: Optional[List[dict]] = None,
      embeddings: Optional[List[List[float]]] = None,
      **kwargs: Any,
  ) -> List[str]:
      """Add more texts to the vectorstore.

      Args:
          texts (Iterable[str]): Iterable of strings/text to add to the vectorstore.
          metadatas (Optional[List[dict]], optional): Optional list of metadatas.
              Defaults to None.
          embeddings (Optional[List[List[float]]], optional): Optional pre-generated
              embeddings. Defaults to None.

      Returns:
          List[str]: empty list
      """
      if isinstance(texts, str):
          texts = [texts]
      embedded_texts = [self.embeddings.embed_query(text) for text in texts]
      list_of_embeddings_texts = list(zip(embedded_texts, texts))
      for pair in list_of_embeddings_texts:
          self._add_text_with_embedding_in_table(pair)
    

    def _add_text_with_embedding_in_table(self, pair: Tuple):
        """Inset the text with associated embedding into the table."""
        from google.cloud import bigquery

        sql = f"""
INSERT INTO `{self.full_table_id}` (
{self.content_field}, {self.vector_field}
) VALUES (
'{list(pair)[1]}', ARRAY{list(pair)[0]}
)
"""
        print(sql)
        job_config = bigquery.QueryJobConfig()

        query_job = self.bqclient.query(sql, job_config=job_config)
        return []
    
    def similarity_search(
        self, query: str, k: int = 4, filter: Optional[dict] = None, **kwargs: Any
    ) -> List[Document]:
        """Returns the most similar indexed documents to the query text.

        Uses cosine similarity.

        Args:
            query (str): The query text for which to find similar documents.
            k (int): The number of documents to return. Default is 4.
            filter (dict): A dictionary of metadata fields and values to filter by.

        Returns:
            List[Document]: A list of documents that are most similar to the query text.
        """
        docs_and_scores = self.similarity_search_with_score(
            query=query, k=k, filter=filter
        )
        return [doc for doc, _ in docs_and_scores]

    def similarity_search_with_score(
        self, query: str, k: int = 4, filter: Optional[dict] = None
    ) -> List[Tuple[Document, float]]:
        """Return docs most similar to query. Uses cosine similarity.

        Args:
            query: Text to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            filter: A dictionary of metadata fields and values to filter by.
                    Defaults to None.
        """
        document_tuples = self._search_with_score_and_embeddings(query, k, filter)
        return [(doc, distance) for doc, _, distance in document_tuples]


    def _create_vector_index(self) -> Any:
        """
        A vector index in BigQuery table enables efficient
        approximate vector search.
        """
        job_config = bigquery.QueryJobConfig()

        index_col = "my_index" if self.index_field is None else self.index_field

        if self.distance_strategy == DistanceStrategy.EUCLIDEAN_DISTANCE:
            distance_type = "EUCLIDEAN"
        elif self.distance_strategy == DistanceStrategy.COSINE:
            distance_type = "COSINE"
        # Default to EUCLIDEAN_DISTANCE
        else:
            distance_type = "EUCLIDEAN"
        sql = f"""
      CREATE OR REPLACE VECTOR INDEX `{self.project_id}.{self.dataset_name}.{index_col}`
      ON `{self.full_table_id}`({self.vector_field})
      OPTIONS(distance_type="{distance_type}", index_type="IVF")
      """
        print("_create_vector_index")
        print(sql)
        job = self.bqclient.query(sql, job_config=job_config)

    def _create_search_input_table(
        self,
        query: str,
    ) -> Any:
        """
        Create a new table with vector to search.
        """
        job_config = bigquery.QueryJobConfig()
        ## Create a new table with query to search in the exisiting dataset
        embedding = self.embeddings.embed_query(query)
        new_table = f"{self.project_id}.{self.dataset_name}.test_query"
        sql = f"""
    CREATE OR REPLACE TABLE `{new_table}` (
        {self.content_field} STRING,
        {self.vector_field} ARRAY<FLOAT64>
    ) AS
    SELECT '{query}', ARRAY{embedding}
    """
        print("_create_search_input_table")
        print(sql)
        job = self.bqclient.query(sql, job_config=job_config)

    def _bigquery_vector_search(self, k: int = 4) -> Any:
        """
        Conduct vector search in BigQuery.
        """
        job_config = bigquery.QueryJobConfig()
        new_table = f"{self.project_id}.{self.dataset_name}.test_query"
        vector_search_sql = f"""
    SELECT
        base.{self.content_field} AS {self.content_field},
        base.{self.vector_field} AS {self.vector_field},
        distance
    FROM VECTOR_SEARCH(
        TABLE `{self.full_table_id}`, '{self.vector_field}',
        TABLE `{new_table}`, top_k => {k})
    """
        print("_bigquery_vector_search")
        print(vector_search_sql)
        vector_search_job = self.bqclient.query(
            vector_search_sql, job_config=job_config
        )
        return vector_search_job

    def _search_with_score_and_embeddings(
        self, query: str, k: int = 4, filter: Optional[dict] = None
    ) -> List[Document]:
        self._create_vector_index()
        self._create_search_input_table(query=query)
        vector_search_job = self._bigquery_vector_search(k=k)

        # Build the documents
        document_tuples: List[Tuple[Document, List[float], float]] = []
        for row in vector_search_job:
            doc = Document(page_content=row[self.content_field])
            document_tuples.append((doc, row[self.vector_field], row["distance"]))
        return document_tuples
