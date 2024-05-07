import multiprocessing
import os
import re
import sys
from pathlib import Path
from typing import Iterable, Tuple

import nbformat
from nbconvert.exporters import MarkdownExporter
from nbconvert.preprocessors import Preprocessor


class EscapePreprocessor(Preprocessor):
    def preprocess_cell(self, cell, resources, cell_index):
        if cell.cell_type == "markdown":
            # find all occurrences of ```{=mdx} blocks and remove wrapper
            if "```{=mdx}\n" in cell.source:
                cell.source = re.sub(
                    r"```{=mdx}\n(.*)\n```", "", cell.source, flags=re.DOTALL
                )
        return cell, resources


class ExtractAttachmentsPreprocessor(Preprocessor):
    """
    Extracts all of the outputs from the notebook file.  The extracted
    outputs are returned in the 'resources' dictionary.
    """

    def preprocess_cell(self, cell, resources, cell_index):
        """
        Apply a transformation on each cell,
        Parameters
        ----------
        cell : NotebookNode cell
            Notebook cell being processed
        resources : dictionary
            Additional resources used in the conversion process.  Allows
            preprocessors to pass variables into the Jinja engine.
        cell_index : int
            Index of the cell being processed (see base.py)
        """

        # Get files directory if it has been specified
        output_files_dir = resources.get("output_files_dir", None)

        # Make sure outputs key exists
        if not isinstance(resources["outputs"], dict):
            resources["outputs"] = {}

        # Loop through all of the attachments in the cell
        for name, attach in cell.get("attachments", {}).items():
            for mime, data in attach.items():
                if mime not in {
                    "image/png",
                    "image/jpeg",
                    "image/svg+xml",
                    "application/pdf",
                }:
                    continue

                # attachments are pre-rendered. Only replace markdown-formatted
                # images with the following logic
                attach_str = f"({name})"
                if attach_str in cell.source:
                    data = f"(data:{mime};base64,{data})"
                    cell.source = cell.source.replace(attach_str, data)

        return cell, resources


exporter = MarkdownExporter(
    preprocessors=[EscapePreprocessor, ExtractAttachmentsPreprocessor],
    template_name="mdoutput",
    extra_template_basedirs=["./scripts/notebook_convert_templates"],
)


def _process_path(tup: Tuple[Path, Path, Path]):
    notebook_path, intermediate_docs_dir, output_docs_dir = tup
    relative = notebook_path.relative_to(intermediate_docs_dir)
    output_path = output_docs_dir / relative.parent / (relative.stem + ".md")
    print(notebook_path)
    _convert_notebook(notebook_path, output_path)


def _convert_notebook(notebook_path: Path, output_path: Path):
    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)

    body, resources = exporter.from_notebook_node(nb)

    if not output_path.parent.exists():
        output_path.parent.mkdir(parents=True)

    with open(output_path, "w") as f:
        f.write(body)

    return output_path


if __name__ == "__main__":
    intermediate_docs_dir = Path(sys.argv[1])
    output_docs_dir = Path(sys.argv[2])

    source_paths_arg = os.environ.get("SOURCE_PATHS")
    source_paths: Iterable[Path]
    if source_paths_arg:
        source_path_strs = re.split(r"\s+", source_paths_arg)
        source_paths_stripped = [p.strip() for p in source_path_strs]
        source_paths = [intermediate_docs_dir / p for p in source_paths_stripped if p]
    else:
        source_paths = intermediate_docs_dir.glob("**/*.ipynb")

    with multiprocessing.Pool() as pool:
        pool.map(
            _process_path,
            (
                (notebook_path, intermediate_docs_dir, output_docs_dir)
                for notebook_path in source_paths
            ),
        )
