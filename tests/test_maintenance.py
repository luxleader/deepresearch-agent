import subprocess
from pathlib import Path

from scripts.check_change_record import check_change_record


def git(root, *args):
    result = subprocess.run(["git", "-c", f"safe.directory={root.as_posix()}", *args], cwd=root,
                            check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip()


def test_code_change_requires_own_record_with_matching_id(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.invalid")
    git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "base.txt").write_text("initial")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial")
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "app.py").write_text("pass")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "feat(DR-20261014-999): missing record")
    assert any("Markdown" in e for e in check_change_record(base, "HEAD", tmp_path))
    before = git(tmp_path, "rev-parse", "HEAD")
    record = tmp_path / "docs/changes/999.md"
    record.parent.mkdir(parents=True)
    record.write_text("# DR-20261014-998\n\n## 需求与改动\nx\n## 验证\nx\n## 限制与回退\nx\n## 备份与溯源\nx", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "feat(DR-20261014-998): recorded")
    assert check_change_record(before, "HEAD", tmp_path) == []
    assert len(check_change_record(base, "HEAD", tmp_path)) >= 1


def test_packaged_static_assets_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "src/deepresearch_app/static/index.html").exists()
