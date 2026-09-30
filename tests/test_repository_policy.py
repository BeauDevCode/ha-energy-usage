from __future__ import annotations

import ast
import json
from pathlib import Path

from PIL import Image

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


def test_public_documentation_describes_the_actual_release_and_limits() -> None:
    required = {
        "README.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "docs/PRIVACY.md",
        "docs/PROVIDERS.md",
        "docs/INSTALL.md",
        "docs/ROLLBACK.md",
    }
    documents = {path: (ROOT / path).read_text() for path in required}
    combined = "\n".join(documents.values())

    assert "Energy Usage" in documents["README.md"]
    assert "0.1.0-rc.1" in documents["README.md"]
    assert "one service location" in combined
    assert "not bill-grade" in combined
    assert "delayed" in combined
    assert "not an encrypted password vault" in combined
    assert "Entergy is the only available provider" in documents["docs/PROVIDERS.md"]
    assert "no release date" in documents["docs/PROVIDERS.md"]
    assert "protected" in documents["docs/INSTALL.md"]
    assert "ha core check" in documents["docs/INSTALL.md"]
    assert "one planned restart" in documents["docs/INSTALL.md"]
    assert "custom_components/energy_usage/" in documents["docs/INSTALL.md"]
    assert "custom_components/entergy_mobile/" in documents["docs/INSTALL.md"]
    assert "Never overwrite" in documents["docs/INSTALL.md"]
    assert "does not delete Recorder history" in documents["docs/ROLLBACK.md"]

    stale_public_identity = (
        "github.com/BeauDevCode/ha-entergy/releases",
        "ha-entergy-1.0.0-rc.1",
        "# Entergy Usage",
    )
    assert not any(value in combined for value in stale_public_identity)


def test_brand_assets_are_generic_and_well_formed() -> None:
    svg_path = ROOT / "assets" / "energy-usage-icon.svg"
    png_path = COMPONENT / "brand" / "icon.png"
    svg = svg_path.read_text()
    assert 'viewBox="0 0 256 256"' in svg
    assert "Energy Usage" in svg
    assert "Entergy" not in svg
    with Image.open(png_path) as image:
        assert image.format == "PNG"
        assert image.mode == "RGBA"
        assert image.size == (256, 256)
        assert image.getbbox() == (0, 0, 256, 256)
