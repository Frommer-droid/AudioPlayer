"""Fail-closed DLL provenance and one consistent Qt MSVC runtime."""
import json
import os
import sys
from pathlib import Path


def validate_binaries(binaries, root, qt):
    allowed = [Path(root).resolve(), Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve(),
               Path(os.environ["SystemRoot"]).resolve()]
    result = []
    replacements = []
    for destination, source, kind in binaries:
        resolved = Path(source).resolve()
        if not any(resolved.is_relative_to(folder) for folder in allowed):
            raise RuntimeError(f"Untrusted binary origin: {destination}: {resolved}")
        name = Path(destination).name.lower()
        if ("/" not in destination.replace("\\", "/") and
                name.startswith(("vcruntime140", "msvcp140", "concrt140", "vcomp140", "vcamp140",
                                 "vccorlib140")) and (qt / name).is_file()):
            source = str(qt / name)
            replacements.append(destination)
        result.append((destination, source, kind))
    existing = {destination.lower() for destination, _, _ in result}
    for path in qt.glob("*140*.dll"):
        if path.name.lower() not in existing:
            result.append((path.name, str(path), "BINARY"))
    report = os.environ.get("AUDIOPLAYER_BINARY_REPORT")
    if report:
        Path(report).write_text(json.dumps({"allowed": list(map(str, allowed)),
            "qt_runtime_replacements": replacements, "binaries": result}, indent=2), encoding="utf-8")
    return result
