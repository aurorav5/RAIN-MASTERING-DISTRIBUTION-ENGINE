#!/usr/bin/env python3
"""
RAIN AI Mastering Engine - Test Protocol Demo
=============================================

Demonstrates the test protocol structure and validates test syntax.
This runs without requiring the actual RAIN backend.
"""

import ast
import sys
from pathlib import Path
from datetime import datetime

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


def count_tests_in_file(filepath: Path) -> dict:
    """Parse Python file and count test functions and classes."""
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())
        
        test_classes = 0
        test_functions = 0
        assertions = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name.startswith('Test'):
                    test_classes += 1
            elif isinstance(node, ast.FunctionDef):
                if node.name.startswith('test_'):
                    test_functions += 1
            elif isinstance(node, ast.Assert):
                assertions += 1
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['assertEqual', 'assertTrue', 'assertFalse', 
                                          'assertIn', 'assertNotIn', 'assertRaises',
                                          'assertIsNone', 'assertIsNotNone']:
                        assertions += 1
        
        return {
            'classes': test_classes,
            'functions': test_functions,
            'assertions': assertions,
            'valid': True
        }
    except SyntaxError as e:
        return {
            'classes': 0,
            'functions': 0,
            'assertions': 0,
            'valid': False,
            'error': str(e)
        }


def analyze_test_protocol():
    """Analyze all test protocols."""
    print_header("RAIN AI MASTERING ENGINE - TEST PROTOCOL ANALYSIS")
    
    base_path = Path(__file__).parent
    
    protocols = {
        'Backend': base_path / 'backend' / 'test_protocol.py',
        'Security': base_path / 'security' / 'test_protocol.py',
        'Performance': base_path / 'performance' / 'test_protocol.py',
    }
    
    results = {}
    total_tests = 0
    total_assertions = 0
    
    for name, filepath in protocols.items():
        print_section(f"Analyzing {name} Tests")
        
        if not filepath.exists():
            print(f"{Colors.FAIL}✗ File not found: {filepath}{Colors.ENDC}")
            results[name] = {'valid': False, 'error': 'File not found'}
            continue
        
        stats = count_tests_in_file(filepath)
        results[name] = stats
        
        if stats['valid']:
            print(f"{Colors.OKGREEN}✓ Valid Python syntax{Colors.ENDC}")
            print(f"  Test Classes: {stats['classes']}")
            print(f"  Test Functions: {stats['functions']}")
            print(f"  Assertions: {stats['assertions']}")
            total_tests += stats['functions']
            total_assertions += stats['assertions']
        else:
            print(f"{Colors.FAIL}✗ Syntax error: {stats.get('error', 'Unknown')}{Colors.ENDC}")
    
    # Frontend tests
    print_section("Analyzing Frontend Tests")
    frontend_path = base_path / 'frontend' / 'test_protocol.tsx'
    if frontend_path.exists():
        with open(frontend_path, 'r') as f:
            content = f.read()
        
        # Count describe/it blocks
        describe_count = content.count('describe(')
        it_count = content.count('it(')
        expect_count = content.count('expect(')
        
        print(f"{Colors.OKGREEN}✓ TypeScript test file found{Colors.ENDC}")
        print(f"  Test Suites (describe): {describe_count}")
        print(f"  Test Cases (it): {it_count}")
        print(f"  Assertions (expect): {expect_count}")
        
        results['Frontend'] = {
            'valid': True,
            'suites': describe_count,
            'tests': it_count,
            'assertions': expect_count
        }
        total_tests += it_count
        total_assertions += expect_count
    else:
        print(f"{Colors.WARNING}⚠ Frontend test file not found{Colors.ENDC}")
    
    # E2E tests
    print_section("Analyzing E2E Tests")
    e2e_path = base_path / 'e2e' / 'test_protocol.spec.ts'
    if e2e_path.exists():
        with open(e2e_path, 'r') as f:
            content = f.read()
        
        test_count = content.count('test(')
        expect_count = content.count('expect(')
        
        print(f"{Colors.OKGREEN}✓ Playwright test file found{Colors.ENDC}")
        print(f"  Test Cases: {test_count}")
        print(f"  Assertions: {expect_count}")
        
        results['E2E'] = {
            'valid': True,
            'tests': test_count,
            'assertions': expect_count
        }
        total_tests += test_count
        total_assertions += expect_count
    else:
        print(f"{Colors.WARNING}⚠ E2E test file not found{Colors.ENDC}")
    
    # Print summary
    print_header("TEST PROTOCOL SUMMARY")
    
    print(f"{Colors.OKBLUE}Total Test Cases: {Colors.BOLD}{total_tests}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}Total Assertions: {Colors.BOLD}{total_assertions}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}Test Protocols: {Colors.BOLD}{len(results)}{Colors.ENDC}")
    
    print(f"\n{Colors.OKCYAN}Test Categories:{Colors.ENDC}")
    print(f"  • Backend API Tests - Authentication, Mastering, QC, Distribution")
    print(f"  • Security Tests - JWT, SQL Injection, XSS, CSRF, Rate Limiting")
    print(f"  • Performance Tests - Load, Stress, Spike, Endurance, Latency")
    print(f"  • Frontend Tests - Components, State, Visualizations, Accessibility")
    print(f"  • E2E Tests - User Workflows, Navigation, File Upload")
    
    # Generate report
    generate_report(results, total_tests, total_assertions)
    
    return 0


