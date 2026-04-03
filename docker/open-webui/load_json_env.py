#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: load_json_env.py <json-file>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    payload = json.loads(path.read_text(encoding="utf-8"))
    sys.stdout.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
