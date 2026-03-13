#!/usr/bin/env python3
"""
Diagnose MCP server installation and find correct binary names
"""
import os
import subprocess
import sys

MCP_DIR = os.path.expanduser("~/.mcp-servers")

def find_binaries():
    """Find all MCP-related binaries in node_modules"""
    print("🔍 Searching for MCP binaries...")
    print(f"MCP_DIR: {MCP_DIR}")
    print()
    
    # Check node_modules/.bin/
    bin_dir = os.path.join(MCP_DIR, "node_modules", ".bin")
    if os.path.exists(bin_dir):
        print(f"📁 {bin_dir}:")
        binaries = os.listdir(bin_dir)
        for b in sorted(binaries):
            path = os.path.join(bin_dir, b)
            if os.path.isfile(path) or os.path.islink(path):
                print(f"   - {b}")
    else:
        print(f"❌ {bin_dir} not found")
    
    print()
    
    # Check each package's bin directory
    packages_dir = os.path.join(MCP_DIR, "node_modules")
    if os.path.exists(packages_dir):
        print(f"📦 Installed packages:")
        for pkg in sorted(os.listdir(packages_dir)):
            if pkg.startswith("."):
                continue
            pkg_path = os.path.join(packages_dir, pkg)
            if os.path.isdir(pkg_path):
                # Check package.json for bin field
                pkg_json = os.path.join(pkg_path, "package.json")
                if os.path.exists(pkg_json):
                    import json
                    try:
                        with open(pkg_json) as f:
                            data = json.load(f)
                        bin_field = data.get("bin", {})
                        if bin_field:
                            print(f"   📦 {pkg}:")
                            if isinstance(bin_field, str):
                                print(f"      → {bin_field}")
                            else:
                                for name, path in bin_field.items():
                                    print(f"      → {name}: {path}")
                    except:
                        print(f"   📦 {pkg} (no bin info)")
                else:
                    print(f"   📦 {pkg}")
    else:
        print(f"❌ {packages_dir} not found")

def test_npx():
    """Test if npx can run the MCP servers"""
    print()
    print("🧪 Testing npx commands...")
    
    test_packages = [
        ("mcp-server-fetch", ["--help"]),
        ("mcp-server-sqlite", ["--help"]),
        ("@modelcontextprotocol/server-filesystem", ["--help"]),
        ("@modelcontextprotocol/server-memory", ["--help"]),
    ]
    
    for pkg, args in test_packages:
        cmd = ["npx", "-y", pkg] + args
        print(f"   Testing: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=MCP_DIR if os.path.exists(MCP_DIR) else os.path.expanduser("~")
            )
            if result.returncode == 0 or "help" in result.stdout.lower() or "usage" in result.stderr.lower():
                print(f"   ✅ {pkg} works via npx")
            else:
                print(f"   ⚠️  {pkg} returned code {result.returncode}")
                if result.stderr:
                    print(f"      Error: {result.stderr[:100]}")
        except subprocess.TimeoutExpired:
            print(f"   ⏱️  {pkg} timed out (might be waiting for input)")
        except Exception as e:
            print(f"   ❌ {pkg} failed: {e}")

if __name__ == "__main__":
    find_binaries()
    test_npx()
    print()
    print("💡 Recommendations:")
    print("   If binaries are missing, reinstall with:")
    print("   cd ~/.mcp-servers && npm install mcp-server-fetch mcp-server-sqlite")
