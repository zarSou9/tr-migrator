import argparse
import json
import os
from pathlib import Path

from convert_from_directories import convert_markdown_to_html


def setEnv(path_name):
    with open(os.environ["GITHUB_ENV"], "a") as f:
        f.write(f"PATH_NAME={path_name}\n")


def main(production=False, map_repo=""):
    map_path = Path("map-repo" if production else "test_data")
    source_path = Path("source-repo" if production else ".")

    meta = json.loads((map_path / "meta.json").read_text(encoding="utf-8"))

    if production:
        allowed = json.loads((source_path / "allowed_maps.json").read_text())
        if not allowed.get(map_repo):
            raise ValueError(f"Repo: {map_repo} not allowed")
        setEnv(allowed[map_repo]["pathName"])

    for section in ["note", "coverRootDescription"]:
        if meta.get(section):
            meta[section] = convert_markdown_to_html(meta[section])

    (source_path / "meta-converted.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--production",
        "-p",
        action="store_true",
    )
    parser.add_argument("--map-repo", type=str)
    return vars(parser.parse_args())


if __name__ == "__main__":
    main(**parse_args())
