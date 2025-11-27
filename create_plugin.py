#!/usr/bin/env python3
"""
ZephyrGate Plugin Template Generator

This script generates a new plugin from a template with customizable options.
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime
import re


def validate_plugin_name(name: str) -> bool:
    """
    Validate plugin name (lowercase, alphanumeric, underscores only).
    
    Args:
        name: Plugin name to validate
        
    Returns:
        True if valid, False otherwise
    """
    return bool(re.match(r'^[a-z][a-z0-9_]*$', name))


def create_directory_structure(plugin_path: Path) -> None:
    """
    Create the plugin directory structure.
    
    Args:
        plugin_path: Path to the plugin directory
    """
    directories = [
        plugin_path,
        plugin_path / "handlers",
        plugin_path / "tasks",
        plugin_path / "utils",
        plugin_path / "tests",
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")


def render_template(template_content: str, variables: dict) -> str:
    """
    Render a template by replacing placeholders with values.
    
    Supports:
    - {{variable}} - Simple variable replacement
    - {{#if variable}}...{{/if}} - Conditional blocks (supports nesting)
    
    Args:
        template_content: Template string with placeholders
        variables: Dictionary of variable names to values
        
    Returns:
        Rendered template string
    """
    import re
    
    result = template_content
    
    # Process conditional blocks {{#if variable}}...{{/if}}
    # Process innermost conditionals first to handle nesting correctly
    def process_conditionals(text):
        max_iterations = 20  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            # Pattern to match {{#if variable}}content{{/if}} where content has NO nested {{#if}}
            # This ensures we process innermost conditionals first
            pattern = r'\{\{#if\s+(\w+)\}\}((?:(?!\{\{#if).)*?)\{\{/if\}\}'
            
            def replace_conditional(match):
                var_name = match.group(1)
                content = match.group(2)
                
                # Check if variable is truthy
                var_value = variables.get(var_name, "false")
                if var_value in ("true", True, "True", 1, "1"):
                    return content
                return ""
            
            new_text = re.sub(pattern, replace_conditional, text, flags=re.DOTALL)
            
            # If no changes were made, we're done
            if new_text == text:
                break
            
            text = new_text
            iteration += 1
        
        return text
    
    # Process conditionals first
    result = process_conditionals(result)
    
    # Then replace simple variables
    for key, value in variables.items():
        placeholder = f"{{{{{key}}}}}"
        result = result.replace(placeholder, str(value))
    
    return result


def generate_plugin_files(plugin_path: Path, options: dict) -> None:
    """
    Generate plugin files from templates.
    
    Args:
        plugin_path: Path to the plugin directory
        options: Dictionary of plugin options
    """
    template_dir = Path(__file__).parent / "plugin_template"
    
    # Prepare template variables
    variables = {
        "plugin_name": options["name"],
        "plugin_class": options["class_name"],
        "plugin_description": options["description"],
        "plugin_author": options["author"],
        "plugin_email": options["email"],
        "plugin_version": options["version"],
        "plugin_license": options["license"],
        "current_year": datetime.now().year,
        "has_commands": "true" if options["features"]["commands"] else "false",
        "has_scheduled_tasks": "true" if options["features"]["scheduled_tasks"] else "false",
        "has_menu_items": "true" if options["features"]["menu_items"] else "false",
        "has_http": "true" if options["features"]["http"] else "false",
        "has_storage": "true" if options["features"]["storage"] else "false",
    }
    
    # Generate files from templates
    files_to_generate = [
        ("__init__.py.template", plugin_path / "__init__.py"),
        ("plugin.py.template", plugin_path / "plugin.py"),
        ("manifest.yaml.template", plugin_path / "manifest.yaml"),
        ("config_schema.json.template", plugin_path / "config_schema.json"),
        ("README.md.template", plugin_path / "README.md"),
        ("requirements.txt.template", plugin_path / "requirements.txt"),
        ("handlers/__init__.py.template", plugin_path / "handlers" / "__init__.py"),
        ("tasks/__init__.py.template", plugin_path / "tasks" / "__init__.py"),
        ("utils/__init__.py.template", plugin_path / "utils" / "__init__.py"),
        ("tests/__init__.py.template", plugin_path / "tests" / "__init__.py"),
        ("tests/test_plugin.py.template", plugin_path / "tests" / "test_plugin.py"),
    ]
    
    # Add optional files based on features
    if options["features"]["commands"]:
        files_to_generate.append(
            ("handlers/commands.py.template", plugin_path / "handlers" / "commands.py")
        )
    
    if options["features"]["scheduled_tasks"]:
        files_to_generate.append(
            ("tasks/scheduled.py.template", plugin_path / "tasks" / "scheduled.py")
        )
    
    for template_file, output_file in files_to_generate:
        template_path = template_dir / template_file
        
        if template_path.exists():
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            rendered_content = render_template(template_content, variables)
            
            with open(output_file, 'w') as f:
                f.write(rendered_content)
            
            print(f"Generated file: {output_file}")
        else:
            # Generate minimal file if template doesn't exist
            if output_file.name == "__init__.py":
                with open(output_file, 'w') as f:
                    f.write(f'"""Plugin: {options["name"]}"""\n')
                print(f"Generated minimal file: {output_file}")


def main():
    """Main entry point for the plugin generator."""
    parser = argparse.ArgumentParser(
        description="Generate a new ZephyrGate plugin from template",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a basic plugin
  python create_plugin.py my_plugin --author "John Doe"
  
  # Generate a plugin with specific features
  python create_plugin.py weather_bot --author "Jane Smith" \\
    --commands --scheduled-tasks --http
  
  # Generate a plugin with all features
  python create_plugin.py full_featured --author "Dev Team" \\
    --commands --scheduled-tasks --menu-items --http --storage
  
  # Specify output directory
  python create_plugin.py my_plugin --author "John Doe" --output /path/to/plugins
        """
    )
    
    parser.add_argument(
        "name",
        help="Plugin name (lowercase, alphanumeric, underscores only)"
    )
    
    parser.add_argument(
        "--author",
        required=True,
        help="Plugin author name"
    )
    
    parser.add_argument(
        "--email",
        default="",
        help="Plugin author email"
    )
    
    parser.add_argument(
        "--description",
        default="",
        help="Plugin description"
    )
    
    parser.add_argument(
        "--version",
        default="1.0.0",
        help="Plugin version (default: 1.0.0)"
    )
    
    parser.add_argument(
        "--license",
        default="MIT",
        help="Plugin license (default: MIT)"
    )
    
    parser.add_argument(
        "--output",
        default="plugins",
        help="Output directory for plugin (default: plugins)"
    )
    
    # Feature flags
    parser.add_argument(
        "--commands",
        action="store_true",
        help="Include command handler support"
    )
    
    parser.add_argument(
        "--scheduled-tasks",
        action="store_true",
        help="Include scheduled task support"
    )
    
    parser.add_argument(
        "--menu-items",
        action="store_true",
        help="Include BBS menu integration"
    )
    
    parser.add_argument(
        "--http",
        action="store_true",
        help="Include HTTP client utilities"
    )
    
    parser.add_argument(
        "--storage",
        action="store_true",
        help="Include data storage support"
    )
    
    parser.add_argument(
        "--all-features",
        action="store_true",
        help="Include all available features"
    )
    
    args = parser.parse_args()
    
    # Validate plugin name
    if not validate_plugin_name(args.name):
        print(f"Error: Invalid plugin name '{args.name}'", file=sys.stderr)
        print("Plugin name must be lowercase, start with a letter, and contain only letters, numbers, and underscores", file=sys.stderr)
        sys.exit(1)
    
    # Set default description if not provided
    description = args.description or f"A ZephyrGate plugin: {args.name}"
    
    # Generate class name from plugin name
    class_name = "".join(word.capitalize() for word in args.name.split("_")) + "Plugin"
    
    # Determine features
    features = {
        "commands": args.commands or args.all_features,
        "scheduled_tasks": args.scheduled_tasks or args.all_features,
        "menu_items": args.menu_items or args.all_features,
        "http": args.http or args.all_features,
        "storage": args.storage or args.all_features,
    }
    
    # Prepare options
    options = {
        "name": args.name,
        "class_name": class_name,
        "author": args.author,
        "email": args.email,
        "description": description,
        "version": args.version,
        "license": args.license,
        "features": features,
    }
    
    # Create plugin directory
    output_dir = Path(args.output)
    plugin_path = output_dir / args.name
    
    if plugin_path.exists():
        print(f"Error: Plugin directory already exists: {plugin_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Generating plugin: {args.name}")
    print(f"Output directory: {plugin_path}")
    print(f"Author: {args.author}")
    print(f"Features: {', '.join(k for k, v in features.items() if v) or 'none'}")
    print()
    
    # Create directory structure
    create_directory_structure(plugin_path)
    
    # Generate plugin files
    generate_plugin_files(plugin_path, options)
    
    print()
    print("=" * 60)
    print("Plugin generated successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print(f"1. Review and customize the generated files in: {plugin_path}")
    print(f"2. Edit {plugin_path}/manifest.yaml to configure dependencies and permissions")
    print(f"3. Implement your plugin logic in {plugin_path}/plugin.py")
    print(f"4. Add the plugin directory to your ZephyrGate plugins path")
    print(f"5. Enable the plugin in your config.yaml")
    print()
    print("For more information, see docs/PLUGIN_DEVELOPMENT.md")


if __name__ == "__main__":
    main()
