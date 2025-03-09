import argparse
import json
import re
from pathlib import Path

from utils import (
    Breakdown,
    Node,
    md_to_html,
    resolve_md_list,
    rjson,
    rtext,
    wjson,
)


def desanitize_filename(filename: str):
    return filename.replace("_", " ").strip()


def split_by_sections(content: str):
    sections: list[tuple[str, str]] = []
    re_sections = re.split(r"^###\s+(.*?)$", content, flags=re.MULTILINE)[1:]

    for i in range(0, len(re_sections), 2):
        sections.append(
            (
                re_sections[i].strip(),
                re_sections[i + 1].strip() if i + 1 < len(re_sections) else "",
            )
        )

    return sections


def get_sub_dir_names(dir: Path):
    return sorted(
        [d.name for d in dir.iterdir() if d.is_dir()],
        key=lambda s: s.lstrip("Untitled_"),
    )


def resolve_breakdown(file_path: Path, parent_path: Path):
    breakdown: Breakdown = {
        "title": None
        if file_path.stem.startswith("Untitled")
        else desanitize_filename(file_path.stem)
    }
    sub_dir_names = get_sub_dir_names(parent_path)
    content = rtext(file_path)

    for section_title, section_content in split_by_sections(content):
        match section_title:
            case "Paper":
                try:
                    s = section_content.index("```json")
                    paper = section_content[s + 7 :]
                    paper = paper[: paper.rindex("```")]
                except ValueError:
                    paper = section_content
                breakdown["paper"] = json.loads(paper)
            case "Explanation":
                breakdown["explanation"] = md_to_html(section_content)
            case "Order":
                sub_dir_names = resolve_md_list(
                    section_content, ol_filler=sub_dir_names
                ).str_list

    return breakdown, [parent_path / sdn for sdn in sub_dir_names]


def resolve_node(file_path: Path, parent_path: Path, is_b: bool, id: str):
    node: Node = {"id": id, "title": desanitize_filename(file_path.stem)}
    content = rtext(file_path)

    sub_dir_names = get_sub_dir_names(parent_path)

    for section_title, section_content in split_by_sections(content):
        match section_title:
            case "Mini Description":
                node["mini_description"] = md_to_html(section_content)
            case "Description":
                node["description"] = md_to_html(section_content)
            case "Questions":
                node["questions"] = [
                    {"id": f"{id}{i}", "question": md_to_html(q)}
                    for i, q in enumerate(resolve_md_list(section_content).str_list)
                ]
            case "Order":
                sub_dir_names = resolve_md_list(
                    section_content, ol_filler=sub_dir_names
                ).str_list
            case "Related Nodes":
                links = []
                list_obj = resolve_md_list(section_content)

                if list_obj:
                    for item in list_obj.items:
                        match = re.search(r"\[(.*?)\]\((.*?)\)", item.s)
                        if match:
                            path = match.group(2).lstrip("/")

                            # Store the path for now, we'll convert to IDs later
                            link = {"path": path}

                            # Check if there's a reason in a child list
                            if item.child and item.child.items:
                                reason_item = item.child.items[0]
                                if reason_item.s.startswith("Reason: "):
                                    # Remove "Reason: " prefix
                                    link["reason"] = reason_item.s[8:]

                            links.append(link)

                if links:
                    node["links"] = links

    if is_b:
        paper_dir_map: dict[str, str] = {}
        for sub_dir_name in get_sub_dir_names(parent_path):
            paper_title = (
                resolve_breakdown(
                    parent_path / sub_dir_name / f"{sub_dir_name}.md",
                    parent_path / sub_dir_name,
                )[0]
                .get("paper", {})
                .get("title")
            )
            if paper_title:
                paper_dir_map[paper_title] = sub_dir_name

        sub_dir_names_copy = sub_dir_names.copy()
        for i, sub_name in enumerate(sub_dir_names):
            match = re.search(r"Paper: (\"|')(.*?)(\1)", sub_name)
            if match:
                sub_dir_names_copy[i] = paper_dir_map[match.group(2)]

        sub_dir_names = sub_dir_names_copy

    return node, [parent_path / sub_dir_name for sub_dir_name in sub_dir_names]


def format_index(idx: int | str):
    return f".{idx}." if int(idx) > 9 else str(idx)


