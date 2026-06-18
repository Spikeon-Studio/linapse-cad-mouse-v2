import re
from pathlib import Path

def test_userscript_metadata_headers():
    """
    Verify linapse-browser-connector.user.js has correct @match patterns.
    """
    script_path = Path(__file__).parent / "linapse-browser-connector.user.js"
    assert script_path.exists(), f"Userscript file not found at {script_path}"

    content = script_path.read_text()
    
    # Extract UserScript block
    match = re.search(r"// ==UserScript==\n(.*?)\n// ==/UserScript==\n", content, re.DOTALL)
    assert match is not None, "UserScript metadata block not found"
    
    metadata_lines = match.group(1).splitlines()
    
    # Extract all @match directives
    match_patterns = []
    for line in metadata_lines:
        line = line.strip()
        if line.startswith("// @match"):
            parts = line.split()
            if len(parts) >= 3:
                match_patterns.append(parts[2])
            elif len(parts) == 2:
                # In case no spaces between @match and pattern, check standard format
                pass

    expected_patterns = [
        "https://cad.onshape.com/*",
        "https://*.sketchup.com/*",
        "https://sketchup.com/*"
    ]
    
    # Ensure all expected patterns are matched
    for expected in expected_patterns:
        assert expected in match_patterns, f"Missing expected @match pattern: {expected}"
        
    # Ensure no extra unexpected match patterns
    assert len(match_patterns) == len(expected_patterns), f"Found unexpected @match patterns: {set(match_patterns) - set(expected_patterns)}"
