
from langchain.chains.query_constructor.ir import (
    Comparator,
    Comparison,
    Operation,
    Operator,
    StructuredQuery,
)
from langchain.retrievers.self_query.tencentvectordb import TencentVectorDBTranslator


def test_translate_with_operator():
    query = StructuredQuery(
        query="What are songs by Taylor Swift or Katy Perry under 3 minutes long in the dance pop genre",
        filter=Operation(
            operator=Operator.AND,
            arguments=[
                Operation(
                    operator=Operator.OR,
                    arguments=[
                        Comparison(comparator=Comparator.EQ, attribute="artist", value="Taylor Swift"),
                        Comparison(comparator=Comparator.EQ, attribute="artist", value="Katy Perry"),
                    ],
                ),
                Comparison(comparator=Comparator.LT, attribute="length", value=180),
            ],
        ),
    )
    translator = TencentVectorDBTranslator()
    query, kwargs = translator.visit_structured_query(query)
    expr = "(artist = \"Taylor Swift\" or artist = \"Katy Perry\") and length < 180"
    assert kwargs['expr'] == expr


def test_translate_with_in_comparison():
    # 写成Comparison的形式
    query = StructuredQuery(
        query="What are songs by Taylor Swift or Katy Perry under 3 minutes long in the dance pop genre",
        filter=Comparison(comparator=Comparator.IN, attribute="artist", value=["Taylor Swift", "Katy Perry"]),
    )
    translator = TencentVectorDBTranslator()
    query, kwargs = translator.visit_structured_query(query)
    expr = "artist in (\"Taylor Swift\", \"Katy Perry\")"
    assert kwargs['expr'] == expr


def test_translate_with_allowed_fields():
    query = StructuredQuery(
        query="What are songs by Taylor Swift or Katy Perry under 3 minutes long in the dance pop genre",
        filter=Comparison(comparator=Comparator.IN, attribute="artist", value=["Taylor Swift", "Katy Perry"]),
    )
    translator = TencentVectorDBTranslator(meta_keys=["artist"])
    query, kwargs = translator.visit_structured_query(query)
    expr = "artist in (\"Taylor Swift\", \"Katy Perry\")"
    assert kwargs['expr'] == expr


def test_translate_with_unsupported_field():
    query = StructuredQuery(
        query="What are songs by Taylor Swift or Katy Perry under 3 minutes long in the dance pop genre",
        filter=Comparison(comparator=Comparator.IN, attribute="artist", value=["Taylor Swift", "Katy Perry"]),
    )
    translator = TencentVectorDBTranslator(meta_keys=["title"])
    try:
        translator.visit_structured_query(query)
    except ValueError as e:
        assert str(e) == "Expr Filtering found Unsupported attribute: artist"
    else:
        assert False
