"""Run the local checks before committing or sharing the project."""

import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def run(*command):
    print("\nRunning:", " ".join(command), flush=True)
    env = dict(os.environ, PYTHON=sys.executable)
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def check_files():
    for path in [ROOT / "server.py", ROOT / "verify.py", *ROOT.glob("locksystem/*.py"), *ROOT.glob("tests/*.py")]:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in ROOT.glob("assets/*.svg"):
        ET.parse(path)
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    for relative in re.findall(r'(?:src|href)="([^"]+)"', html):
        if not relative.startswith("#") and not (ROOT / relative).is_file():
            raise ValueError(f"Missing page asset: {relative}")
    notebook = json.loads((ROOT / "VonDoom.ipynb").read_text(encoding="utf-8"))
    if notebook["nbformat"] != 4:
        raise ValueError("Expected notebook format 4.")
    ids = [cell["id"] for cell in notebook["cells"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Notebook cell IDs must be unique.")
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            ast.parse("".join(cell["source"]))
    print("Source syntax, SVGs, page assets and notebook structure passed.")
    return notebook


def run_notebook(notebook):
    namespace = {"__name__": "__main__"}
    executed = 0
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        # Verification must not start a persistent server or ask for a PIN.
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"RUN_PRIVATE_DEMO", "RUN_WEB", "STOP_WEB"}:
                        if not isinstance(node.value, ast.Constant) or node.value.value is not False:
                            raise ValueError(f"Set {target.id} = False before notebook verification.")
        exec(compile(source, f"notebook-cell-{cell['id']}", "exec"), namespace)
        executed += 1
    print(f"Executed {executed} notebook code cells.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", action="store_true", help="Also execute the notebook with optional prompts and server disabled.")
    args = parser.parse_args()
    os.chdir(ROOT)
    notebook = check_files()
    run(sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")
    node = shutil.which("node")
    if node:
        run(node, "--check", "assets/app.js")
        run(node, "tests/test_frontend.cjs", "--integration")
    else:
        print("Node.js was not found; JavaScript checks were skipped.")
    if args.notebook:
        run_notebook(notebook)
    print("All available requested checks passed.")


if __name__ == "__main__":
    main()
