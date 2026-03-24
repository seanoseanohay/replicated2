"""Hygiene ratchet: ensures the codebase doesn't shrink unexpectedly.

These tests act as a floor — they will fail if production code, detection
rules, API routes, or models are accidentally deleted.  Bump the minimums
when intentional additions are made; never lower them.
"""

from pathlib import Path

APP_ROOT = Path(__file__).parent.parent / "app"


def _py_files(directory: Path) -> list[Path]:
    return [
        p
        for p in directory.rglob("*.py")
        if "__pycache__" not in str(p) and p.name != "__init__.py"
    ]


def test_production_module_count() -> None:
    """At least 74 non-init Python files exist under app/."""
    files = _py_files(APP_ROOT)
    assert len(files) >= 74, (
        f"Expected >= 74 production modules, found {len(files)}. "
        "If you deleted code intentionally, lower this threshold."
    )


def test_detection_rule_count() -> None:
    """At least 19 detection rules are registered."""
    rules_dir = APP_ROOT / "detection" / "rules"
    rule_files = [p for p in rules_dir.glob("*.py") if p.name != "__init__.py"]
    assert len(rule_files) >= 19, (
        f"Expected >= 19 detection rules, found {len(rule_files)}."
    )


def test_api_route_count() -> None:
    """At least 10 API route modules exist."""
    routes_dir = APP_ROOT / "api" / "routes"
    route_files = [p for p in routes_dir.glob("*.py") if p.name != "__init__.py"]
    assert len(route_files) >= 10, (
        f"Expected >= 10 API route modules, found {len(route_files)}."
    )


def test_model_count() -> None:
    """At least 7 ORM model files exist."""
    models_dir = APP_ROOT / "models"
    model_files = [p for p in models_dir.glob("*.py") if p.name != "__init__.py"]
    assert len(model_files) >= 7, (
        f"Expected >= 7 model files, found {len(model_files)}."
    )


def test_detection_registry_imports_all_rules() -> None:
    """The detection registry imports every rule file in the rules directory."""
    rules_dir = APP_ROOT / "detection" / "rules"
    registry_path = APP_ROOT / "detection" / "registry.py"

    rule_names = {p.stem for p in rules_dir.glob("*.py") if p.name != "__init__.py"}
    registry_text = registry_path.read_text()

    missing = [name for name in rule_names if name not in registry_text]
    assert not missing, (
        f"The following rule modules are not imported in registry.py: {missing}"
    )