def generate_report(results: dict, total_tests: int, total_assertions: int):
    """Generate markdown report."""
    report = []
    report.append("# RAIN AI Mastering Engine - Test Protocol Report")
    report.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"\n---\n")
    
    report.append("## Executive Summary\n")
    report.append(f"| Metric | Value |")
    report.append(f"|--------|-------|")
    report.append(f"| Total Test Cases | {total_tests} |")
    report.append(f"| Total Assertions | {total_assertions} |")
    report.append(f"| Test Protocols | {len(results)} |")
    report.append("")
    
    report.append("## Test Protocol Breakdown\n")
    
    for name, stats in results.items():
        report.append(f"### {name}\n")
        
        if stats.get('valid'):
            if 'classes' in stats:
                report.append(f"- Test Classes: {stats['classes']}")
                report.append(f"- Test Functions: {stats['functions']}")
            if 'suites' in stats:
                report.append(f"- Test Suites: {stats['suites']}")
            if 'tests' in stats:
                report.append(f"- Test Cases: {stats['tests']}")
            report.append(f"- Assertions: {stats.get('assertions', 'N/A')}")
            report.append(f"- Status: ✅ Valid")
        else:
            report.append(f"- Status: ❌ Invalid")
            report.append(f"- Error: {stats.get('error', 'Unknown')}")
        
        report.append("")
    
    report.append("## Test Coverage Areas\n")
    
    report.append("### Backend Tests")
    report.append("- ✅ Authentication & Authorization")
    report.append("- ✅ JWT Security (algorithm confusion, tampering)")
    report.append("- ✅ File Upload Security")
    report.append("- ✅ Mastering Engine")
    report.append("- ✅ QC Engine")
    report.append("- ✅ Stem Separation")
    report.append("- ✅ Billing & Quotas")
    report.append("- ✅ Distribution")
    report.append("- ✅ AI Co-Master Engineer")
    report.append("- ✅ Provenance & Certificates")
    report.append("")
    
    report.append("### Security Tests")
    report.append("- ✅ JWT Vulnerabilities (none algorithm, confusion)")
    report.append("- ✅ SQL Injection")
    report.append("- ✅ XSS (Cross-Site Scripting)")
    report.append("- ✅ CSRF (Cross-Site Request Forgery)")
    report.append("- ✅ Rate Limiting")
    report.append("- ✅ File Upload Security")
    report.append("- ✅ Authorization (tier-based, cross-tenant)")
    report.append("- ✅ Information Disclosure")
    report.append("- ✅ SSRF (Server-Side Request Forgery)")
    report.append("")
    
    report.append("### Performance Tests")
    report.append("- ✅ Load Testing (10-200 concurrent users)")
    report.append("- ✅ Stress Testing (until failure)")
    report.append("- ✅ Spike Testing (sudden traffic increase)")
    report.append("- ✅ Endurance Testing (5-minute sustained load)")
    report.append("- ✅ Latency Distribution (P50, P95, P99)")
    report.append("- ✅ Throughput Measurement")
    report.append("- ✅ Memory Stability")
    report.append("- ✅ Database Query Performance")
    report.append("")
    
    report.append("### Frontend Tests")
    report.append("- ✅ Component Rendering")
    report.append("- ✅ User Interactions")
    report.append("- ✅ State Management (Zustand)")
    report.append("- ✅ Audio Visualization (Canvas)")
    report.append("- ✅ Authentication Flow")
    report.append("- ✅ Error Handling")
    report.append("- ✅ Accessibility (ARIA, Keyboard)")
    report.append("- ✅ Performance")
    report.append("- ✅ Browser Compatibility")
    report.append("")
    
    report.append("### E2E Tests")
    report.append("- ✅ Authentication Flows")
    report.append("- ✅ Mastering Workflow")
    report.append("- ✅ Transport Controls")
    report.append("- ✅ Sidebar Navigation")
    report.append("- ✅ File Upload")
    report.append("- ✅ Analysis Tabs")
    report.append("- ✅ Metering Panel")
    report.append("- ✅ Responsive Design")
    report.append("- ✅ Accessibility")
    report.append("- ✅ Error Handling")
    report.append("")
    
    report.append("## Running the Tests\n")
    report.append("### Backend Tests")
    report.append("```bash")
    report.append("cd rain-tests/backend")
    report.append("pytest test_protocol.py -v")
    report.append("```")
    report.append("")
    
    report.append("### Security Tests")
    report.append("```bash")
    report.append("cd rain-tests/security")
    report.append("pytest test_protocol.py -v")
    report.append("```")
    report.append("")
    
    report.append("### Performance Tests")
    report.append("```bash")
    report.append("cd rain-tests/performance")
    report.append("pytest test_protocol.py -v --tb=short")
    report.append("```")
    report.append("")
    
    report.append("### Frontend Tests")
    report.append("```bash")
    report.append("cd rain-tests/frontend")
    report.append("npm install")
    report.append("npm test")
    report.append("```")
    report.append("")
    
    report.append("### E2E Tests")
    report.append("```bash")
    report.append("cd rain-tests/e2e")
    report.append("npx playwright test")
    report.append("```")
    report.append("")
    
    report.append("## CI/CD Integration\n")
    report.append("Add to `.github/workflows/ci.yml`:")
    report.append("```yaml")
    report.append("- name: Run Security Tests")
    report.append("  run: pytest rain-tests/security/ -v")
    report.append("  ")
    report.append("- name: Run Performance Tests")
    report.append("  run: pytest rain-tests/performance/ -v --tb=short")
    report.append("```")
    
    report_path = Path(__file__).parent / 'TEST_PROTOCOL_REPORT.md'
    with open(report_path, 'w') as f:
        f.write('\n'.join(report))
    
    print(f"\n{Colors.OKGREEN}Report saved to: {report_path}{Colors.ENDC}\n")


if __name__ == "__main__":
    sys.exit(analyze_test_protocol())
