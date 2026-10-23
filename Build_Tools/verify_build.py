"""Inspect COLLECT origins, Qt runtime hashes and a captured frozen smoke."""
import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pefile
import PySide6


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    allowed = [root, Path(sys.prefix), Path(sys.base_prefix), Path(os.environ["SystemRoot"])]
    entries = []

    def inspect(value):
        if isinstance(value, (tuple, list)):
            if len(value) == 3 and all(isinstance(x, str) for x in value):
                if value[2] in ("BINARY", "EXTENSION"):
                    source = Path(value[1]).resolve()
                    assert any(source.is_relative_to(p.resolve()) for p in allowed), value[0]
                    entries.append(value)
            else:
                for child in value:
                    inspect(child)

    toc = args.work / "work" / "AudioPlayer" / "COLLECT-00.toc"
    inspect(ast.literal_eval(toc.read_text(encoding="utf-8")))
    assert entries, "COLLECT native origins not inspected"
    qt = Path(PySide6.__file__).parent
    target = root / "AudioPlayer"
    version = (root / "VERSION").read_text().strip()
    helper_name = f"AudioPlayerShell-{version}.dll"
    helper = target / helper_name
    assert helper.read_bytes() == (args.work / "native" / helper_name).read_bytes()
    with pefile.PE(str(helper)) as native:
        imports = [item.dll.decode().lower() for item in native.DIRECTORY_ENTRY_IMPORT]
        assert set(imports) <= {"ole32.dll", "shell32.dll", "advapi32.dll", "kernel32.dll", "user32.dll"}
        assert native.FILE_HEADER.Machine == 0x8664
        exports = {item.name for item in native.DIRECTORY_ENTRY_EXPORT.symbols}
        assert {b"DllGetClassObject", b"DllCanUnloadNow"} <= exports
    runtime = []
    for source in qt.glob("*140*.dll"):
        bundled = target / "_internal" / source.name
        assert bundled.is_file(), source.name
        assert hashlib.sha256(source.read_bytes()).digest() == hashlib.sha256(bundled.read_bytes()).digest()
        runtime.append(source.name)
    env = os.environ.copy()
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    env["TEMP"] = env["TMP"] = str(args.work)
    for name in ("PYTHONPATH", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH"):
        env.pop(name, None)
    report_path = args.work / "frozen-smoke.json"
    result = subprocess.run([str(target / "AudioPlayer.exe"), "--smoke-test", str(report_path)],
                            cwd=args.work, env=env, capture_output=True, timeout=35)
    (args.work / "frozen-stdout.log").write_bytes(result.stdout)
    (args.work / "frozen-stderr.log").write_bytes(result.stderr)
    report = {"collect_binary_count": len(entries), "foreign_origins": 0,
              "shell_helper": helper_name, "shell_helper_imports": imports,
              "shell_helper_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
              "qt_msvc_runtime": runtime, "exit_code": result.returncode,
              "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr)}
    if report_path.exists():
        report["smoke"] = json.loads(report_path.read_text(encoding="utf-8"))
    (args.work / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    assert result.returncode == 0 and report.get("smoke", {}).get("ok"), "Frozen smoke failed"
    assert not re.search(rb"Traceback|ImportError|DLL load failed|PyInstallerImportError|\[PYI-.*:ERROR\]",
                         result.stdout + result.stderr), "Frozen runtime diagnostics contain a fatal error"


if __name__ == "__main__":
    main()
