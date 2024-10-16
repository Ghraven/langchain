"""Test of Apache Cassandra graph vector g_store class `CassandraGraphVectorStore`"""

import json
import math
import os
from typing import Any, Iterable, List, Optional, Tuple, Union

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from langchain_community.graph_vectorstores import CassandraGraphVectorStore
from langchain_community.graph_vectorstores.base import Node
from langchain_community.graph_vectorstores.links import (
    METADATA_LINKS_KEY,
    Link,
    add_links,
)

TEST_KEYSPACE = "graph_test_keyspace"


class ParserEmbeddings(Embeddings):
    """Parse input texts: if they are json for a List[float], fine.
    Otherwise, return all zeros and call it a day.
    """

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(txt) for txt in texts]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        try:
            vals = json.loads(text)
        except json.JSONDecodeError:
            return [0.0] * self.dimension
        else:
            assert len(vals) == self.dimension
            return vals

    async def aembed_query(self, text: str) -> list[float]:
        return self.embed_query(text)


def _embedding_d2() -> Embeddings:
    return ParserEmbeddings(dimension=2)


class FakeEmbeddings(Embeddings):
    """Fake embeddings functionality for testing."""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Return simple embeddings.
        Embeddings encode each text as its index."""
        return [[float(1.0)] * 9 + [float(i)] for i in range(len(texts))]

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """Return constant query embeddings.
        Embeddings are identical to embed_documents(texts)[0].
        Distance to each text will be that text's index,
        as it was passed to embed_documents."""
        return [float(1.0)] * 9 + [float(0.0)]

    async def aembed_query(self, text: str) -> List[float]:
        return self.embed_query(text)


class AngularTwoDimensionalEmbeddings(Embeddings):
    """
    From angles (as strings in units of pi) to unit embedding vectors on a circle.
    """

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Make a list of texts into a list of embedding vectors.
        """
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        """
        Convert input text to a 'vector' (list of floats).
        If the text is a number, use it as the angle for the
        unit vector in units of pi.
        Any other input text becomes the singular result [0, 0] !
        """
        try:
            angle = float(text)
            return [math.cos(angle * math.pi), math.sin(angle * math.pi)]
        except ValueError:
            # Assume: just test string, no attention is paid to values.
            return [0.0, 0.0]


def _result_ids(docs: Iterable[Document]) -> List[Optional[str]]:
    return [doc.id for doc in docs]

def _graph_vector_store_docs() -> list[Document]:
    """
    This is a set of Documents to pre-populate a graph vector g_store,
    with entries placed in a certain way.

    Space of the entries (under Euclidean similarity):

                      A0    (*)
        ....        AL   AR       <....
        :              |              :
        :              |  ^           :
        v              |  .           v
                       |   :
       TR              |   :          BL
    T0   --------------x--------------   B0
       TL              |   :          BR
                       |   :
                       |  .
                       | .
                       |
                    FL   FR
                      F0

    the query point is meant to be at (*).
    the A are bidirectionally with B
    the A are outgoing to T
    the A are incoming from F
    The links are like: L with L, 0 with 0 and R with R.
    """

    docs_a = [
        Document(id="AL", page_content="[-1, 9]", metadata={"label": "AL"}),
        Document(id="A0", page_content="[0, 10]", metadata={"label": "A0"}),
        Document(id="AR", page_content="[1, 9]", metadata={"label": "AR"}),
    ]
    docs_b = [
        Document(id="BL", page_content="[9, 1]", metadata={"label": "BL"}),
        Document(id="B0", page_content="[10, 0]", metadata={"label": "B0"}),
        Document(id="BL", page_content="[9, -1]", metadata={"label": "BR"}),
    ]
    docs_f = [
        Document(id="FL", page_content="[1, -9]", metadata={"label": "FL"}),
        Document(id="F0", page_content="[0, -10]", metadata={"label": "F0"}),
        Document(id="FR", page_content="[-1, -9]", metadata={"label": "FR"}),
    ]
    docs_t = [
        Document(id="TL", page_content="[-9, -1]", metadata={"label": "TL"}),
        Document(id="T0", page_content="[-10, 0]", metadata={"label": "T0"}),
        Document(id="TR", page_content="[-9, 1]", metadata={"label": "TR"}),
    ]
    for doc_a, suffix in zip(docs_a, ["l", "0", "r"]):
        add_links(doc_a, Link.bidir(kind="ab_example", tag=f"tag_{suffix}"))
        add_links(doc_a, Link.outgoing(kind="at_example", tag=f"tag_{suffix}"))
        add_links(doc_a, Link.incoming(kind="af_example", tag=f"tag_{suffix}"))
    for doc_b, suffix in zip(docs_b, ["l", "0", "r"]):
        add_links(doc_b, Link.bidir(kind="ab_example", tag=f"tag_{suffix}"))
    for doc_t, suffix in zip(docs_t, ["l", "0", "r"]):
        add_links(doc_t, Link.incoming(kind="at_example", tag=f"tag_{suffix}"))
    for doc_f, suffix in zip(docs_f, ["l", "0", "r"]):
        add_links(doc_f, Link.outgoing(kind="af_example", tag=f"tag_{suffix}"))
    return docs_a + docs_b + docs_f + docs_t


