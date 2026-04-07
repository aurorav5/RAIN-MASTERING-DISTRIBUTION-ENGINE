#!/usr/bin/env python3
"""
RAIN AI Mastering Engine - Test Protocol Runner
===============================================

Runs all test protocols and generates a comprehensive report.
"""

import subprocess
import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Test configuration
TEST_SUITES = {
    "backend": {
        "path": "backend/test_protocol.py",
        "description": "Backend API and security tests",
        "framework": "pytest",
    },
    "security": {
        "path": "security/test_protocol.py", 
        "description": "Security vulnerability tests",
        "framework": "pytest",
    },
    "performance": {
        "path": "performance/test_protocol.py",
        "description": "Performance and load tests",
        "framework": "pytest",
    },
}

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}\n")


def print_section(text: str):
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'-'*70}{Colors.ENDC}\n")


def run_test_suite(name: str, config: dict) -> dict:
    """Run a test suite and return results."""
    print_section(f"Running {name.upper()} Tests")
    
    path = config["path"]
    framework = config["framework"]
    
    if not os.path.exists(path):
        print(f"{Colors.WARNING}⚠ Test file not found: {path}{Colors.ENDC}")
        return {"status": "skipped", "reason": "file not found"}
    
    try:
        if framework == "pytest":
            # Run pytest with verbose output and JSON report
            result = subprocess.run(
                ["python", "-m", "pytest", path, "-v", "--tb=short", "-x"],
                capture_output=True,
                text=True,
                timeout=300
            )
        else:
            result = subprocess.run(
                ["python", path],
                capture_output=True,
                text=True,
                timeout=300
            )
        
        # Parse results
        passed = result.returncode == 0
        output = result.stdout + result.stderr
        
        # Count tests
        import re
        test_count = len(re.findall(r'PASSED|FAILED|ERROR', output))
        passed_count = len(re.findall(r'PASSED', output))
        failed_count = len(re.findall(r'FAILED', output))
        error_count = len(re.findall(r'ERROR', output))
        
        print(output)
        
        if passed:
            print(f"{Colors.OKGREEN}✓ {name.upper()} tests passed ({passed_count}/{test_count}){Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}✗ {name.upper()} tests failed ({failed_count} failed, {error_count} errors){Colors.ENDC}")
        
        return {
            "status": "passed" if passed else "failed",
            "total": test_count,
            "passed": passed_count,
            "failed": failed_count,
            "errors": error_count,
            "output": output,
        }
        
    except subprocess.TimeoutExpired:
        print(f"{Colors.FAIL}✗ {name.upper()} tests timed out{Colors.ENDC}")
        return {"status": "timeout", "reason": "test execution exceeded 5 minutes"}
    except Exception as e:
        print(f"{Colors.FAIL}✗ {name.upper()} tests error: {e}{Colors.ENDC}")
        return {"status": "error", "reason": str(e)}


def generate_report(results: dict) -> str:
    """Generate a comprehensive test report."""
    report = []
    report.append("# RAIN AI Mastering Engine - Test Protocol Report")
    report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"\n---\n")
    
    # Summary
    total_tests = sum(r.get("total", 0) for r in results.values() if isinstance(r, dict))
    total_passed = sum(r.get("passed", 0) for r in results.values() if isinstance(r, dict))
    total_failed = sum(r.get("failed", 0) for r in results.values() if isinstance(r, dict))
    total_errors = sum(r.get("errors", 0) for r in results.values() if isinstance(r, dict))
    
    report.append("## Summary\n")
    report.append(f"| Metric | Value |")
    report.append(f"|--------|-------|")
    report.append(f"| Total Tests | {total_tests} |")
    report.append(f"| Passed | {total_passed} |")
    report.append(f"| Failed | {total_failed} |")
    report.append(f"| Errors | {total_errors} |")
    report.append(f"| Success Rate | {(total_passed/max(total_tests,1)*100):.1f}% |")
    report.append("")
    
    # Detailed results
    report.append("## Detailed Results\n")
    for suite_name, result in results.items():
        report.append(f"### {suite_name.upper()}\n")
        
        if isinstance(result, dict):
            status = result.get("status", "unknown")
            status_emoji = "✅" if status == "passed" else "❌" if status in ["failed", "error", "timeout"] else "⚠️"
            
            report.append(f"**Status:** {status_emoji} {status.upper()}\n")
            
            if "total" in result:
                report.append(f"- Total: {result['total']}")
                report.append(f"- Passed: {result['passed']}")
                report.append(f"- Failed: {result['failed']}")
                report.append(f"- Errors: {result['errors']}")
            
            if "reason" in result:
                report.append(f"\n**Reason:** {result['reason']}")
        
        report.append("")
    
    # Recommendations
    report.append("## Recommendations\n")
    
    if total_failed > 0:
        report.append("- ⚠️ Address failing tests before production deployment")
    
    if total_errors > 0:
        report.append("- 🔧 Fix test errors (configuration/environment issues)")
    
    if total_passed / max(total_tests, 1) < 0.8:
        report.append("- 📊 Test coverage below 80% - add more tests")
    
    report.append("- 🔒 Run security tests regularly")
    report.append("- 📈 Monitor performance test trends")
    report.append("- 🔄 Integrate tests into CI/CD pipeline")
    
    return "\n".join(report)


def main():
    """Main test runner."""
    print_header("RAIN AI MASTERING ENGINE - TEST PROTOCOL RUNNER")
    
    print(f"{Colors.OKBLUE}Starting comprehensive test suite...{Colors.ENDC}\n")
    
    # Change to test directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Run all test suites
    results = {}
    
    for suite_name, config in TEST_SUITES.items():
        results[suite_name] = run_test_suite(suite_name, config)
    
    # Generate report
    print_header("TEST REPORT")
    
    report = generate_report(results)
    print(report)
    
    # Save report
    report_path = script_dir / "test_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    
    print(f"\n{Colors.OKGREEN}Report saved to: {report_path}{Colors.ENDC}\n")
    
    # Final summary
    total_passed = sum(r.get("passed", 0) for r in results.values() if isinstance(r, dict))
    total_tests = sum(r.get("total", 0) for r in results.values() if isinstance(r, dict))
    
    if total_tests > 0 and total_passed == total_tests:
        print(f"{Colors.OKGREEN}{Colors.BOLD}🎉 ALL TESTS PASSED!{Colors.ENDC}\n")
        return 0
    else:
        print(f"{Colors.WARNING}{Colors.BOLD}⚠ Some tests failed or were skipped{Colors.ENDC}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
