#!/usr/bin/env python3
"""Smoke test for P0+P1 deployment verification.

This script performs quick sanity checks before production deployment.
Run: python3 smoke_test.py

Expected: All checks should pass (✅)
"""

import sys
import subprocess
from pathlib import Path


def check_modules():
    """Verify all P0+P1 modules can be imported."""
    print("\n📦 Checking module imports...")
    
    modules = [
        "app.services.markdown_validator",
        "app.services.visual_qa_service",
        "app.services.image_service",
        "app.services.design_validator",
        "app.services.template_validator",
        "app.services.design_qa",
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError as e:
            print(f"  ❌ {module}: {e}")
            return False
    
    return True


def check_dependencies():
    """Verify required Python packages."""
    print("\n📚 Checking Python dependencies...")
    
    packages = {
        "fastapi": "FastAPI framework",
        "pydantic": "Data validation",
        "markitdown": "PPTX text extraction",
        "PIL": "Image analysis",
        "python_pptx": "PPTX manipulation",
    }
    
    for package, description in packages.items():
        try:
            __import__(package)
            print(f"  ✅ {package:15} - {description}")
        except ImportError:
            print(f"  ❌ {package:15} - {description} NOT FOUND")
            return False
    
    return True


def check_system_tools():
    """Verify required system tools are available."""
    print("\n🔧 Checking system tools...")
    
    tools = {
        "soffice": "LibreOffice (PPTX→PDF conversion)",
        "pdftoppm": "Poppler (PDF→JPEG conversion)",
    }
    
    for tool, description in tools.items():
        try:
            result = subprocess.run(
                ["which", tool],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                path = result.stdout.strip()
                print(f"  ✅ {tool:10} - {description}")
                print(f"     Path: {path}")
            else:
                print(f"  ⚠️  {tool:10} - NOT FOUND (optional, verify if P0 Visual QA needed)")
        except Exception as e:
            print(f"  ⚠️  {tool:10} - Check failed: {e}")
    
    return True


def check_generate_endpoint():
    """Verify generate.py has P0+P1 imports."""
    print("\n🔌 Checking generate endpoint integration...")
    
    generate_py = Path("app/api/routes/generate.py")
    
    if not generate_py.exists():
        print(f"  ❌ {generate_py} not found")
        return False
    
    content = generate_py.read_text()
    
    required_imports = [
        ("MarkdownValidator", "P0: Content validation"),
        ("VisualQAService", "P0: Visual QA"),
        ("DesignValidator", "P1: Design rules"),
        ("TemplateValidator", "P1: Template validation"),
        ("DesignQAService", "P1: Design QA"),
    ]
    
    all_found = True
    for class_name, description in required_imports:
        if f"from app.services" in content and class_name in content:
            print(f"  ✅ {class_name:20} - {description}")
        else:
            print(f"  ❌ {class_name:20} - {description} NOT IMPORTED")
            all_found = False
    
    return all_found


def check_test_file():
    """Verify integration test file exists."""
    print("\n🧪 Checking test suite...")
    
    test_file = Path("tests/test_p0_p1_pipeline.py")
    
    if test_file.exists():
        print(f"  ✅ {test_file} exists")
        
        # Count test cases
        content = test_file.read_text()
        test_count = content.count("def test_")
        print(f"     Found {test_count} test cases")
        
        return True
    else:
        print(f"  ❌ {test_file} not found")
        return False


def check_dockerfile():
    """Verify Dockerfile has P0 system packages."""
    print("\n🐳 Checking Docker configuration...")
    
    dockerfile = Path("Dockerfile")
    
    if not dockerfile.exists():
        print(f"  ❌ {dockerfile} not found")
        return False
    
    content = dockerfile.read_text()
    
    packages = {
        "libreoffice": "PPTX→PDF conversion",
        "poppler-utils": "PDF→JPEG conversion",
    }
    
    all_found = True
    for package, description in packages.items():
        if package in content:
            print(f"  ✅ {package:15} - {description}")
        else:
            print(f"  ❌ {package:15} - {description} NOT IN DOCKERFILE")
            all_found = False
    
    return all_found


def check_requirements():
    """Verify requirements.txt has P0+P1 dependencies."""
    print("\n📋 Checking requirements.txt...")
    
    req_file = Path("requirements.txt")
    
    if not req_file.exists():
        print(f"  ❌ {req_file} not found")
        return False
    
    content = req_file.read_text()
    
    packages = {
        "markitdown": "Text extraction (P0)",
        "Pillow": "Image analysis (P0)",
    }
    
    all_found = True
    for package, description in packages.items():
        # Check both with and without version
        if package.lower() in content.lower():
            version = next((line for line in content.split('\n') if package.lower() in line.lower()), "")
            print(f"  ✅ {package:15} - {description}")
            print(f"     {version.strip()}")
        else:
            print(f"  ❌ {package:15} - {description} NOT FOUND")
            all_found = False
    
    return all_found


def main():
    """Run all checks."""
    print("=" * 70)
    print("🚀 P0+P1 DEPLOYMENT SMOKE TEST")
    print("=" * 70)
    
    checks = [
        ("Module Imports", check_modules),
        ("Dependencies", check_dependencies),
        ("System Tools", check_system_tools),
        ("Generate Endpoint", check_generate_endpoint),
        ("Test Suite", check_test_file),
        ("Dockerfile", check_dockerfile),
        ("Requirements", check_requirements),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"  ❌ Check failed with exception: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {name}")
    
    print("=" * 70)
    print(f"\nResult: {passed}/{total} checks passed")
    
    if passed == total:
        print("✨ All checks passed! Ready for deployment.")
        return 0
    else:
        print("⚠️  Some checks failed. Review above and fix before deployment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