def _get_cassandra_session(table_name: str, drop: bool = True) -> Any:
    from cassandra.cluster import Cluster

    # get db connection
    if "CASSANDRA_CONTACT_POINTS" in os.environ:
        contact_points = [
            cp.strip()
            for cp in os.environ["CASSANDRA_CONTACT_POINTS"].split(",")
            if cp.strip()
        ]
    else:
        contact_points = None
    cluster = Cluster(contact_points)
    session = cluster.connect()
    # ensure keyspace exists
    session.execute(
        (
            f"CREATE KEYSPACE IF NOT EXISTS {TEST_KEYSPACE} "
            f"WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}"
        )
    )
    # drop table if required
    if drop:
        session.execute(f"DROP TABLE IF EXISTS {TEST_KEYSPACE}.{table_name}")

    return session


def _graphvectorstore_from_texts(
    texts: List[str],
    embedding: Embeddings,
    metadatas: Optional[List[dict]] = None,
    ids: Optional[List[str]] = None,
    drop: bool = True,
    metadata_indexing: Union[Tuple[str, Iterable[str]], str] = "all",
    table_name: str = "graph_test_table",
) -> CassandraGraphVectorStore:
    session = _get_cassandra_session(table_name=table_name, drop=drop)
    return CassandraGraphVectorStore.from_texts(
        texts=texts,
        embedding=embedding,
        metadatas=metadatas,
        ids=ids,
        session=session,
        keyspace=TEST_KEYSPACE,
        table_name=table_name,
        metadata_indexing=metadata_indexing,
    )

async def _graphvectorstore_from_texts_async(
    texts: List[str],
    embedding: Embeddings,
    metadatas: Optional[List[dict]] = None,
    ids: Optional[List[str]] = None,
    drop: bool = True,
    metadata_indexing: Union[Tuple[str, Iterable[str]], str] = "all",
    table_name: str = "graph_test_table",
) -> CassandraGraphVectorStore:
    session = _get_cassandra_session(table_name=table_name, drop=drop)
    return await CassandraGraphVectorStore.afrom_texts(
        texts=texts,
        embedding=embedding,
        metadatas=metadatas,
        ids=ids,
        session=session,
        keyspace=TEST_KEYSPACE,
        table_name=table_name,
        metadata_indexing=metadata_indexing,
    )


def _graphvectorstore_from_documents(
    docs: List[Document],
    embedding: Embeddings,
    ids: Optional[List[str]] = None,
    drop: bool = True,
    metadata_indexing: Union[Tuple[str, Iterable[str]], str] = "all",
    table_name: str = "graph_test_table",
) -> CassandraGraphVectorStore:
    session = _get_cassandra_session(table_name=table_name, drop=drop)
    return CassandraGraphVectorStore.from_documents(
        documents=docs,
        ids=ids,
        embedding=embedding,
        session=session,
        keyspace=TEST_KEYSPACE,
        table_name=table_name,
        metadata_indexing=metadata_indexing,
    )

