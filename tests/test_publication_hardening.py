import re
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"


def test_package_modules_do_not_ship_runnable_main_blocks():
    """Examples belong under examples/, not in importable package modules."""
    offenders = [
        str(path.relative_to(SRC_ROOT.parent))
        for path in SRC_ROOT.rglob("*.py")
        if 'if __name__ == "__main__"' in path.read_text()
    ]

    assert offenders == []


def test_package_modules_do_not_print():
    """Library code must not write to stdout via print().

    print() belongs in examples/, not in importable package modules; a library
    that prints pollutes the host application's output. Demo/console behaviour
    lives under examples/.
    """
    print_call = re.compile(r"\bprint\s*\(")
    offenders = []
    for path in SRC_ROOT.rglob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            code = line.split("#", 1)[0]
            if print_call.search(code):
                offenders.append(f"{path.relative_to(SRC_ROOT.parent)}:{lineno}")

    assert offenders == [], f"print() calls in shipped code: {offenders}"
