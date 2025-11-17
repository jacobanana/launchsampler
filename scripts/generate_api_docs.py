#!/usr/bin/env python3
"""
Generate API documentation markdown files from Python modules.

This script scans the launchsampler package and automatically creates
markdown files with mkdocstrings directives for each module.
"""

from pathlib import Path
from typing import Dict, List


def get_module_path(file_path: Path, src_root: Path) -> str:
    """Convert a file path to a Python module path."""
    relative = file_path.relative_to(src_root)
    parts = list(relative.parts[:-1]) + [relative.stem]
    return ".".join(parts)


def generate_doc_content(module_path: str, title: str, description: str = "") -> str:
    """Generate markdown content for a module."""
    content = f"# {title}\n\n"
    if description:
        content += f"{description}\n\n"
    content += f"::: {module_path}\n"
    return content


def scan_package(
    package_path: Path, src_root: Path, exclude_patterns: List[str] = None
) -> Dict[str, str]:
    """
    Scan a package and return a mapping of doc paths to module paths.

    Args:
        package_path: Path to the package directory
        src_root: Root source directory
        exclude_patterns: List of patterns to exclude

    Returns:
        Dict mapping documentation file paths to module paths
    """
    exclude_patterns = exclude_patterns or ["__pycache__", "*.pyc", "__main__.py"]
    docs = {}

    for py_file in package_path.rglob("*.py"):
        # Skip excluded patterns
        if any(py_file.match(pattern) for pattern in exclude_patterns):
            continue

        # Skip __init__.py files for now (could be included if desired)
        if py_file.name == "__init__.py":
            continue

        module_path = get_module_path(py_file, src_root)

        # Generate doc file path
        rel_path = py_file.relative_to(package_path)
        doc_path = rel_path.with_suffix(".md")

        docs[str(doc_path)] = module_path

    return docs


def create_title_from_filename(filename: str) -> str:
    """Convert a filename to a human-readable title."""
    name = Path(filename).stem
    # Convert snake_case to Title Case
    return " ".join(word.capitalize() for word in name.split("_"))


def generate_nav_structure(docs_root: Path, packages_to_document: Dict[str, str]) -> str:
    """Generate navigation structure for mkdocs.yml."""
    nav_lines = ["  - API Reference:"]

    for package_name in packages_to_document.keys():
        package_dir = docs_root / package_name
        if not package_dir.exists():
            continue

        # Add package section
        title = package_name.capitalize()
        nav_lines.append(f"      - {title}:")
        nav_lines.append(f"          - Overview: api/{package_name}/index.md")

        # Find all markdown files except index
        md_files = sorted(
            [f for f in package_dir.rglob("*.md") if f.name != "index.md"]
        )

        for md_file in md_files:
            rel_path = md_file.relative_to(docs_root)
            file_title = create_title_from_filename(md_file.name)

            # Handle nested structure (like adapters/)
            if md_file.parent != package_dir:
                subdir = md_file.parent.name.capitalize()
                file_title = f"{subdir}: {file_title}"

            nav_lines.append(f"          - {file_title}: api/{rel_path.as_posix()}")

    return "\n".join(nav_lines)


def main():
    """Generate all API documentation files."""
    # Paths
    project_root = Path(__file__).parent.parent
    src_root = project_root / "src"
    package_root = src_root / "launchsampler"
    docs_root = project_root / "docs" / "api"

    # Configuration: which packages to document
    packages_to_document = {
        "core": "Audio playback engine and state management",
        "models": "Pydantic data models for configuration and state",
        "devices": "MIDI device interface and hardware adapters",
        "audio": "Low-level audio primitives and sample loading",
        "midi": "MIDI input/output management",
        "services": "Business logic services",
        "utils": "Utility functions and helper classes",
    }

    print("Generating API documentation...")

    for package_name, description in packages_to_document.items():
        package_path = package_root / package_name
        if not package_path.exists():
            print(f"Warning: Package {package_name} not found at {package_path}")
            continue

        print(f"\nProcessing package: {package_name}")

        # Scan package
        docs = scan_package(package_path, src_root)

        # Create documentation files
        for doc_path, module_path in docs.items():
            full_doc_path = docs_root / package_name / doc_path
            full_doc_path.parent.mkdir(parents=True, exist_ok=True)

            title = create_title_from_filename(doc_path)
            content = generate_doc_content(module_path, title)

            full_doc_path.write_text(content, encoding="utf-8")
            print(f"  Created: {full_doc_path.relative_to(project_root)}")

    # Generate index files for each package
    print("\nGenerating package index files...")
    for package_name, description in packages_to_document.items():
        index_path = docs_root / package_name / "index.md"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        content = f"# {package_name.capitalize()}\n\n{description}\n\n"
        content += f"::: launchsampler.{package_name}\n"

        index_path.write_text(content, encoding="utf-8")
        print(f"  Created: {index_path.relative_to(project_root)}")

    print("\nAPI documentation generated successfully!")
    print(f"\nGenerated files in: {docs_root.relative_to(project_root)}")

    # Generate navigation structure
    print("\nGenerating navigation structure...")
    nav_structure = generate_nav_structure(docs_root, packages_to_document)
    nav_file = project_root / "docs" / "api_nav.yml"
    nav_file.write_text(nav_structure, encoding="utf-8")
    print(f"Navigation structure saved to: {nav_file.relative_to(project_root)}")
    print("\nYou can copy this navigation structure into your mkdocs.yml file.")
    print("\nRun 'uv run mkdocs serve' to preview the documentation.")


if __name__ == "__main__":
    main()
