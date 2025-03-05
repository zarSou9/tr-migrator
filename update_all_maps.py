import json
import os
import time
from pathlib import Path

import requests


def main():
    allowed_maps: dict = json.loads(Path("allowed_maps.json").read_text())

    # Get the GitHub token from environment variables
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("Error: GITHUB_TOKEN environment variable not set")
        return

    # Get the current repository from environment variables
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        print("Error: GITHUB_REPOSITORY environment variable not set")
        return

    # Trigger update workflows for each map
    for map_repo in allowed_maps.keys():
        print(f"Triggering update for {map_repo}")

        # Create the dispatch event
        url = f"https://api.github.com/repos/{repo}/dispatches"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {github_token}",
        }
        payload = {
            "event_type": "update_research_map",
            "client_payload": {"map_repo": map_repo},
        }

        # Send the request
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            print(f"Successfully triggered update for {map_repo}")
        except Exception as e:
            print(f"Error triggering update for {map_repo}: {e}")

        time.sleep(2)


if __name__ == "__main__":
    main()
