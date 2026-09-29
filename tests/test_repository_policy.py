from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "energy_usage"
MANIFEST = COMPONENT / "manifest.json"


def test_permanent_product_identity() -> None:
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["domain"] == "energy_usage"
    assert manifest["name"] == "Energy Usage"
    assert manifest["version"] == "0.1.0-rc.1"
    assert manifest["single_config_entry"] is True
    assert not (ROOT / "custom_components" / "entergy_mobile").exists()
    assert "BeauDevCode/ha-energy-usage" in manifest["documentation"]


def test_constant_and_package_imports_are_provider_neutral() -> None:
    const_tree = ast.parse((COMPONENT / "const.py").read_text())
    assignments = {
        target.id: ast.literal_eval(node.value)
        for node in const_tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance((target := node.target), ast.Name)
        and isinstance(node.value, ast.Constant)
    }
    assert assignments["DOMAIN"] == "energy_usage"
    for path in [*COMPONENT.rglob("*.py"), *ROOT.glob("tests/**/*.py")]:
        tree = ast.parse(path.read_text())
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert "custom_components.entergy_mobile" not in imported_modules


def test_notice_preserves_attribution_without_endorsement() -> None:
    notice = (ROOT / "NOTICE.md").read_text()
    assert "daviddelahoz/ha-entergy" in notice
    assert "BeauDevCode/ha-entergy" in notice
    assert "not affiliated with, endorsed by, or supported by Entergy" in notice


def test_release_archive_policy_uses_only_generic_component_tree() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert "custom_components/energy_usage/" in workflow
    assert "custom_components/entergy_mobile/" not in workflow
    assert "ha-energy-usage-0.1.0-rc.1.zip" in workflow
