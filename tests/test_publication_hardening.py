from pathlib import Path


def test_package_modules_do_not_ship_runnable_main_blocks():
    """Examples belong under examples/, not in importable package modules."""
    src_root = Path(__file__).resolve().parents[1] / "src"

    offenders = [
        str(path.relative_to(src_root.parent))
        for path in src_root.rglob("*.py")
        if 'if __name__ == "__main__"' in path.read_text()
    ]

    assert offenders == []
