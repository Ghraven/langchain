from langchain.document_loaders.parsers.language.tree_sitter_segmenter import (
    TreeSitterSegmenter,
)

CHUNK_QUERY = """
    [
        (function_declaration) @function
        (type_declaration) @type
    ]
""".strip()


class GoSegmenter(TreeSitterSegmenter):
    """Code segmenter for Go."""

    def get_language(self):
        from tree_sitter_languages import get_language

        return get_language("go")

    def get_chunk_query(self) -> str:
        return CHUNK_QUERY

    def make_line_comment(self, text: str) -> str:
        return f"// {text}"
