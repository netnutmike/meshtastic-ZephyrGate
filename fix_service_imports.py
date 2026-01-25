#!/usr/bin/env python3
"""
Script to fix import statements in service files
"""

import re
from pathlib import Path

def fix_imports_in_file(filepath):
    """Fix relative imports in a file"""
    try:
        content = filepath.read_text()
        original_content = content
        
        # Pattern 1: from ..models.message import X
        # Replace with try/except block
        pattern1 = r'from \.\.models\.message import (.+?)(?=\n)'
        
        def replacement1(match):
            imports = match.group(1)
            return f'''try:
    from ..models.message import {imports}
except ImportError:
    from models.message import {imports}'''
        
        content = re.sub(pattern1, replacement1, content)
        
        # Pattern 2: from ...models.message import X (three dots)
        pattern2 = r'from \.\.\.models\.message import (.+?)(?=\n)'
        
        def replacement2(match):
            imports = match.group(1)
            return f'''try:
    from ...models.message import {imports}
except ImportError:
    from models.message import {imports}'''
        
        content = re.sub(pattern2, replacement2, content)
        
        # Pattern 3: Multi-line imports from ..models.message
        pattern3 = r'from \.\.models\.message import \(\s*\n((?:.*\n)*?)\)'
        
        def replacement3(match):
            imports = match.group(1).strip()
            return f'''try:
    from ..models.message import (
{imports}
    )
except ImportError:
    from models.message import (
{imports}
    )'''
        
        content = re.sub(pattern3, replacement3, content)
        
        # Pattern 4: Multi-line imports from ...models.message
        pattern4 = r'from \.\.\.models\.message import \(\s*\n((?:.*\n)*?)\)'
        
        def replacement4(match):
            imports = match.group(1).strip()
            return f'''try:
    from ...models.message import (
{imports}
    )
except ImportError:
    from models.message import (
{imports}
    )'''
        
        content = re.sub(pattern4, replacement4, content)
        
        if content != original_content:
            filepath.write_text(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

def main():
    """Fix imports in all service files"""
    services_dir = Path("src/services")
    
    if not services_dir.exists():
        print(f"Services directory not found: {services_dir}")
        return
    
    fixed_count = 0
    checked_count = 0
    
    # Find all Python files in services
    for py_file in services_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        
        checked_count += 1
        if fix_imports_in_file(py_file):
            print(f"✓ Fixed: {py_file}")
            fixed_count += 1
        else:
            print(f"  Skipped: {py_file}")
    
    print(f"\nSummary:")
    print(f"  Checked: {checked_count} files")
    print(f"  Fixed: {fixed_count} files")

if __name__ == "__main__":
    main()
