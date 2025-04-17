from pathlib import Path

import pytest

from convert_to_directories import main as json_to_dirs
from create_map import main as dirs_to_json
from utils import rjson

TEST_DATA = Path("test_data")
TEST_OUTPUT = Path("test_output")


@pytest.mark.parametrize(
    "map_name",
    [
        "fli",
        # "large",
        # "breakdowns",
    ],
)
def test_cycle_equal(map_name: str):
    json_to_dirs(TEST_DATA / map_name / "map.json", TEST_OUTPUT / map_name)
    dirs_to_json(
        repo_root=TEST_OUTPUT / map_name,
        meta_file=TEST_DATA / map_name / "meta.json",
        output_file=TEST_OUTPUT / map_name / "map.json",
    )
    assert rjson(TEST_DATA / map_name / "map.json") == rjson(
        TEST_OUTPUT / map_name / "map.json"
    )
