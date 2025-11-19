#!/usr/bin/env python3
"""
Generate API documentation markdown files from Python modules.

This script scans the launchsampler package and automatically creates
markdown files with mkdocstrings directives for each module.
"""

from pathlib import Path
from typing import Dict, List, Any
import yaml


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


def get_package_title(package_name: str) -> str:
    """Convert package name to human-readable title."""
    # Special case mappings for better readability
    title_map = {
        "model_manager": "Model Manager",
        "led_ui": "LED UI",
        "set_manager_service": "Set Manager Service",
    }

    if package_name in title_map:
        return title_map[package_name]

    # Default: capitalize first letter
    return package_name.capitalize()


def generate_nav_structure(docs_root: Path, packages_to_document: Dict[str, str]) -> str:
    """
    Generate navigation structure for mkdocs.yml using PyYAML.

    This ensures proper YAML formatting with quotes where needed.
    """
    # Build the navigation structure as a Python data structure
    api_reference_items = []

    for package_name in packages_to_document.keys():
        package_dir = docs_root / package_name
        if not package_dir.exists():
            continue

        # Add package section
        title = get_package_title(package_name)
        package_items = [
            {"Overview": f"api/{package_name}/index.md"}
        ]

        # Find all markdown files except index
        md_files = sorted(
            [f for f in package_dir.rglob("*.md") if f.name != "index.md"]
        )

        for md_file in md_files:
            rel_path = md_file.relative_to(docs_root)
            file_title = create_title_from_filename(md_file.name)

            # Handle nested structure (like adapters/, screens/, services/, widgets/)
            if md_file.parent != package_dir:
                subdir = md_file.parent.name.capitalize()
                file_title = f"{subdir}: {file_title}"

            package_items.append({file_title: f"api/{rel_path.as_posix()}"})

        api_reference_items.append({title: package_items})

    # Create the full API Reference structure
    api_reference = [{"API Reference": api_reference_items}]

    # Convert to YAML with proper indentation (2 spaces)
    yaml_output = yaml.dump(
        api_reference,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=1000  # Avoid line wrapping
    )

    # Add proper indentation for mkdocs.yml (starts at 2 spaces)
    lines = yaml_output.strip().split('\n')
    indented_lines = ['  ' + line for line in lines]

    return '\n'.join(indented_lines)


def update_mkdocs_nav(mkdocs_path: Path, new_api_nav: str) -> None:
    """
    Update the API Reference section in mkdocs.yml.

    Args:
        mkdocs_path: Path to mkdocs.yml
        new_api_nav: New API Reference navigation structure
    """
    import re

    # Read current mkdocs.yml
    content = mkdocs_path.read_text(encoding="utf-8")

    # Pattern to match the API Reference section
    # Matches from "  - API Reference:" to the line before the next top-level section
    pattern = r"(  - API Reference:.*?)(\n  - [A-Z])"

    # Replace the API Reference section
    replacement = new_api_nav + r"\2"
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # Write back
    mkdocs_path.write_text(new_content, encoding="utf-8")


def cleanup_old_docs(docs_root: Path, packages_to_document: Dict[str, str]) -> None:
    """
    Clean up old documentation files for packages being regenerated.

    This ensures that if Python files are moved or deleted, their corresponding
    markdown files are also removed.

    Args:
        docs_root: Root directory for API documentation
        packages_to_document: Dictionary of packages to clean
    """
    print("\nCleaning up old documentation files...")

    for package_name in packages_to_document.keys():
        package_dir = docs_root / package_name
        if package_dir.exists():
            # Remove all markdown files except index.md (we'll regenerate it)
            for md_file in package_dir.rglob("*.md"):
                if md_file.name != "index.md":
                    md_file.unlink()
                    print(f"  Removed: {md_file.relative_to(docs_root.parent.parent)}")

            # Remove empty subdirectories
            for subdir in sorted(package_dir.rglob("*"), reverse=True):
                if subdir.is_dir() and not any(subdir.iterdir()):
                    subdir.rmdir()
                    print(f"  Removed empty dir: {subdir.relative_to(docs_root.parent.parent)}")


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
        "audio": "Low-level audio primitives and sample loading",
        "midi": "MIDI input/output management",
        "devices": "MIDI device interface and hardware adapters",
        "tui": "Terminal user interface",
        "led_ui": "Hardware LED grid user interface support",
        "services": "Business logic services",
        "model_manager": "Generic model management framework for Pydantic models",
        "models": "Pydantic data models for configuration and state",
        "utils": "Utility functions and helper classes",
    }

    print("Generating API documentation...")

    # Clean up old documentation files first
    cleanup_old_docs(docs_root, packages_to_document)

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

        # Use the same title function for consistency
        title = get_package_title(package_name)
        content = f"# {title}\n\n{description}\n\n"
        # Disable root heading since we provide a nice title already
        content += f"::: launchsampler.{package_name}\n"
        content += "    options:\n"
        content += "      show_root_heading: false\n"

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

    # Update mkdocs.yml automatically
    print("\nUpdating mkdocs.yml...")
    mkdocs_file = project_root / "mkdocs.yml"
    update_mkdocs_nav(mkdocs_file, nav_structure)
    print(f"Updated API Reference section in mkdocs.yml")

    print("\nRun 'uv run mkdocs serve' to preview the documentation.")


if __name__ == "__main__":
    main()
