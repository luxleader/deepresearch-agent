"""Check each commit has its own added change record and matching change ID."""
import argparse
import re
import subprocess
from pathlib import Path


def check_change_record(base_ref: str, head_ref: str, repo_root=None) -> list[str]:
    root = Path(repo_root or Path(__file__).resolve().parents[1]).resolve()

    def git(*args):
        return subprocess.run(["git", "-c", f"safe.directory={root.as_posix()}", *args], cwd=root,
                              check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()

    errors = []
    commits = git("rev-list", "--reverse", "--no-merges", f"{base_ref}..{head_ref}").splitlines()
    for sha in commits:
        message = git("show", "-s", "--format=%B", sha)
        ids = set(re.findall(r"DR-\d{8}-\d{3}", message))
        added = git("diff-tree", "--root", "--no-commit-id", "--name-only", "--diff-filter=A", "-r", sha).splitlines()
        records = [p for p in added if p.startswith("docs/changes/") and p.endswith(".md") and p != "docs/changes/README.md"]
        if not ids:
            errors.append(f"{sha[:7]}: commit missing change ID")
        if not records:
            errors.append(f"{sha[:7]}: missing own added Markdown record")
        found = set()
        for path in records:
            content = git("show", f"{sha}:{path}")
            found.update(re.findall(r"DR-\d{8}-\d{3}", content))
            for label, pattern in {"需求/改动": r"需求|改动", "验证": r"验证", "限制": r"限制|边界",
                                   "回退": r"回退", "溯源": r"备份|溯源|提交|同步|GitHub"}.items():
                if not re.search(pattern, content):
                    errors.append(f"{sha[:7]}: {path} missing {label}")
        if records and not ids & found:
            errors.append(f"{sha[:7]}: commit and record IDs do not match")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_ref")
    parser.add_argument("head_ref", nargs="?", default="HEAD")
    args = parser.parse_args()
    errors = check_change_record(args.base_ref, args.head_ref)
    print("\n".join(errors) if errors else "Change records OK (presence only, not factual validation).")
    raise SystemExit(bool(errors))
