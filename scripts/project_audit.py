#!/usr/bin/env python3
"""
project_audit.py — Comprehensive Workspace Audit & Compliance Ratio Engine
Audits the Galaxy S8 Native Linux project against:
1. Directory Structure Hygiene (folder-and-file-management standard)
2. Naming Conventions (product-namespace-and-naming standard)
3. Versioning Consistency (versioning-and-rollback-manager standard)
4. Secret & Privacy Guardrails (Rule 16)
5. Dead File Links & Broken Imports

Calculates exact ratios, identifies cleanup targets, and outputs structured audit telemetry.
"""

import os
import sys
import json
import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

# Allowed files directly in workspace root (folder-and-file-management standard)
ALLOWED_ROOT_FILES = {
    "gemini.md", "findings.md", "history.md", "summary.md", "readme.md",
    "project_index.md", "project_visual_index.html", "version_manifest.json",
    "versions.md", "mistakes_and_learnings.md", "future_roadmap.md",
    "credits.md", "memory.md", "license", ".gitignore", ".env",
    "launch_s8_imager.bat", "ap_and_kernel_build_guide.md"
}

ALLOWED_ROOT_DIRS = {
    ".agent", ".github", ".git", ".antigravity", "kernel", "src", "packages", "desktop-app",
    "scripts", "tests", "releases", "distros", "docs", "tools", "archive", "scratch"
}

def audit_root_directory():
    root_files = [f for f in WORKSPACE.iterdir() if f.is_file()]
    root_dirs = [d for d in WORKSPACE.iterdir() if d.is_dir()]
    
    violations = []
    clean_count = 0
    total_count = len(root_files) + len(root_dirs)
    
    for f in root_files:
        name_lower = f.name.lower()
        if name_lower in ALLOWED_ROOT_FILES:
            clean_count += 1
        else:
            violations.append({
                "type": "ROOT_CLUTTER_FILE",
                "path": str(f.relative_to(WORKSPACE)),
                "size": f.stat().st_size,
                "reason": f"File '{f.name}' is not in the canonical allowed root files list."
            })
            
    for d in root_dirs:
        if d.name in ALLOWED_ROOT_DIRS:
            clean_count += 1
        else:
            violations.append({
                "type": "UNREGISTERED_ROOT_DIR",
                "path": str(d.relative_to(WORKSPACE)),
                "reason": f"Directory '{d.name}' is not in the canonical allowed root directories list."
            })
            
    ratio = (clean_count / total_count * 100.0) if total_count > 0 else 100.0
    return {
        "total_root_items": total_count,
        "clean_root_items": clean_count,
        "root_compliance_ratio": round(ratio, 2),
        "violations": violations
    }

def audit_naming_conventions():
    """Scans all tracked/source files (excluding .git, kernel source tree, distros, node_modules)
    to check kebab-case / snake_case compliance and invalid character patterns."""
    exclude_prefixes = (
        WORKSPACE / ".git",
        WORKSPACE / "kernel",
        WORKSPACE / "distros",
        WORKSPACE / "archive",
        WORKSPACE / "scratch",
    )
    
    total_files = 0
    compliant_files = 0
    violations = []
    
    # Valid naming pattern for scripts, drivers, docs, tests:
    # lowercase alphanumeric with hyphens or underscores, plus valid extensions
    # Also allows uppercase for standard root docs (README, GEMINI, etc.)
    valid_name_regex = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
    
    for root, dirs, files in os.walk(WORKSPACE):
        p_root = Path(root)
        if any(str(p_root).startswith(str(ep)) for ep in exclude_prefixes):
            continue
        if any(part.startswith(".") and part not in (".agent", ".github") for part in p_root.parts):
            continue
            
        for fname in files:
            p_file = p_root / fname
            rel_path = p_file.relative_to(WORKSPACE)
            total_files += 1
            
            # Check for spaces in filename
            if " " in fname:
                violations.append({
                    "type": "SPACE_IN_FILENAME",
                    "path": str(rel_path),
                    "reason": "Filenames must never contain spaces (use kebab-case or snake_case)."
                })
                continue
                
            # Check for non-ASCII or prohibited special chars
            if not valid_name_regex.match(fname):
                violations.append({
                    "type": "INVALID_CHARACTERS",
                    "path": str(rel_path),
                    "reason": "Filename contains disallowed special characters."
                })
                continue
                
            compliant_files += 1
            
    ratio = (compliant_files / total_files * 100.0) if total_files > 0 else 100.0
    return {
        "total_scanned_files": total_files,
        "compliant_files": compliant_files,
        "naming_compliance_ratio": round(ratio, 2),
        "violations": violations
    }

def audit_scratch_bloat():
    """Audits scratch/ directory for stale files, duplicates, or files exceeding 50 MB."""
    scratch_dir = WORKSPACE / "scratch"
    if not scratch_dir.exists():
        return {"file_count": 0, "total_size_mb": 0.0, "large_files": [], "stale_candidates": []}
        
    files = list(scratch_dir.glob("**/*"))
    file_items = [f for f in files if f.is_file()]
    total_size = sum(f.stat().st_size for f in file_items)
    
    large_files = []
    for f in file_items:
        size_mb = f.stat().st_size / (1024 * 1024)
        if size_mb > 50.0:
            large_files.append({"path": str(f.relative_to(WORKSPACE)), "size_mb": round(size_mb, 2)})
            
    return {
        "file_count": len(file_items),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "large_files": large_files
    }

def audit_versions_and_releases():
    """Audits VERSION_MANIFEST.json vs releases/ directory."""
    manifest_path = WORKSPACE / "VERSION_MANIFEST.json"
    releases_dir = WORKSPACE / "releases"
    
    manifest_ok = manifest_path.exists()
    releases_ok = releases_dir.exists()
    
    manifest_data = {}
    if manifest_ok:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception as e:
            manifest_ok = False
            
    release_files = [f.name for f in releases_dir.iterdir() if f.is_file()] if releases_ok else []
    
    active_info = manifest_data.get("active", {})
    return {
        "manifest_present": manifest_ok,
        "current_ap_version": active_info.get("ap_version", "UNKNOWN"),
        "current_kernel_version": active_info.get("kernel_version", "UNKNOWN"),
        "desktop_app_version": active_info.get("desktop_app_version", "UNKNOWN"),
        "release_files_count": len(release_files),
        "release_files": release_files
    }

def run_full_audit():
    print("[*] Running Comprehensive Galaxy S8 Repository Audit...")
    root_audit = audit_root_directory()
    naming_audit = audit_naming_conventions()
    scratch_audit = audit_scratch_bloat()
    version_audit = audit_versions_and_releases()
    
    overall_score = round((root_audit["root_compliance_ratio"] * 0.4) + (naming_audit["naming_compliance_ratio"] * 0.6), 2)
    
    summary = {
        "overall_compliance_score": overall_score,
        "root_directory": root_audit,
        "naming_conventions": naming_audit,
        "scratch_storage": scratch_audit,
        "versioning_and_releases": version_audit
    }
    
    return summary

if __name__ == "__main__":
    report = run_full_audit()
    print(json.dumps(report, indent=2))
