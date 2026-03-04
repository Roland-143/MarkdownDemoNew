#!/usr/bin/env python3
"""Fail pre-commit when direct dependencies use GPL-family licenses."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from importlib import metadata


ROOT = Path(__file__).resolve().parents[1]
GPL_RE = re.compile(
    r"(?:\bAGPL\b|\bLGPL\b|\bGPL\b|GNU\s+GENERAL\s+PUBLIC\s+LICENSE)",
    re.IGNORECASE,
)
REQ_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")


@dataclass
class Finding:
    package: str
    detail: str


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower().strip()


def parse_requirement_lines(lines: Iterable[str]) -> set[str]:
    packages: set[str] = set()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r", "--requirement")):
            continue
        if line.startswith(("-e", "--editable", "--index-url", "--extra-index-url")):
            continue
        line = line.split("#", 1)[0].strip()
        line = line.split(";", 1)[0].strip()
        match = REQ_NAME_RE.match(line)
        if not match:
            continue
        packages.add(normalize_name(match.group(1)))
    return packages


def read_requirements_files() -> set[str]:
    packages: set[str] = set()
    for req_file in sorted(ROOT.glob("requirements*.txt")):
        packages.update(
            parse_requirement_lines(req_file.read_text(encoding="utf-8").splitlines())
        )
    return packages


def read_pyproject_dependencies() -> set[str]:
    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        return set()

    try:
        import tomllib
    except ModuleNotFoundError:
        return set()

    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project") or {}
    deps = project.get("dependencies") or []
    return parse_requirement_lines(deps)


def get_dependency_names() -> set[str]:
    deps = set()
    deps.update(read_requirements_files())
    deps.update(read_pyproject_dependencies())
    return deps


def metadata_field(meta: metadata.PackageMetadata, key: str) -> str:
    return meta[key].strip() if key in meta else ""


def build_installed_index() -> dict[str, metadata.Distribution]:
    idx: dict[str, metadata.Distribution] = {}
    for dist in metadata.distributions():
        name = metadata_field(dist.metadata, "Name")
        if not name:
            continue
        idx[normalize_name(name)] = dist
    return idx


def license_text_for_dist(dist: metadata.Distribution) -> str:
    parts = []
    license_field = metadata_field(dist.metadata, "License")
    if license_field:
        parts.append(license_field)
    for classifier in dist.metadata.get_all("Classifier") or []:
        if classifier.startswith("License ::"):
            parts.append(classifier)
    return " | ".join(parts)


def check_for_gpl() -> tuple[list[Finding], list[str]]:
    dependencies = get_dependency_names()
    if not dependencies:
        print(
            "No requirements*.txt or pyproject.toml dependencies found; skipping GPL dependency check."
        )
        return [], []

    installed = build_installed_index()
    findings: list[Finding] = []
    missing: list[str] = []

    for dep in sorted(dependencies):
        dist = installed.get(dep)
        if dist is None:
            missing.append(dep)
            continue
        details = license_text_for_dist(dist)
        if details and GPL_RE.search(details):
            findings.append(Finding(package=dep, detail=details))

    return findings, missing


def main() -> int:
    findings, missing = check_for_gpl()
    if missing:
        print(
            "Warning: dependencies not installed for license inspection:",
            ", ".join(missing),
        )

    if findings:
        print("GPL-family licenses detected:")
        for finding in findings:
            print(f"  - {finding.package}: {finding.detail}")
        print("Remove or replace GPL-family dependencies to pass policy.")
        return 1

    print("GPL dependency license check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
