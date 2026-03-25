"""Utilities for generating KOTS unified diffs and other KOTS-specific helpers."""
import difflib

import yaml


def make_kots_diff(configvalues_raw: dict, key: str, old_value: str, new_value: str) -> str:
    """Generate a unified diff for a KOTS configvalues change.

    Args:
        configvalues_raw: The full parsed configvalues.yaml dict.
        key: The KOTS config key being changed.
        old_value: The current (bad) value.
        new_value: The recommended (fixed) value.

    Returns:
        A unified diff string suitable for a .patch file.
    """
    before = dict(configvalues_raw)

    # Build the after state with the updated key
    after = dict(configvalues_raw)
    after_spec = dict((after.get("spec") or {}))
    after_values = dict((after_spec.get("values") or {}))
    after_values[key] = {"value": new_value}
    after_spec["values"] = after_values
    after["spec"] = after_spec

    before_yaml = yaml.dump(before, default_flow_style=False, sort_keys=True)
    after_yaml = yaml.dump(after, default_flow_style=False, sort_keys=True)

    diff_lines = list(
        difflib.unified_diff(
            before_yaml.splitlines(keepends=True),
            after_yaml.splitlines(keepends=True),
            fromfile="a/configvalues.yaml",
            tofile="b/configvalues.yaml",
        )
    )
    return "".join(diff_lines)
