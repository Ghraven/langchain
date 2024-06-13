import sys
from pathlib import Path

from langchain_community import document_loaders
from langchain_core.document_loaders.base import BaseLoader

DOCUMENT_LOADER_TEMPLATE = """\
---
sidebar_position: 0
sidebar_class_name: hidden
keywords: [compatibility]
custom_edit_url:
hide_table_of_contents: true
---

# Document loaders

## Features

The following table shows the feature support for all document loaders.

{table}

"""


def get_document_loader_table() -> str:
    """Get the table of document loaders."""

    doc_loaders_feat_table = {}
    for cm in document_loaders.__all__:
        doc_loaders_feat_table[cm] = {}
        cls = getattr(document_loaders, cm)
        if issubclass(cls, BaseLoader):
            for feat in ("aload", "alazy_load", ("lazy_load", "lazy_loading")):
                if isinstance(feat, tuple):
                    feat, name = feat
                else:
                    feat, name = feat, feat
                doc_loaders_feat_table[cm][name] = getattr(cls, feat) != getattr(
                    BaseLoader, feat
                )
            native_async = (
                doc_loaders_feat_table[cm]["aload"]
                or doc_loaders_feat_table[cm]["alazy_load"]
            )
            del doc_loaders_feat_table[cm]["aload"]
            del doc_loaders_feat_table[cm]["alazy_load"]
            doc_loaders_feat_table[cm]["native_async"] = native_async

    header = ["loader", "lazy_loading", "native_async"]
    title = ["Document Loader", "Document Lazy Loading", "Native Async Support"]
    rows = [title, [":-"] + [":-:"] * (len(title) - 1)]
    for llm, feats in sorted(doc_loaders_feat_table.items()):
        rows += [[llm] + ["✅" if feats.get(h) else "❌" for h in header[1:]]]
    return "\n".join(["|".join(row) for row in rows])


if __name__ == "__main__":
    output_dir = Path(sys.argv[1])
    output_integrations_dir = output_dir / "integrations"
    output_integrations_dir_doc_loaders = output_integrations_dir / "document_loaders"
    output_integrations_dir_doc_loaders.mkdir(parents=True, exist_ok=True)

    document_loader_page = DOCUMENT_LOADER_TEMPLATE.format(
        table=get_document_loader_table()
    )
    with open(output_integrations_dir / "document_loaders" / "index.mdx", "w") as f:
        f.write(document_loader_page)
