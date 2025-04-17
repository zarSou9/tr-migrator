import json
import re
from pathlib import Path
from typing import TypedDict, Union

from pydantic import BaseModel, ConfigDict


class Question(TypedDict, total=False):
    id: str | None
    question: str


class Breakdown(TypedDict, total=False):
    id: str | None
    title: str | None
    paper: dict | None
    explanation: str | None
    sub_nodes: list["Node"]


class Node(TypedDict, total=False):
    id: str | None
    title: str
    description: str | None
    mini_description: str | None
    questions: list[Question] | None
    papers: list[dict] | None
    breakdowns: list[Breakdown] | None


def get_unique_path(path: Path, spacer="_") -> Path:
    if not path.exists():
        return path

    # Split the path into stem and suffix
    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    counter = 1
    while True:
        new_path = parent / f"{stem}{spacer}{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def truncate_string(text: str, max_length=18, end="..."):
    return text[:max_length] + (
        end if len(text) > max_length and not text.endswith(end) else ""
    )


def wtext(text: str, path: str | Path):
    Path(path).write_text(text)


def rtext(path: str | Path):
    return Path(path).read_text()


def wjson(d: dict, path: str | Path, **kwargs):
    wtext(json.dumps(d, ensure_ascii=False, **kwargs), path)


def rjson(path: str | Path) -> dict:
    return json.loads(rtext(path))


def convert_no_ascii(file: str):
    wjson(rjson(file), file)


class ListItem(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    s: str
    child: Union["UL", None] = None


def resolve_item(item: str | ListItem):
    return ListItem(s=item) if isinstance(item, str) else item


class UL:
    kind = "unordered"

    def __init__(self, items: list[str | ListItem] = []):
        self.items = [resolve_item(item) for item in items]

    @property
    def str_list(self):
        return [item.s for item in self.items]

    def add(self, s: str, child: Union["UL", None] = None):
        self.items.append(ListItem(s=s, child=child))

    def insert(self, idx: int, item: str | ListItem, rem_existing=True):
        item = resolve_item(item)
        if rem_existing:
            try:
                self.items.remove(item)
            except ValueError:
                self.items.pop(idx)
        self.items.insert(idx, item)

    def to_str(self, indent=0, prefix="-", spacing=0):
        strs: list[str] = []
        for item in self.items:
            strs.append(f"{indent * '\t'}{prefix} {item.s}")
            if item.child:
                strs.extend(item.child.to_str(indent + 1, prefix).split("\n"))

        return f"\n{spacing * '\n'}".join(strs)

    def __str__(self) -> str:
        return self.to_str()


class OL(UL):
    kind = "ordered"

    def to_str(self, indent=0, prefix="-", spacing=0):
        strs: list[str] = []
        for i, item in enumerate(self.items):
            strs.append(f"{indent * '\t'}{i + 1}. {item.s}")
            if item.child:
                strs.extend(item.child.to_str(indent + 1, prefix).split("\n"))

        return f"\n{spacing * '\n'}".join(strs)


def is_number_line(line: str):
    return line[0].isdigit() and line[1:].startswith(". ")


def resolve_md_list(
    text: str, allowed_prefixes=("-", "*"), ol_filler: list[str | ListItem] = []
):
    """
    Convert a text-based list into UL or OL objects.
    Detects list type based on prefix (-, *, numbers) and handles nested sublists.
    """
    lines = text.strip().split("\n")
    if not lines:
        return None

    idx: int | None = None
    root_list = OL(ol_filler) if is_number_line(lines[0].lstrip()) else UL()

    list_stack = [(0, root_list)]  # (indent_level, list_object)

    for i, full_line in enumerate(lines):
        line = full_line.lstrip()
        indent_level = len(full_line) - len(line)

        if not line:  # Skip empty lines
            continue

        temp_list_stack = list_stack.copy()  # Temporary until line is validated
        while temp_list_stack and temp_list_stack[-1][0] > indent_level:
            temp_list_stack.pop()

        if not temp_list_stack:  # Fallback if stack is empty
            temp_list_stack = [(0, root_list)]

        parent_index, parent_list = temp_list_stack[-1]

        if parent_list.kind == "ordered":
            if not is_number_line(line):
                continue  # Skip invalid lines
            idx_str, item_text = line.split(". ", 1)
            idx = int(idx_str) - 1
        else:
            if not any(line.startswith(prefix + " ") for prefix in allowed_prefixes):
                continue  # Skip invalid lines
            item_text = line[2:]

        list_stack = temp_list_stack

        # Check if next line indicates a sublist
        child_list = None
        if i < len(lines) - 1:
            next_line = lines[i + 1]
            next_indent = len(next_line) - len(next_line.lstrip())

            if next_indent > indent_level:
                child_list = OL() if is_number_line(next_line.lstrip()) else UL()
                list_stack.append((indent_level + 1, child_list))

        if parent_list == root_list and parent_list.kind == "ordered" and ol_filler:
            parent_list.insert(idx, ListItem(s=item_text, child=child_list))
        else:
            parent_list.add(item_text, child_list)

    return root_list


def md_to_html(text: str | None):
    if not text:
        return text

    # Convert markdown links to HTML links with target="_blank"
    # Pattern: [text](url)
    link_pattern = r"\[(.*?)\]\((.*?)\)"
    html_text = re.sub(link_pattern, r'<a href="\2" target="_blank">\1</a>', text)

    # Convert newlines to <br> tags
    html_text = html_text.replace("\n", "<br>")

    # Convert *text* to <i>text</i>
    italic_pattern = r"\*(.*?)\*"
    html_text = re.sub(italic_pattern, r"<i>\1</i>", html_text)

    # Remove comments <!-- --> and %% %%
    html_text = re.sub(r"<!--.*?-->", "", html_text, flags=re.DOTALL)
    html_text = re.sub(r"%%.*?%%", "", html_text, flags=re.DOTALL)

    return html_text


def html_to_md(text: str | None, convert=True):
    if not text or not convert:
        return text
    pattern = (
        r"<a\s+href=['\"]([^'\"]+)['\"](?:\s+target=['\"][^'\"]*['\"])?\s*>([^<]+)</a>"
    )
    markdown_text = re.sub(pattern, r"[\2](\1)", text)
    # Remove spaces before or after <br> tags
    markdown_text = re.sub(r"\s*<br\s*\/?>\s*", "<br>", markdown_text)
    markdown_text = re.sub(r"<br\s*\/?>", "\n", markdown_text)

    markdown_text = re.sub(r"(\S)<i>", r"\1 <i>", markdown_text)
    markdown_text = re.sub(r"</i>(\S)", r"</i> \1", markdown_text)
    markdown_text = re.sub(
        r"<i>\s*(.*?)\s*</i>", lambda m: f"*{m.group(1).strip()}*", markdown_text
    )

    return markdown_text


if __name__ == "__main__":
    pass
