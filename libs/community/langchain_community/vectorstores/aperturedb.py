# System imports
from __future__ import annotations
from itertools import cycle, islice, repeat
import logging
from typing import Any, Callable, Iterable, List, Optional, Tuple, Type
import time

# Third-party imports
import aperturedb.Utils
import numpy as np

# Local imports
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

ENGINE = "HNSW"
METRIC = "L2"
DESCRIPTOR_SET = "langchain"


class ApertureDB(VectorStore):
    def __init__(self,
                 embeddings: Embeddings = None,
                 descriptor_set: str = DESCRIPTOR_SET,
                 dimensions: Optional[int] = None,
                 engine: str = None,
                 metric: str = None,
                 log_level: int = logging.INFO,
                 **kwargs):
        super().__init__(**kwargs)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        self.descriptor_set = descriptor_set

        self.embedding_function = embeddings
        self.dimensions = dimensions
        self.engine = engine
        self.metric = metric

        if embeddings is None:
            self.logger.warning(
                "No embedding function provided.")

        try:
            import aperturedb
        except ImportError:
            self.logger.exception(
                "ApertureDB is not installed. Please install it using 'pip install aperturedb'")
            raise

        self.connection = aperturedb.Utils.create_connector()
        self.utils = aperturedb.Utils.Utils(self.connection)
        try:
            self.utils.status()
            utils_connector = self.utils.connector
            assert utils_connector.last_query_ok(), utils_connector.get_last_response_str()
        except Exception:
            self.logger.exception(f"Failed to connect to ApertureDB")
            raise

        self._find_or_add_descriptor_set()

    def _select_relevance_score_fn(self) -> Callable[[float], float]:
        """Selects the relevance score function based on the metric.

        This method is defined in order to make the base class implementation of similarity_search_with_relevance_scores work.
        """
        if self.metric == "L2":
            return VectorStore._euclidean_relevance_score_fn
        elif self.metric == "IP":
            return VectorStore._max_inner_product_relevance_score_fn
        elif self.metric == "CS":
            return VectorStore._cosine_relevance_score_fn
        else:
            raise ValueError(f"Unknown metric: {self.metric}")

    def _find_or_add_descriptor_set(self):
        descriptor_set = self.descriptor_set
        """Checks if the descriptor set exists, if not, creates it"""
        find_ds_query = [{
            "FindDescriptorSet": {
                "with_name": descriptor_set,
                "engines": True,
                "metrics": True,
                "dimensions" : True,
            }
        }]
        r, b = self.connection.query(find_ds_query)
        assert self.connection.last_query_ok(), self.connection.get_last_response_str()
        n_entities = len(r[0]["FindDescriptorSet"]["entities"])
        assert n_entities <= 1, "Multiple descriptor sets with the same name"

        if n_entities == 1:
            e = r[0]["FindDescriptorSet"]["entities"][0]
            self.logger.info(f"Descriptor set {descriptor_set} already exists")

            engines = e["_engines"]
            assert len(engines) == 1, "Only one engine is supported"

            if self.engine is None:
                self.engine = engines[0]
            elif self.engine != engines[0]:
                self.logger.error(f"Engine mismatch: {self.engine} != {engines[0]}")
            
            metrics = e["_metrics"]
            assert len(metrics) == 1, "Only one metric is supported"
            if self.metric is None:
                self.metric = metrics[0]
            elif self.metric != metrics[0]:
                self.logger.error(f"Metric mismatch: {self.metric} != {metrics[0]}")

            dimensions = e["_dimensions"]
            if self.dimensions is None:
                self.dimensions = dimensions
            elif self.dimensions != dimensions:
                self.logger.error(f"Dimensions mismatch: {self.dimensions} != {dimensions}")

            if self.dimensions is None:
                self.dimensions = len(
                    self.embedding_function.embed_query("test"))
                
        else:
            self.logger.info(f"Descriptor set {descriptor_set} does not exist. Creating it")
            success = self.utils.add_descriptorset(
                descriptor_set, self.dimensions, engine=self.engine, metric=[self.metric])
            assert success, self.connection.get_last_response_str()

            # Create indexes
            self.utils.create_entity_index("_Descriptor", "_create_txn")
            self.utils.create_entity_index("_DescriptorSet", "_name")
            self.utils.create_entity_index("_Descriptor", "_uniqueid")


    def add_texts(self, texts: Iterable[str],
                  metadatas: Optional[List[dict]] = None,
                  ) -> List[str]:
        if metadatas is not None:
            assert len(texts) == len(
                metadatas), "Length of texts and metadatas should be the same"

        assert self.embedding_function is not None, "Embedding function is not set"
        embeddings = self.embedding_function.embed_documents(texts)
        if metadatas is None:
            metadatas = repeat({})
        refs = cycle(range(1, 100000, 2))
        data = zip(texts, embeddings, metadatas, refs)

        commands = []
        blobs = []
        for text, embedding, metadata, ref in data:
            commands.append({
                "AddDescriptor": {
                    "set": self.descriptor_set,
                    "_ref": ref
                }
            })
            npem = np.array(embedding, dtype=np.float32)
            blobs.append(npem.tobytes())

            commands.append({
                "AddBlob": {
                    "_ref": ref+1,
                    "properties": metadata,
                    "connect": {
                        "class": "has_descriptor",
                        "ref": ref
                    }
                }
            })
            blobs.append(text.encode())

            commands.append({
                "FindDescriptor": {
                    "set": self.descriptor_set,
                    "is_connected_to": {
                        "ref": ref+1
                    },
                    "results": {
                        "list": ["_uniqueid"]
                    }
                }
            })

        status, responses, blobs = aperturedb.ParallelQuery.execute_batch(
            q=commands, blobs=blobs, db=self.connection, commands_per_query=3, blobs_per_query=2)
        assert status == 0, responses
        unique_ids = [r["_uniqueid"]
                      for r in responses[2::3]["FindDescriptor"]["entities"]]
        return unique_ids

    def delete(self, ids: List[str]) -> Optional[bool]:
        refs = cycle(range(1, 100000))
        commands = []
        for id, ref in zip(ids, refs):
            commands.extend([{
                "FindDescriptor": {
                    "_ref": ref,
                    "set": self.descriptor_set,
                    "unique": True,
                    "constraints": {
                        "_uniqueid": ["==", id]
                    }
                }
            }, {
                "DeleteDescriptor": {
                    "_ref": ref,
                    "id": id
                }
            }, {
                "DeleteBlob": {
                    "is_connected_to": {
                        "ref": ref
                    }
                }
            }])

        status, responses, blobs = aperturedb.ParallelQuery.execute_batch(
            q=commands, blobs=blobs, db=self.connection, commands_per_query=3, blobs_per_query=0)
        assert status == 0, responses
        results = [r["DeleteDescriptor"]["results"]
                   ["count"] == 1 for r in responses[1::3]]
        return results

    def similarity_search(
        self, query: str, k: int = 4, *args: Any, **kwargs: Any
    ) -> List[Document]:
        assert self.embedding_function is not None, "Embedding function is not set"
        embedding = self.embedding_function.embed_query(query)
        # print(f"query: {query}, embedding: {embedding}")
        return self.similarity_search_by_vector(embedding, k, *args, **kwargs)

    def similarity_search_with_score(
        self, query: str, *args: Any, **kwargs: Any
    ) -> List[Tuple[Document, float]]:
        assert self.embedding_function is not None, "Embedding function is not set"
        embedding = self.embedding_function.embed_query(query)
        return self._similarity_search_with_score_by_vector(embedding, *args, **kwargs)

    def _similarity_search_with_score_by_vector(
        self, embedding: List[float], k: int = 4, vectors=False
    ) -> List[Tuple[Document, float]]:
        query = [{
            "FindDescriptor": {
                "set": self.descriptor_set,
                "k_neighbors": k,
                "_ref": 1,
                "results": {"list": ["_uniqueid"]},
                "blobs": vectors,
                "distances": True,
            }
        }, {
            "FindBlob": {
                "is_connected_to": {
                    "ref": 1
                },
                "results": {"all_properties": True},
                "blobs": True,
            }
        }]
        self.logger.debug(f"query: {query}")
        blobs_in = [np.array(embedding, dtype=np.float32).tobytes()]
        start_time = time.time()
        responses, blobs_out = self.connection.query(query, blobs_in)
        print(f"ApertureDB query completed in {time.time() - start_time:.1f}s")
        # print(f"responses: {responses}")
        assert self.connection.last_query_ok(), self.connection.get_last_response_str()
        results = []
        descriptors = responses[0]["FindDescriptor"]["entities"]
        blobs = responses[1]["FindBlob"]["entities"]
        for d, b in zip(descriptors, blobs):
            unique_id = d["_uniqueid"]
            distance = d["_distance"]
            blob_index = b["_blob_index"]
            text = blobs_out[blob_index].decode()
            # consider filtering internal properties out of metadata
            if vectors:
                vector_blob_index = d["_blob_index"]
                vector = np.frombuffer(
                    blobs_out[vector_blob_index], dtype=np.float32)
                results.append(
                    (Document(page_content=text, **d), distance, vector))
            else:
                results.append(
                    (Document(page_content=text, **d), distance))
        # print(f"results: {results}")
        return results

    def similarity_search_by_vector(
        self, embedding: List[float], k: int = 4, **kwargs: Any
    ) -> List[Document]:
        results = self._similarity_search_with_score_by_vector(embedding, k)
        return [document for document, _ in results]

    def max_marginal_relevance_search(
        self,
        query: str,
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        **kwargs: Any,
    ) -> List[Document]:
        assert self.embedding_function is not None, "Embedding function is not set"
        embedding = self.embedding_function.embed_query(query)
        # print(f"query-{query}, embedding: {embedding}")
        return self.max_marginal_relevance_search_by_vector(embedding, k, fetch_k, lambda_mult, **kwargs)

    def _vector_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        if self.metric == "L2":
            distance = np.linalg.norm(np.array(vector1) - np.array(vector2))
        elif self.metric == "IP":
            distance = np.dot(vector1, vector2)
        elif self.metric == "CS":
            distance = np.dot(vector1, vector2) / \
                (np.linalg.norm(vector1) * np.linalg.norm(vector2))
        else:
            raise ValueError(f"Unknown metric: {self.metric}")
        similarity = self._select_relevance_score_fn()(distance)
        return similarity

    def max_marginal_relevance_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        **kwargs: Any,
    ) -> List[Document]:
        results = self._similarity_search_with_score_by_vector(
            embedding, fetch_k, vectors=True)
        query_similarity = [self._vector_similarity(
            embedding, vector) for _, _, vector in results]
        document_similarity = {}
        for i, (_, _, vector) in enumerate(results):
            for j, (_, _, vector2) in enumerate(results[i+1:], i+1):
                similarity = self._vector_similarity(vector, vector2)
                document_similarity[(i, j)] = similarity
                document_similarity[(j, i)] = similarity

        selected = []
        unselected = list(range(len(results)))

        while len(selected) < k and unselected:
            if not selected:
                selected.append(0)
                unselected.remove(0)
            else:
                selected_unselected_similarity = np.array(
                    [[document_similarity[(i, j)] for j in unselected] for i in selected])
                worst_similarity = np.max(
                    selected_unselected_similarity, axis=0)
                relevance_scores = np.array([query_similarity[i] for i in unselected])
                scores = (1 - lambda_mult) * worst_similarity + \
                    lambda_mult * relevance_scores
                max_index = unselected[np.argmax(scores)]
                #print(f"max_index: {max_index}, selected: {selected}, unselected: {unselected}")
                selected.append(max_index)
                unselected.remove(max_index)
        results2 = [results[i][0] for i in selected]
        return results2

    @classmethod
    def from_texts(
        cls: Type[ApertureDB],
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        **kwargs: Any,
    ) -> ApertureDB:
        store = cls(embeddings=embedding, **kwargs)
        store.add_texts(texts, metadatas)
        return store