async def _graphvectorstore_from_documents_async(
    docs: List[Document],
    embedding: Embeddings,
    ids: Optional[List[str]] = None,
    drop: bool = True,
    metadata_indexing: Union[Tuple[str, Iterable[str]], str] = "all",
    table_name: str = "graph_test_table",
) -> CassandraGraphVectorStore:
    session = _get_cassandra_session(table_name=table_name, drop=drop)
    return await CassandraGraphVectorStore.afrom_documents(
        documents=docs,
        ids=ids,
        embedding=embedding,
        session=session,
        keyspace=TEST_KEYSPACE,
        table_name=table_name,
        metadata_indexing=metadata_indexing,
    )


def _graph_vector_store_d2(
    table_name: str = "graph_test_table",
) -> CassandraGraphVectorStore:
    session = _get_cassandra_session(table_name=table_name)
    return CassandraGraphVectorStore(
        embedding=_embedding_d2(),
        session=session,
        keyspace=TEST_KEYSPACE,
        table_name=table_name,
    )


def _populated_graph_vector_store_d2() -> CassandraGraphVectorStore:
    g_store = _graph_vector_store_d2()
    g_store.add_documents(_graph_vector_store_docs())
    return g_store


def test_mmr_traversal() -> None:
    """
    Test end to end construction and MMR search.
    The embedding function used here ensures `texts` become
    the following vectors on a circle (numbered v0 through v3):

           ______ v2
          /      \
         /        |  v1
    v3  |     .    | query
         |        /  v0
          |______/                 (N.B. very crude drawing)

    With fetch_k==2 and k==2, when query is at (1, ),
    one expects that v2 and v0 are returned (in some order)
    because v1 is "too close" to v0 (and v0 is closer than v1)).

    Both v2 and v3 are reachable via edges from v0, so once it is
    selected, those are both considered.
    """
    g_store = _graphvectorstore_from_documents(
        docs=[],
        embedding=AngularTwoDimensionalEmbeddings(),
    )

    v0 = Node(
        id="v0",
        text="-0.124",
        links=[
            Link.outgoing(kind="explicit", tag="link"),
        ],
    )
    v1 = Node(
        id="v1",
        text="+0.127",
    )
    v2 = Node(
        id="v2",
        text="+0.25",
        links=[
            Link.incoming(kind="explicit", tag="link"),
        ],
    )
    v3 = Node(
        id="v3",
        text="+1.0",
        links=[
            Link.incoming(kind="explicit", tag="link"),
        ],
    )
    g_store.add_nodes([v0, v1, v2, v3])

    results = g_store.mmr_traversal_search("0.0", k=2, fetch_k=2)
    assert _result_ids(results) == ["v0", "v2"]

    # With max depth 0, no edges are traversed, so this doesn't reach v2 or v3.
    # So it ends up picking "v1" even though it's similar to "v0".
    results = g_store.mmr_traversal_search("0.0", k=2, fetch_k=2, depth=0)
    assert _result_ids(results) == ["v0", "v1"]

    # With max depth 0 but higher `fetch_k`, we encounter v2
    results = g_store.mmr_traversal_search("0.0", k=2, fetch_k=3, depth=0)
    assert _result_ids(results) == ["v0", "v2"]

    # v0 score is .46, v2 score is 0.16 so it won't be chosen.
    results = g_store.mmr_traversal_search("0.0", k=2, score_threshold=0.2)
    assert _result_ids(results) == ["v0"]

    # with k=4 we should get all of the documents.
    results = g_store.mmr_traversal_search("0.0", k=4)
    assert _result_ids(results) == ["v0", "v2", "v1", "v3"]


