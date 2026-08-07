"""Baseline architecture metrics for Milestone 4.5."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def nonblank_loc(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.strip():
                total += 1
    return total


def count_patterns(paths: list[Path], patterns: dict[str, str]) -> dict[str, int]:
    counts = {name: 0 for name in patterns}
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name, pattern in patterns.items():
            counts[name] += len(re.findall(pattern, text, flags=re.M))
    return counts


def main() -> None:
    py_src = sorted((ROOT / "src").rglob("*.py"))
    py_tests = sorted((ROOT / "tests").rglob("*.py"))
    editor = ROOT / "unity-package" / "Editor"
    cs_src = sorted(p for p in editor.rglob("*.cs") if "Tests" not in p.parts)
    cs_tests = sorted((editor / "Tests").rglob("*.cs"))

    print("PY_SOURCE_FILES", len(py_src))
    print("PY_TEST_FILES", len(py_tests))
    print("PY_SOURCE_LOC", nonblank_loc(py_src))
    print("PY_TEST_LOC", nonblank_loc(py_tests))
    print("CS_SOURCE_FILES", len(cs_src))
    print("CS_TEST_FILES", len(cs_tests))
    print("CS_SOURCE_LOC", nonblank_loc(cs_src))
    print("CS_TEST_LOC", nonblank_loc(cs_tests))
    print(
        "PY_CLASSES",
        count_patterns(py_src, {"class": r"^class\s+\w+"})["class"],
    )
    print(
        "CS_TYPES",
        count_patterns(cs_src, {"t": r"\b(class|struct|enum|interface)\s+\w+"})["t"],
    )
    print(
        "PY_PROTOCOL_ABC",
        count_patterns(py_src, {"p": r"\b(Protocol|ABC)\b"})["p"],
    )
    print(
        "CS_INTERFACES",
        count_patterns(cs_src, {"i": r"\binterface\s+\w+"})["i"],
    )
    print(
        "SERVICE_LIKE",
        count_patterns(
            py_src + cs_src,
            {
                "s": (
                    r"\b(class|interface)\s+\w*(Service|Manager|Registry|"
                    r"Repository|Factory|Provider|Resolver|Adapter|Handler|Controller)\w*"
                )
            },
        )["s"],
    )
    tiny = 0
    sizes: list[tuple[int, str]] = []
    for path in py_src + cs_src:
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        ]
        n = len(lines)
        sizes.append((n, path.relative_to(ROOT).as_posix()))
        if n < 30:
            tiny += 1
    print("FILES_UNDER_30", tiny)
    print("LARGEST_10")
    for n, rel in sorted(sizes, reverse=True)[:10]:
        print(f"  {n:4d} {rel}")


if __name__ == "__main__":
    main()