def build_directory_map(root_path: Path, map_path: Path, breakdowns_identifier="."):
    """Build a map of directories to their node information."""
    directory_map = {}
    path_to_id_map = {}

    # Build the hierarchy and generate IDs
    # Start with root
    root_id = "0"
    root_dir = root_path
    path_to_id_map[str(root_dir)] = root_id

    # Process all directories level by level
    process_directory(
        root_dir, root_id, directory_map, path_to_id_map, breakdowns_identifier
    )

    # Update all links to use IDs instead of paths
    for node_id, node_info in directory_map.items():
        if "links" in node_info:
            for i, link in enumerate(node_info["links"]):
                if "path" in link:
                    path = link["path"]
                    # Extract the path without the filename
                    path_parts = path.split("/")
                    dir_path = str(map_path / "/".join(path_parts[:-1]))

                    # Look up the ID in our path mapping
                    if dir_path in path_to_id_map:
                        # Create a new link object with just id (and reason if present)
                        new_link = {"id": path_to_id_map[dir_path]}
                        if "reason" in link:
                            new_link["reason"] = link["reason"]
                        node_info["links"][i] = new_link
                    else:
                        # Keep the original link if we couldn't resolve it
                        print(
                            f"Warning: Could not resolve path {dir_path} to a node ID"
                        )

    return directory_map


def process_directory(
    dir_path: Path,
    node_id: str,
    directory_map: dict,
    path_to_id_map: dict,
    breakdowns_identifier=".",
):
    is_b = dir_path.name.endswith(breakdowns_identifier)
    dir_name = dir_path.name[: -len(breakdowns_identifier)] if is_b else dir_path.name
    md_file = dir_path / f"{dir_name}.md"

    if md_file.exists():
        node, sub_dirs = resolve_node(md_file, dir_path, is_b, node_id)
        directory_map[node_id] = node

        if sub_dirs:
            if is_b:
                node["breakdowns"] = []
                bs_sub_node_dirs = []

                for idx, b_sub_dir in enumerate(sub_dirs):
                    breakdown, sub_node_dirs = resolve_breakdown(
                        b_sub_dir / f"{b_sub_dir.name}.md", b_sub_dir
                    )
                    breakdown["id"] = f"{node_id}{format_index(idx)}"

                    node["breakdowns"].append(breakdown)
                    bs_sub_node_dirs.append(sub_node_dirs)
            else:
                node["breakdowns"] = [{"id": f"{node_id}0", "sub_nodes": []}]
                bs_sub_node_dirs = [sub_dirs]

            for breakdown, sub_node_dirs in zip(node["breakdowns"], bs_sub_node_dirs):
                for idx, sub_node_dir in enumerate(sub_node_dirs):
                    child_node_id = f"{breakdown['id']}{format_index(idx)}"
                    path_to_id_map[str(sub_node_dir)] = child_node_id

                    process_directory(
                        sub_node_dir,
                        child_node_id,
                        directory_map,
                        path_to_id_map,
                        breakdowns_identifier,
                    )

                    # If the subdirectory was processed (has an entry in directory_map)
                    if child_node_id in directory_map:
                        if not breakdown.get("sub_nodes"):
                            breakdown["sub_nodes"] = []
                        breakdown["sub_nodes"].append(directory_map[child_node_id])


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--production",
        "-p",
        action="store_true",
    )
    return vars(parser.parse_args())


def main(
    production=False,
    root_parent: Path | None = None,
    meta_file: Path | None = None,
    output_file: Path | None = None,
):
    root_parent = root_parent or Path("map-repo" if production else "test_output")
    meta_file = meta_file or (root_parent / "meta.json")
    working_path = Path("source-repo" if production else ".")
    output_file = output_file or (working_path / "map.json")

    meta = rjson(meta_file)

    root_path: Path = root_parent / meta["rootDir"]
    if not root_path.exists() or not root_path.is_dir():
        raise ValueError(f"Root directory '{root_path}' not found.")

    # Build the directory map and generate the JSON structure in one step
    directory_map = build_directory_map(
        root_path, root_parent, meta.get("breakdownsIdentifier") or "."
    )

    # Get the root node
    root_node = directory_map.get("0")
    if not root_node:
        raise ValueError("Could not find the root node.")

    wjson(root_node, output_file)

    print(f"JSON structure reconstructed successfully to '{output_file}'")


# if __name__ == "__main__":
#     main(**parse_args())

if __name__ == "__main__":
    main(
        root_parent=Path("test_output/breakdowns"),
        meta_file=Path("test_data/breakdowns/meta.json"),
        output_file=Path("test_output/breakdowns/map.json"),
    )
