from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "energy_usage"
MANIFEST = COMPONENT / "manifest.json"


def test_permanent_product_identity() -> None:
    manifest = json.loads(MANIFEST.read_text())
    assert list(manifest) == ["domain", "name", *sorted(set(manifest) - {"domain", "name"})]
    assert manifest["domain"] == "energy_usage"
    assert manifest["name"] == "Energy Usage"
    assert manifest["version"] == "0.1.0-rc.3"
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
    assert "ha-energy-usage-0.1.0-rc.3.zip" in workflow


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
    assert "0.1.0-rc.3" in documents["README.md"]
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


def test_development_and_ownership_metadata_use_permanent_identity() -> None:
    project = (ROOT / "pyproject.toml").read_text()
    lock = (ROOT / "uv.lock").read_text()
    owners = (ROOT / ".github" / "CODEOWNERS").read_text()
    assert 'name = "ha-energy-usage"' in project
    assert 'version = "0.1.0-rc.3"' in project
    assert "provider-neutral Energy Usage" in project
    assert 'name = "ha-energy-usage"' in lock
    assert 'version = "0.1.0rc3"' in lock
    assert "custom_components/energy_usage/ @BeauDevCode" in owners
    assert "custom_components/entergy_mobile/" not in owners


def test_workflows_are_pinned_least_privilege_and_cover_every_gate() -> None:
    workflows = {
        path.name: path.read_text() for path in (ROOT / ".github" / "workflows").glob("*.yml")
    }
    assert {"ci.yml", "codeql.yml", "release.yml", "secret-scan.yml", "validate.yml"} <= set(
        workflows
    )
    for name, source in workflows.items():
        assert "permissions: {}" in source, name
        for action in re.findall(r"uses:\s*([^\s#]+)", source):
            assert re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", action), (name, action)

    ci = workflows["ci.yml"]
    for token in (
        "HA 2026.9.3",
        "HA 2026.9.4",
        "ruff format --check .",
        "ruff check .",
        "mypy --explicit-package-bases custom_components/energy_usage",
        "--cov-fail-under=95",
        "scripts/check_dependency_audit.py 2026.9.3",
        "scripts/check_dependency_audit.py 2026.9.4",
    ):
        assert token in ci
    assert "hacs/action@" in workflows["validate.yml"]
    assert "home-assistant/actions/hassfest@" in workflows["validate.yml"]
    assert "gitleaks/gitleaks-action@" in workflows["secret-scan.yml"]
    assert "GITLEAKS_ENABLE_UPLOAD_ARTIFACT: 'false'" in workflows["secret-scan.yml"]
    assert "github/codeql-action/analyze@" in workflows["codeql.yml"]


def test_release_workflow_requires_exact_tag_builds_and_attests_exact_archive() -> None:
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    for token in (
        "refs/tags/v0.1.0-rc.3",
        "scripts/build_release.py",
        "ha-energy-usage-0.1.0-rc.3.zip",
        "sha256sum --check",
        "actions/attest@",
        "subject-path: dist/ha-energy-usage-0.1.0-rc.3.zip",
    ):
        assert token in release


def test_release_builder_is_deterministic_exact_and_embeds_commit(tmp_path: Path) -> None:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    outputs = [tmp_path / "first.zip", tmp_path / "second.zip"]
    for output in outputs:
        subprocess.run(
            [
                sys.executable,
                "scripts/build_release.py",
                "--version",
                "0.1.0-rc.3",
                "--commit",
                commit,
                "--output",
                str(output),
            ],
            cwd=ROOT,
            check=True,
        )
    assert (
        hashlib.sha256(outputs[0].read_bytes()).digest()
        == hashlib.sha256(outputs[1].read_bytes()).digest()
    )
    tracked = set(
        subprocess.check_output(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                "HEAD",
                "custom_components/energy_usage",
            ],
            cwd=ROOT,
            text=True,
        ).splitlines()
    )
    with zipfile.ZipFile(outputs[0]) as archive:
        expected_members = {
            *tracked,
            "custom_components/energy_usage/release.json",
        }
        assert set(archive.namelist()) == expected_members
        assert archive.namelist() == sorted(expected_members)
        release = json.loads(archive.read("custom_components/energy_usage/release.json"))
        manifest = json.loads(archive.read("custom_components/energy_usage/manifest.json"))
    assert release == {"commit": commit, "version": "0.1.0-rc.3"}
    assert manifest["domain"] == "energy_usage"
    assert manifest["version"] == release["version"]
