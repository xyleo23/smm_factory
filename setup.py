"""Setup script for SMM Factory."""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """Run a shell command and return success status."""
    print(f"\n{'='*60}")
    print(f"📦 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        print(f"✅ {description} - SUCCESS")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print(f"Error: {e.stderr}")
        return False


def main():
    """Run setup steps."""
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║                    SMM Factory Setup                       ║
    ║           UTM Injector & Multi-Platform Publishers        ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    project_root = Path(__file__).parent
    print(f"📁 Project root: {project_root}")
    
    steps = [
        ("pip install -r requirements.txt", "Installing Python dependencies"),
        ("playwright install chromium", "Installing Playwright Chromium browser"),
    ]
    
    success_count = 0
    for cmd, desc in steps:
        if run_command(cmd, desc):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"Setup completed: {success_count}/{len(steps)} steps successful")
    print(f"{'='*60}")
    
    if success_count == len(steps):
        print("\n✅ All dependencies installed successfully!")
        print("\n📝 Next steps:")
        print("1. Copy .env.example to .env")
        print("2. Fill in your credentials in .env")
        print("3. Run test_publishers.py to verify setup")
        print("4. Check example_usage.py for usage examples")
        return 0
    else:
        print("\n⚠️ Some steps failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
