#!/usr/bin/env python3
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: update_badges.py <results_dir> [readme_path]")
        sys.exit(1)

    results_dir = Path(sys.argv[1])
    readme_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent.parent / "README.md"

    if not results_dir.is_dir():
        print(f"Error: {results_dir} is not a directory.")
        sys.exit(1)

    if not readme_path.is_file():
        print(f"Error: {readme_path} is not a file.")
        sys.exit(1)

    # Distros we expect to test
    distros = ["ubuntu", "debian", "fedora"]
    status_map = {}

    for distro in distros:
        status_file = results_dir / distro
        if status_file.is_file():
            val = status_file.read_text().strip().lower()
            if val in ("success", "passing"):
                status_map[distro] = ("passing", "success")
            elif val in ("failure", "failing"):
                status_map[distro] = ("failing", "critical")
            else:
                status_map[distro] = ("unknown", "inactive")
        else:
            status_map[distro] = ("unknown", "inactive")

    # Generate badges
    badge_parts = []
    for distro in distros:
        label = distro.capitalize()
        msg, color = status_map[distro]
        badge_url = f"https://img.shields.io/badge/{label}-{msg}-{color}"
        badge_parts.append(f"[![{label}]({badge_url})](#)")

    badge_line = " ".join(badge_parts)

    # Update README.md
    content = readme_path.read_text()
    start_tag = "<!-- DISTRO_BADGES_START -->"
    end_tag = "<!-- DISTRO_BADGES_END -->"

    if start_tag not in content or end_tag not in content:
        print("Error: Placeholders not found in README.md.")
        sys.exit(1)

    # We need to find the existing block and replace it
    start_idx = content.find(start_tag)
    end_idx = content.find(end_tag) + len(end_tag)
    
    new_content = content[:start_idx] + start_tag + "\n" + badge_line + "\n" + end_tag + content[end_idx:]

    readme_path.write_text(new_content)
    print("README.md updated with badges:")
    print(badge_line)

if __name__ == "__main__":
    main()
