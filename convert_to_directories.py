import argparse
import json
import re
from pathlib import Path
from typing import Literal

from utils import (
    OL,
    UL,
    get_unique_path,
    html_to_md,
    rjson,
    truncate_string,
    wjson,
    wtext,
)


def get_node_id_idxs(node_id: str, only_node_ids: bool = True) -> list[int]:
    idxs = []
    in_closure = None
    for char in node_id[1:]:
        if in_closure is not None:
            if char == ".":
                idxs.append(int(in_closure))
                in_closure = None
            else:
                in_closure += char
        else:
            if char == ".":
                in_closure = ""
            else:
                idxs.append(int(char))

    return [idx for i, idx in enumerate(idxs) if not only_node_ids or i % 2 != 0]


def get_node_from_id(node_id: str | None, root: dict | None) -> dict | None:
    if not root or not node_id:
        return

    current_node = root
    for idx in get_node_id_idxs(node_id):
        if not current_node or not current_node.get("breakdowns"):
            return
        if idx >= len(current_node["breakdowns"][0]["sub_nodes"]):
            return
        current_node = current_node["breakdowns"][0]["sub_nodes"][idx]

    return current_node


def sanitize_filename(name: str):
    # Replace spaces with underscores and remove other invalid characters
    return re.sub(r"[^\w\-\.]", "_", name.strip().replace(" ", "_"))


def get_node_path(node_id: str, root: dict) -> str | None:
    """Convert a node ID to its path in the tree structure."""
    # First, we need to build the complete path from root to the node
    path_parts = []

    # Start with the root node
    if not root or "title" not in root:
        return None

    # Parse the node ID to get the sequence of indices
    indices = get_node_id_idxs(node_id)
    if not indices:
        return None

    # Start with the root node
    current_node = root
    path_parts.append(sanitize_filename(current_node.get("title", "Root")))

    # Follow the path through the tree
    for idx in indices:
        if (
            not current_node
            or not current_node.get("breakdowns")
            or not current_node["breakdowns"][0].get("sub_nodes")
            or idx >= len(current_node["breakdowns"][0]["sub_nodes"])
        ):
            return None

        # Move to the next node in the path
        current_node = current_node["breakdowns"][0]["sub_nodes"][idx]
        if "title" in current_node:
            path_parts.append(sanitize_filename(current_node["title"]))

    return "/".join(path_parts) if path_parts else None


def get_node_title(node_id: str, root: dict) -> str | None:
    """Get the title of a node from its ID."""
    node = get_node_from_id(node_id, root)
    if node and "title" in node:
        return node["title"]
    return None


def convert_links_to_paths(links: list, root: dict) -> list:
    """Convert link IDs to paths in the tree structure."""
    converted_links = []
    for link in links:
        new_link = link.copy()
        if "id" in new_link:
            path = get_node_path(new_link["id"], root)
            title = get_node_title(new_link["id"], root)

            if path:
                dir_name = path.split("/")[-1]
                new_link["path"] = f"{path}/{dir_name}.md"
                if title:
                    new_link["title"] = title
                del new_link["id"]
            else:
                # Keep the ID if path couldn't be resolved
                new_link["path"] = f"Unknown path (ID: {new_link['id']})"
                new_link["title"] = "Unknown Node"
                del new_link["id"]
        converted_links.append(new_link)
    return converted_links


def get_breakdown_strat(node: dict) -> Literal["sub_nodes", "breakdowns"]:
    if not node.get("breakdowns"):
        return "sub_nodes"

    if any(node["breakdowns"][0].get(key) for key in ["paper", "explanation"]):
        return "breakdowns"

    return "breakdowns" if len(node["breakdowns"]) > 1 else "sub_nodes"