def test_write_retrieve_keywords() -> None:
    greetings = Node(
        id="greetings",
        text="Typical Greetings",
        links=[
            Link.incoming(kind="parent", tag="parent"),
        ],
    )

    node1 = Node(
        id="doc1",
        text="Hello World",
        links=[
            Link.outgoing(kind="parent", tag="parent"),
            Link.bidir(kind="kw", tag="greeting"),
            Link.bidir(kind="kw", tag="world"),
        ],
    )

    node2 = Node(
        id="doc2",
        text="Hello Earth",
        links=[
            Link.outgoing(kind="parent", tag="parent"),
            Link.bidir(kind="kw", tag="greeting"),
            Link.bidir(kind="kw", tag="earth"),
        ],
    )

    g_store = _graphvectorstore_from_documents(
        docs=[],
        embedding=FakeEmbeddings(),
    )

    g_store.add_nodes(nodes=[greetings, node1, node2])

    # Doc2 is more similar, but World and Earth are similar enough that doc1 also
    # shows up.
    results: Iterable[Document] = g_store.similarity_search("Earth", k=2)
    assert _result_ids(results) == ["doc2", "doc1"]

    results = g_store.similarity_search("Earth", k=1)
    assert _result_ids(results) == ["doc2"]

    results = g_store.traversal_search("Earth", k=2, depth=0)
    assert _result_ids(results) == ["doc2", "doc1"]

    results = g_store.traversal_search("Earth", k=2, depth=1)
    assert _result_ids(results) == ["doc2", "doc1", "greetings"]

    # K=1 only pulls in doc2 (Hello Earth)
    results = g_store.traversal_search("Earth", k=1, depth=0)
    assert _result_ids(results) == ["doc2"]

    # K=1 only pulls in doc2 (Hello Earth). Depth=1 traverses to parent and via
    # keyword edge.
    results = g_store.traversal_search("Earth", k=1, depth=1)
    assert set(_result_ids(results)) == {"doc2", "doc1", "greetings"}


def test_metadata() -> None:
    g_store = _graphvectorstore_from_documents(
        docs=[],
        embedding=FakeEmbeddings(),
    )

    doc_a = Node(
        id="a",
        text="A",
        metadata={"other": "some other field"},
        links=[
            Link.incoming(kind="hyperlink", tag="http://a"),
            Link.bidir(kind="other", tag="foo"),
        ],
    )

    g_store.add_nodes([doc_a])
    results = g_store.similarity_search("A")
    assert len(results) == 1
    assert results[0].id == "a"
    metadata = results[0].metadata
    assert metadata["other"] == "some other field"
    assert set(metadata[METADATA_LINKS_KEY]) == {
        Link.incoming(kind="hyperlink", tag="http://a"),
        Link.bidir(kind="other", tag="foo"),
    }




def test_gvs_similarity_search_sync() -> None:
    """Simple (non-graph) similarity search on a graph vector g_store."""
    g_store = _populated_graph_vector_store_d2()
    ss_response = g_store.similarity_search(query="[2, 10]", k=2)
    ss_labels = [doc.metadata["label"] for doc in ss_response]
    assert ss_labels == ["AR", "A0"]
    ss_by_v_response = g_store.similarity_search_by_vector(embedding=[2, 10], k=2)
    ss_by_v_labels = [doc.metadata["label"] for doc in ss_by_v_response]
    assert ss_by_v_labels == ["AR", "A0"]


async def test_gvs_similarity_search_async() -> None:
    """Simple (non-graph) similarity search on a graph vector g_store."""
    g_store = _populated_graph_vector_store_d2()
    ss_response = await g_store.asimilarity_search(query="[2, 10]", k=2)
    ss_labels = [doc.metadata["label"] for doc in ss_response]
    assert ss_labels == ["AR", "A0"]
    ss_by_v_response = await g_store.asimilarity_search_by_vector(
        embedding=[2, 10], k=2
    )
    ss_by_v_labels = [doc.metadata["label"] for doc in ss_by_v_response]
    assert ss_by_v_labels == ["AR", "A0"]


