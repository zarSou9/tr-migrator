import argparse
import os
from pathlib import Path

from create_map import md_to_html
from utils import rjson, wjson


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--production",
        "-p",
        action="store_true",
    )
    parser.add_argument("--map-repo", type=str)
    return vars(parser.parse_args())


def setEnv(path_name):
    with open(os.environ["GITHUB_ENV"], "a") as f:
        f.write(f"PATH_NAME={path_name}\n")


def main(
    production=False,
    map_repo="",
    map_dir: str | None = None,
    output_file_name="meta-converted.json",
):
    map_path = Path(map_dir or ("map-repo" if production else "test_output"))
    source_path = Path("source-repo" if production else ".")

    meta = rjson(map_path / "meta.json")

    if "rootDir" in meta:
        del meta["rootDir"]
    if "sourceFile" in meta:
        del meta["sourceFile"]

    if production:
        allowed = rjson(source_path / "allowed_maps.json")
        if not allowed.get(map_repo):
            raise ValueError(f"Repo: {map_repo} not allowed")

        meta["pathName"] = allowed[map_repo]["pathName"]
        setEnv(allowed[map_repo]["pathName"])

    for section in ["note", "coverRootDescription"]:
        if meta.get(section):
            meta[section] = md_to_html(meta[section])

    wjson(meta, source_path / output_file_name)


if __name__ == "__main__":
    main(**parse_args())
