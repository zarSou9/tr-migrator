import json
import os
from pathlib import Path

from convert_from_directories import convert_markdown_to_html, parse_args


def setEnv(path_name):
    with open(os.environ["GITHUB_ENV"], "a") as f:
        f.write(f"PATH_NAME={path_name}\n")


def main(production=False):
    map_path = Path("map-repo" if production else "test_data")
    source_path = Path("source-repo" if production else ".")

    meta = json.loads((map_path / "meta.json").read_text(encoding="utf-8"))

    if production:
        setEnv(meta["pathName"])

    for section in ["note", "cover_root_description"]:
        if meta.get(section):
            meta[section] = convert_markdown_to_html(meta[section])

    (source_path / "meta-converted.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main(**parse_args())
