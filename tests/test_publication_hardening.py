import ast
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


def test_package_modules_do_not_call_print():
    """Importable package code should use logging, not stdout."""
    src_root = Path(__file__).resolve().parents[1] / "src"
    offenders = []

    for path in src_root.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                offenders.append(f"{path.relative_to(src_root.parent)}:{node.lineno}")

    assert offenders == []


def test_package_modules_do_not_configure_root_logging_except_helper():
    """Only the explicit configure_logging helper may call logging.basicConfig."""
    src_root = Path(__file__).resolve().parents[1] / "src"
    offenders = []

    for path in src_root.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "basicConfig"
            ):
                continue

            current = node
            enclosing_function = None
            while current in parents:
                current = parents[current]
                if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    enclosing_function = current.name
                    break

            if enclosing_function != "configure_logging":
                offenders.append(f"{path.relative_to(src_root.parent)}:{node.lineno}")

    assert offenders == []