def test_gvs_traversal_search_sync() -> None:
    """Graph traversal search on a graph vector g_store."""
    g_store = _populated_graph_vector_store_d2()
    ts_response = g_store.traversal_search(query="[2, 10]", k=2, depth=2)
    # this is a set, as some of the internals of trav.search are set-driven
    # so ordering is not deterministic:
    ts_labels = {doc.metadata["label"] for doc in ts_response}
    assert ts_labels == {"AR", "A0", "BR", "B0", "TR", "T0"}


async def test_gvs_traversal_search_async() -> None:
    """Graph traversal search on a graph vector g_store."""
    g_store = _populated_graph_vector_store_d2()
    ts_labels = set()
    async for doc in g_store.atraversal_search(query="[2, 10]", k=2, depth=2):
        ts_labels.add(doc.metadata["label"])
    # this is a set, as some of the internals of trav.search are set-driven
    # so ordering is not deterministic:
    assert ts_labels == {"AR", "A0", "BR", "B0", "TR", "T0"}


def test_gvs_mmr_traversal_search_sync() -> None:
    """MMR Graph traversal search on a graph vector g_store."""
    g_store = _populated_graph_vector_store_d2()
    mt_response = g_store.mmr_traversal_search(
        query="[2, 10]",
        k=2,
        depth=2,
        fetch_k=1,
        adjacent_k=2,
        lambda_mult=0.1,
    )
    # TODO: can this rightfully be a list (or must it be a set)?
    mt_labels = {doc.metadata["label"] for doc in mt_response}
    assert mt_labels == {"AR", "BR"}


async def test_gvs_mmr_traversal_search_async() -> None:
    """MMR Graph traversal search on a graph vector g_store."""
    g_store = _populated_graph_vector_store_d2()
    mt_labels = set()
    async for doc in g_store.ammr_traversal_search(
        query="[2, 10]",
        k=2,
        depth=2,
        fetch_k=1,
        adjacent_k=2,
        lambda_mult=0.1,
    ):
        mt_labels.add(doc.metadata["label"])
    # TODO: can this rightfully be a list (or must it be a set)?
    assert mt_labels == {"AR", "BR"}


def test_gvs_metadata_search_sync() -> None:
    """Metadata search on a graph vector g_store."""
    g_store = _populated_graph_vector_store_d2()
    mt_response = g_store.metadata_search(
        filter={"label": "T0"},
        n=2,
    )
    doc: Document = next(iter(mt_response))
    assert doc.page_content == "[-10, 0]"
    links = doc.metadata["links"]
    assert len(links) == 1
    link: Link = links.pop()
    assert isinstance(link, Link)
    assert link.direction == "in"
    assert link.kind == "at_example"
    assert link.tag == "tag_0"


async def test_gvs_metadata_search_async() -> None:
    """Metadata search on a graph vector g_store."""
    g_store = _populated_graph_vector_store_d2()
    mt_response = await g_store.ametadata_search(
        filter={"label": "T0"},
        n=2,
    )
    doc: Document = next(iter(mt_response))
    assert doc.page_content == "[-10, 0]"
    links: set[Link] = doc.metadata["links"]
    assert len(links) == 1
    link: Link = links.pop()
    assert isinstance(link, Link)
    assert link.direction == "in"
    assert link.kind == "at_example"
    assert link.tag == "tag_0"


def test_gvs_get_by_document_id_sync() -> None:
    """Get by document_id on a graph vector g_store."""
    g_store = _populated_graph_vector_store_d2()
    doc = g_store.get_by_document_id(document_id="FL")
    assert doc is not None
    assert doc.page_content == "[1, -9]"
    links = doc.metadata["links"]
    assert len(links) == 1
    link: Link = links.pop()
    assert isinstance(link, Link)
    assert link.direction == "out"
    assert link.kind == "af_example"
    assert link.tag == "tag_l"

    invalid_doc = g_store.get_by_document_id(document_id="invalid")
    assert invalid_doc is None


