import base64
import re
from dataclasses import asdict
from typing import List, Optional

from langchain_core.runnables.graph import (
    CurveStyle,
    Edge,
    MermaidDrawMethod,
    NodeColors,
)


def draw_mermaid(
    nodes: dict[str, str],
    edges: List[Edge],
    first_node_label: Optional[str] = None,
    last_node_label: Optional[str] = None,
    curve_style: CurveStyle = CurveStyle.LINEAR,
    node_colors: NodeColors = NodeColors(),
    wrap_label_n_words: int = 9,
) -> str:
    """Draws a Mermaid graph using the provided graph data

    Args:
        nodes (dict[str, str]): List of node ids
        edges (List[Edge]): List of edges, object with source,
        target and data.
        curve_style (CurveStyle, optional): Curve style for the edges.
        node_colors (NodeColors, optional): Node colors for different types.
        wrap_label_n_words (int, optional): Words to wrap the edge labels.

    Returns:
        str: Mermaid graph syntax
    """
    # Initialize Mermaid graph configuration
    mermaid_graph = (
        f"%%{{init: {{'flowchart': {{'curve': '{curve_style.value}', "
        f"'defaultRenderer': 'elk'}}}}}}%%\ngraph TD;\n"
    )

    # Node formatting templates
    default_class_label = "default"
    format_dict = {default_class_label: "{0}([{0}]):::otherclass"}
    if first_node_label is not None:
        format_dict[first_node_label] = "{0}[{0}]:::startclass"
    if last_node_label is not None:
        format_dict[last_node_label] = "{0}[{0}]:::endclass"

    # Filter out nodes that were created due to conditional edges
    pure_nodes = {id: value for id, value in nodes.items() if "edges" not in value}

    # Add __end__ node if it is in any of the edges.target
    if any("__end__" in edge.target for edge in edges):
        pure_nodes["__end__"] = "__end__"

    # Add nodes to the graph
    for node in pure_nodes.values():
        node_label = format_dict.get(node, format_dict[default_class_label]).format(
            _escape_node_label(node)
        )
        mermaid_graph += f"\t{node_label};\n"

    # Add edges to the graph
    for edge in edges:
        source, target = _adjust_mermaid_edge(edge, nodes, pure_nodes)
        if source == target:  # Ignore loops
            continue

        # Add BR every wrap_label_n_words words
        if edge.data is not None:
            edge_data = edge.data
            words = edge_data.split()  # Split the string into words
            # Group words into chunks of wrap_label_n_words size
            if len(words) > wrap_label_n_words:
                edge_data = "<br>".join(
                    [
                        " ".join(words[i : i + wrap_label_n_words])
                        for i in range(0, len(words), wrap_label_n_words)
                    ]
                )
            edge_label = f" -- {edge_data} --> "
        else:
            edge_label = " --> "
        mermaid_graph += (
            f"\t{_escape_node_label(source)}{edge_label}"
            f"{_escape_node_label(target)};\n"
        )

    # Add custom styles for nodes
    mermaid_graph += _generate_mermaid_graph_styles(node_colors)
    return mermaid_graph


def _escape_node_label(node_label: str) -> str:
    """Escapes the node label for Mermaid syntax."""
    return re.sub(r"[^a-zA-Z-_]", "_", node_label)


def _adjust_mermaid_edge(
    edge: Edge, nodes: dict[str, str], pure_nodes: dict[str, str]
) -> tuple[str, str]:
    """Adjusts Mermaid edge to map conditional nodes to pure nodes."""
    source_node_label = nodes.get(edge.source, edge.source)
    target_node_label = nodes.get(edge.target, edge.target)

    # TODO: Filter overlapping nodes with ::edges

    return source_node_label, target_node_label


def _generate_mermaid_graph_styles(node_colors: NodeColors) -> str:
    """Generates Mermaid graph styles for different node types."""
    styles = ""
    for class_name, color in asdict(node_colors).items():
        styles += f"\tclassDef {class_name}class fill:{color};\n"
    return styles


def draw_mermaid_png(
    mermaid_syntax: str,
    output_file_path: str = "graph.png",
    draw_method: MermaidDrawMethod = MermaidDrawMethod.API,
    background_color: str = "white",
    padding: int = 10,
) -> None:
    """Draws a Mermaid graph as PNG using provided syntax."""
    if draw_method == MermaidDrawMethod.PYPPETEER:
        import asyncio

        asyncio.run(
            _render_mermaid_using_pyppeteer(
                mermaid_syntax, output_file_path, background_color, padding
            )
        )
    elif draw_method == MermaidDrawMethod.API:
        _render_mermaid_using_api(mermaid_syntax, output_file_path, background_color)
    else:
        supported_methods = ", ".join([m.value for m in MermaidDrawMethod])
        raise ValueError(
            f"Invalid draw method: {draw_method}. "
            f"Supported draw methods are: {supported_methods}"
        )


async def _render_mermaid_using_pyppeteer(
    mermaid_syntax: str,
    output_file_path: str,
    background_color: str = "white",
    padding: int = 10,
) -> None:
    """Renders Mermaid graph using Pyppeteer."""
    try:
        from pyppeteer import launch  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "Install Pyppeteer to use the Pyppeteer method: `pip install pyppeteer`."
        ) from e

    browser = await launch()
    page = await browser.newPage()

    # Setup Mermaid JS
    await page.goto("about:blank")
    await page.addScriptTag({"url": "https://unpkg.com/mermaid/dist/mermaid.min.js"})
    await page.evaluate(
        """() => {
                mermaid.initialize({startOnLoad:true});
            }"""
    )

    # Render SVG
    svg_code = await page.evaluate(
        """(mermaidGraph) => {
                return mermaid.mermaidAPI.render('mermaid', mermaidGraph);
            }""",
        mermaid_syntax,
    )

    # Set the page background to white
    await page.evaluate(
        """(svg, background_color) => {
            document.body.innerHTML = svg;
            document.body.style.background = background_color;
        }""",
        svg_code["svg"],
        background_color,
    )

    # Take a screenshot
    dimensions = await page.evaluate(
        """() => {
            const svgElement = document.querySelector('svg');
            const rect = svgElement.getBoundingClientRect();
            return { width: rect.width, height: rect.height };
        }"""
    )
    await page.setViewport(
        {
            "width": int(dimensions["width"] + padding),
            "height": int(dimensions["height"] + padding),
        }
    )
    await page.screenshot({"path": output_file_path, "fullPage": False})
    await browser.close()


def _render_mermaid_using_api(
    mermaid_syntax: str, output_file_path: str, background_color: str = "white"
) -> None:
    """Renders Mermaid graph using the Mermaid.INK API."""
    try:
        import requests  # type: ignore[import]
    except ImportError as e:
        raise ImportError(
            "Install the `requests` module to use the Mermaid.INK API: "
            "`pip install requests`."
        ) from e

    # Use Mermaid API to render the image
    mermaid_syntax_encoded = base64.b64encode(mermaid_syntax.encode("utf8")).decode(
        "ascii"
    )

    # Check if the background color is a hexadecimal color code using regex
    hex_color_pattern = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")
    if not hex_color_pattern.match(background_color):
        background_color = f"!{background_color}"

    image_url = (
        f"https://mermaid.ink/img/{mermaid_syntax_encoded}?bgColor={background_color}"
    )
    response = requests.get(image_url)
    if response.status_code == 200:
        with open(output_file_path, "wb") as file:
            file.write(response.content)
    else:
        raise ValueError(
            f"Failed to render the graph using the Mermaid.INK API. "
            f"Status code: {response.status_code}."
        )
