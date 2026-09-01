"""Submit a fixed ComfyUI API workflow for a local smoke test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workflow", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8188")
    args = parser.parse_args()

    workflow = json.loads(args.workflow.read_text(encoding="utf-8"))
    workflow.pop("_movie_agent", None)
    request = Request(
        f"{args.base_url.rstrip('/')}/prompt",
        data=json.dumps({"prompt": workflow}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:  # nosec B310: explicitly configured local endpoint
        print(response.read().decode("utf-8"))


if __name__ == "__main__":
    main()
