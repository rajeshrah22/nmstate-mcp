#!/usr/bin/env python3
"""
Setup script for nmstate-mcp with Cursor
Automatically configures the MCP server in Cursor's mcp.json
"""

import json
import os
import sys
import subprocess
import shutil
from pathlib import Path

def print_step(step_num, total_steps, message):
    """Print a formatted step message"""
    print(f"[{step_num}/{total_steps}] {message}")

def print_success(message):
    """Print a success message"""
    print(f"SUCCESS: {message}")

def print_error(message):
    """Print an error message"""
    print(f"ERROR: {message}")

def print_info(message):
    """Print an info message"""
    print(f"INFO: {message}")

def cleanup_on_failure(created_files, created_dirs):
    """Clean up created files and directories on failure"""
    print_info("Cleaning up created files...")
    
    for file_path in created_files:
        if os.path.exists(file_path):
            os.unlink(file_path)
            print_info(f"Removed file: {file_path}")
    
    for dir_path in created_dirs:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            print_info(f"Removed directory: {dir_path}")

def check_dependencies():
    """Check for missing dependencies"""
    missing_deps = []
    
    if shutil.which("uv") is None:
        missing_deps.append("uv")
    
    if shutil.which("ansible") is None:
        missing_deps.append("ansible")
    
    if not missing_deps:
        print_success("All dependencies are available")
        return True
    
    print_info(f"Missing dependencies: {', '.join(missing_deps)}")
    print_info("Please install missing dependencies:")
    
    for dep in missing_deps:
        if dep == "uv":
            print_info("  - uv: Download the installer script using 'curl -O https://astral.sh/uv/install.sh', verify its integrity, and then execute it manually (or use your package manager).")
        elif dep == "ansible":
            print_info("  - ansible: pip install ansible  (or use your package manager)")
    
    print_info("You can continue setup without these dependencies, but some features may not work")
    return False

def create_mcp_json():
    """Create or update ~/.cursor/mcp.json"""
    cursor_dir = Path.home() / ".cursor"
    mcp_json_path = cursor_dir / "mcp.json"
    
    cursor_dir.mkdir(exist_ok=True)
    
    if mcp_json_path.exists():
        with open(mcp_json_path, 'r') as f:
            config = json.load(f)
    else:
        config = {"mcpServers": {}}
    
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    if "nmstate-mcp" in config["mcpServers"]:
        print_info("nmstate-mcp entry already exists in mcp.json, skipping")
        return True, mcp_json_path
    
    nmstate_mcp_dir = Path(__file__).parent.absolute()
    config["mcpServers"]["nmstate-mcp"] = {
        "command": "uv",
        "args": [
            "run",
            "--directory",
            str(nmstate_mcp_dir),
            "main.py"
        ]
    }
    
    with open(mcp_json_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    return True, mcp_json_path

def create_nmstate_mcp_directory():
    """Create ~/.nmstate-mcp directory structure"""
    nmstate_dir = Path.home() / ".nmstate-mcp"
    
    try:
        nmstate_dir.mkdir(exist_ok=True)
        
        (nmstate_dir / "playbooks").mkdir(exist_ok=True)
        (nmstate_dir / "vars").mkdir(exist_ok=True)
        
        inventory_file = nmstate_dir / "inventory.yaml"
        if not inventory_file.exists():
            with open(inventory_file, 'w') as f:
                f.write(
                    "# inventory.yaml\n"
                    "# This file is used to define the inventory for nmstate-mcp.\n"
                    "# Add your hosts and groups below in YAML format.\n\n"
                    "# Example structure:\n"
                    "# all:\n"
                    "#   hosts:\n"
                    "#     localhost:\n"
                    "#       ansible_connection: local\n"
                )
        
        return True, nmstate_dir
        
    except PermissionError:
        print_error(f"Permission denied creating directory: {nmstate_dir}")
        return False, None
    except Exception as e:
        print_error(f"Failed to create directory {nmstate_dir}: {e}")
        return False, None

def main():
    print("nmstate-mcp Setup for Cursor")
    print("=" * 40)
    
    created_files = []
    created_dirs = []
    
    try:
        # Step 1: Check dependencies
        print_step(1, 4, "Checking dependencies...")
        deps_available = check_dependencies()
        if not deps_available:
            print_info("Continuing setup without all dependencies...")
        
        # Step 2: Create ~/.nmstate-mcp directory
        print_step(2, 4, "Creating ~/.nmstate-mcp directory...")
        success, nmstate_dir = create_nmstate_mcp_directory()
        if not success:
            cleanup_on_failure(created_files, created_dirs)
            sys.exit(1)
        
        if nmstate_dir:
            created_dirs.append(str(nmstate_dir))
        
        print_success(f"Created directory: {nmstate_dir}")
        print_success(f"Created subdirectories: playbooks, vars")
        print_success(f"Created empty inventory file: {nmstate_dir}/inventory.yaml")
        
        # Step 3: Create/update mcp.json
        print_step(3, 4, "Configuring Cursor mcp.json...")
        success, mcp_json_path = create_mcp_json()
        if not success:
            cleanup_on_failure(created_files, created_dirs)
            sys.exit(1)
        
        print_success(f"Updated configuration: {mcp_json_path}")
        
        # Step 4: Final summary
        print_step(4, 4, "Setup complete!")
        print()
        print("Configuration Summary:")
        print(f"  - MCP config: {mcp_json_path}")
        print(f"  - nmstate directory: {nmstate_dir}")
        print(f"  - Inventory file: {nmstate_dir}/inventory.yaml")
        print(f"  - Playbooks directory: {nmstate_dir}/playbooks")
        print(f"  - Variables directory: {nmstate_dir}/vars")
        print()
        print("Next steps:")
        print("1. Configure your hosts in ~/.nmstate-mcp/inventory.yaml")
        print("2. Restart Cursor to load the new MCP server")
        print("3. Use the nmstate-mcp tools in Cursor")
        
        if not deps_available:
            print()
            print("NOTE: Some dependencies are missing. Install them for full functionality.")
        
    except KeyboardInterrupt:
        print_error("Setup interrupted by user")
        cleanup_on_failure(created_files, created_dirs)
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        cleanup_on_failure(created_files, created_dirs)
        sys.exit(1)

if __name__ == "__main__":
    main() 