def create_directory_structure(
    node,
    root,
    parent_path=Path(),
    convert_html=True,
    preserve_order=True,
    breakdowns_identifier=".",
):
    dir_name = sanitize_filename(node["title"])
    dir_path = parent_path / (
        dir_name
        + (breakdowns_identifier if get_breakdown_strat(node) == "breakdowns" else "")
    )

    dir_path.mkdir(parents=True)

    sections: list[str] = []

    if node.get("mini_description"):
        sections.append(f"### Mini Description\n\n{node['mini_description']}")

    if node.get("description"):
        sections.append(f"### Description\n\n{node['description']}")

    if node.get("questions"):
        sections.append(
            f"### Questions\n\n{UL([q['question'] for q in node['questions']]).to_str(spacing=1)}"
        )

    if preserve_order and node.get("breakdowns"):
        if get_breakdown_strat(node) == "breakdowns":
            titles = [
                sanitize_filename(b.get("title"))
                if b.get("title")
                else f'Paper: "{b.get("paper", {}).get("title")}"'
                for b in node["breakdowns"]
            ]
        else:
            breakdown = node["breakdowns"][0]
            titles = [sanitize_filename(sub["title"]) for sub in breakdown["sub_nodes"]]

        if titles != sorted(titles):
            sections.append(f"### Order\n\n{OL(titles)}")

    links = node.get("links", [])
    if links:
        converted_links = convert_links_to_paths(links, root)

        link_list = UL()

        for link in converted_links:
            path = link.get("path", "")
            title = link.get("title", path)

            link_list.add(
                f"[{title}](/{path})",
                UL([f"Reason: {link['reason']}"]) if link.get("reason") else None,
            )

        sections.append(f"### Related Nodes\n\n{link_list}")

    wtext(
        html_to_md("\n\n".join(sections) + "\n", convert_html),
        dir_path / f"{dir_name}.md",
    )

    if node.get("papers"):
        wjson(node["papers"], dir_path / "papers.json", indent=2)

    if node.get("breakdowns"):
        for breakdown in node["breakdowns"]:
            if get_breakdown_strat(node) == "breakdowns":
                title = sanitize_filename(
                    breakdown.get("title")
                    or f"Untitled {truncate_string(breakdown.get('paper', {}).get('title', ''), end='_')}"
                )
                sub_parent_path = get_unique_path(dir_path / title, spacer="")
                sub_parent_path.mkdir()
                sub_sections = []

                if breakdown.get("paper"):
                    sub_sections.append(
                        f"### Paper\n\n```json\n{json.dumps(breakdown['paper'], indent=10).replace(' ' * 10, '\t')}\n```"
                    )

                if breakdown.get("explanation"):
                    sub_sections.append(
                        f"### Explanation\n\n{html_to_md(breakdown['explanation'], convert_html)}"
                    )

                titles = [
                    sanitize_filename(sub["title"])
                    + (
                        breakdowns_identifier
                        if get_breakdown_strat(sub) == "breakdowns"
                        else ""
                    )
                    for sub in breakdown["sub_nodes"]
                ]
                if titles != sorted(titles):
                    sub_sections.append(f"### Order\n\n{OL(titles)}")

                wtext(
                    "\n\n".join(sub_sections) + "\n",
                    sub_parent_path / f"{sub_parent_path.name}.md",
                )
            else:
                sub_parent_path = dir_path

            if "sub_nodes" in breakdown:
                for sub_node in breakdown["sub_nodes"]:
                    create_directory_structure(
                        sub_node, root, sub_parent_path, convert_html, preserve_order
                    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file", type=Path, help="The JSON file to convert.")
    parser.add_argument("--output-path", type=Path, required=True)
    parser.add_argument(
        "--no-markdown",
        "-nmd",
        action="store_false",
        help="Dont convert HTML to Markdown.",
    )

    args = vars(parser.parse_args())
    args["convert_html"] = args["no_markdown"]
    return args


def main(json_file: Path, output_path=Path(), convert_html=True, preserve_order=True):
    data = rjson(json_file)

    output_path.mkdir(parents=True, exist_ok=True)
    create_directory_structure(data, data, output_path, convert_html, preserve_order)
    print(
        f"Directory structure created successfully based on '{data.get('title', 'Root')}'"
    )


# if __name__ == "__main__":
#     main(**parse_args())


if __name__ == "__main__":
    main(
        json_file=Path("test_data/fli/map.json"),
        output_path=Path("test_output/fli"),
    )