async def test_gvs_get_by_document_id_async() -> None:
    """Get by document_id on a graph vector g_store."""
    g_store = _populated_graph_vector_store_d2()
    doc = await g_store.aget_by_document_id(document_id="FL")
    assert doc is not None
    assert doc.page_content == "[1, -9]"
    links = doc.metadata["links"]
    assert len(links) == 1
    link: Link = links.pop()
    assert isinstance(link, Link)
    assert link.direction == "out"
    assert link.kind == "af_example"
    assert link.tag == "tag_l"

    invalid_doc = await g_store.aget_by_document_id(document_id="invalid")
    assert invalid_doc is None


def test_gvs_from_texts() -> None:
    g_store = _graphvectorstore_from_texts(
        texts=["[1, 2]"],
        embedding=_embedding_d2(),
        metadatas=[{"md": 1}],
        ids=["x_id"],
    )

    hits = g_store.similarity_search("[2, 1]", k=2)
    assert len(hits) == 1
    assert hits[0].page_content == "[1, 2]"
    assert hits[0].id == "x_id"
    # there may be more re:graph structure.
    assert hits[0].metadata["md"] == 1


def test_gvs_from_documents_containing_ids() -> None:
    the_document = Document(
        page_content="[1, 2]",
        metadata={"md": 1},
        id="x_id",
    )
    g_store = _graphvectorstore_from_documents(
        docs=[the_document],
        embedding=_embedding_d2(),
    )
    hits = g_store.similarity_search("[2, 1]", k=2)
    assert len(hits) == 1
    assert hits[0].page_content == "[1, 2]"
    assert hits[0].id == "x_id"
    # there may be more re:graph structure.
    assert hits[0].metadata["md"] == 1


def test_gvs_add_nodes_sync() -> None:
    g_store = _graph_vector_store_d2()
    links0 = [
        Link(kind="kA", direction="out", tag="tA"),
        Link(kind="kB", direction="bidir", tag="tB"),
    ]
    links1 = [
        Link(kind="kC", direction="in", tag="tC"),
    ]
    nodes = [
        Node(id="id0", text="[0, 2]", metadata={"m": 0}, links=links0),
        Node(text="[0, 1]", metadata={"m": 1}, links=links1),
    ]
    g_store.add_nodes(nodes)
    hits = g_store.similarity_search_by_vector([0, 3])
    assert len(hits) == 2
    assert hits[0].id == "id0"
    assert hits[0].page_content == "[0, 2]"
    md0 = hits[0].metadata
    assert md0["m"] == 0
    assert any(isinstance(v, set) for k, v in md0.items() if k != "m")
    assert hits[1].id != "id0"
    assert hits[1].page_content == "[0, 1]"
    md1 = hits[1].metadata
    assert md1["m"] == 1
    assert any(isinstance(v, set) for k, v in md1.items() if k != "m")


async def test_gvs_add_nodes_async() -> None:
    g_store = _graph_vector_store_d2()
    links0 = [
        Link(kind="kA", direction="out", tag="tA"),
        Link(kind="kB", direction="bidir", tag="tB"),
    ]
    links1 = [
        Link(kind="kC", direction="in", tag="tC"),
    ]
    nodes = [
        Node(id="id0", text="[0, 2]", metadata={"m": 0}, links=links0),
        Node(text="[0, 1]", metadata={"m": 1}, links=links1),
    ]
    async for _ in g_store.aadd_nodes(nodes):
        pass

    hits = await g_store.asimilarity_search_by_vector([0, 3])
    assert len(hits) == 2
    assert hits[0].id == "id0"
    assert hits[0].page_content == "[0, 2]"
    md0 = hits[0].metadata
    assert md0["m"] == 0
    assert any(isinstance(v, set) for k, v in md0.items() if k != "m")
    assert hits[1].id != "id0"
    assert hits[1].page_content == "[0, 1]"
    md1 = hits[1].metadata
    assert md1["m"] == 1
    assert any(isinstance(v, set) for k, v in md1.items() if k != "m")
