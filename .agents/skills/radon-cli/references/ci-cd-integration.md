# CI/CD Integration and Automation

Integrate Radon into continuous integration pipelines and automate code quality checks.

## GitHub Actions Workflow

### Basic Quality Gate

```yaml
name: Code Quality

on: [push, pull_request]

jobs:
  radon:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install radon
        run: pip install radon
      
      - name: Check cyclomatic complexity
        run: radon cc --min D --max F src/
        continue-on-error: true
      
      - name: Check maintainability index
        run: radon mi src/
        continue-on-error: true
```

### Strict Enforcement

```yaml
- name: Enforce complexity limits
  run: |
    # Fail if any function exceeds C rank
    if radon cc --min C src/ | grep -E "^\s+(M|F)"; then
      echo "Functions exceed complexity limit C"
      exit 1
    fi

- name: Enforce maintainability
  run: |
    # Fail if any file has low MI
    if radon mi --max B src/ | grep "^src"; then
      echo "Some files have low maintainability"
      exit 1
    fi
```

### Generate Artifacts

```yaml
- name: Generate metrics reports
  if: always()
  run: |
    mkdir -p metrics
    radon cc --json src/ > metrics/cc-report.json
    radon mi --json src/ > metrics/mi-report.json
    radon raw --json src/ > metrics/raw-report.json
    radon hal --json src/ > metrics/hal-report.json

- name: Upload metrics
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: radon-metrics
    path: metrics/
```

## Pre-commit Hook

Automatically check code before committing:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: radon-cc
        name: radon cyclomatic complexity
        entry: radon cc
        language: system
        types: [python]
        args: [--min, B, --order, SCORE]
        require_serial: false

      - id: radon-mi
        name: radon maintainability index
        entry: radon mi
        language: system
        types: [python]
        args: [--min, A]
        require_serial: false
```

## Make Targets

Add to Makefile for local development:

```makefile
.PHONY: quality metrics report-cc report-mi report-raw report-hal

# Install radon
install-radon:
	uv add --dev radon

# Check all metrics
quality: check-cc check-mi
	@echo "✓ Code quality checks passed"

check-cc:
	@echo "Checking cyclomatic complexity..."
	radon cc --min B --order SCORE src/ || exit 1

check-mi:
	@echo "Checking maintainability index..."
	radon mi --min A src/ || exit 1

# Generate metrics files
metrics: report-cc report-mi report-raw report-hal
	@echo "✓ Metrics generated"

report-cc:
	radon cc --json src/ > build/cc-metrics.json

report-mi:
	radon mi --json src/ > build/mi-metrics.json

report-raw:
	radon raw --json src/ > build/raw-metrics.json

report-hal:
	radon hal --json src/ > build/hal-metrics.json

# HTML report (requires custom script)
report-html: metrics
	@python scripts/generate_report.py build/ > build/metrics.html
```

## Python Script for Automated Checks

```python
#!/usr/bin/env python3
"""
Automated radon checks with custom thresholds.
"""
import subprocess
import json
import sys

COMPLEXITY_MAX = "D"  # C = 20 max, D = 30 max
MIN_MI = "A"  # A = 20+ MI

def run_command(cmd):
    """Run radon command and return JSON output."""
    result = subprocess.run(
        cmd + ["--json"],
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)

def check_complexity(path: str) -> bool:
    """Check cyclomatic complexity thresholds."""
    print("Checking cyclomatic complexity...")
    data = run_command(["radon", "cc", "--max", COMPLEXITY_MAX, path])
    
    violations = []
    for file_path, results in data.items():
        for block in results:
            if block["rank"] in ["D", "E", "F"]:
                violations.append(
                    f"  {file_path}:{block['lineno']} "
                    f"{block['name']} ({block['rank']})"
                )
    
    if violations:
        print("✗ Complexity violations:")
        for v in violations:
            print(v)
        return False
    
    print("✓ Complexity checks passed")
    return True

def check_maintainability(path: str) -> bool:
    """Check maintainability index thresholds."""
    print("Checking maintainability index...")
    data = run_command(["radon", "mi", "--min", MIN_MI, path])
    
    violations = []
    for file_path, result in data.items():
        if result["rank"] not in ["A"]:
            violations.append(
                f"  {file_path} - MI: {result['mi']:.2f} ({result['rank']})"
            )
    
    if violations:
        print("✗ Maintainability violations:")
        for v in violations:
            print(v)
        return False
    
    print("✓ Maintainability checks passed")
    return True

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "src/"
    
    results = [
        check_complexity(path),
        check_maintainability(path),
    ]
    
    if not all(results):
        sys.exit(1)
    
    print("\n✓ All quality checks passed")

if __name__ == "__main__":
    main()
```

## Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    stages {
        stage('Install') {
            steps {
                sh 'pip install radon'
            }
        }
        
        stage('Metrics') {
            steps {
                script {
                    // Cyclomatic complexity
                    sh 'radon cc --json src/ > cc-report.json || true'
                    
                    // Maintainability index
                    sh 'radon mi --json src/ > mi-report.json || true'
                    
                    // Raw metrics
                    sh 'radon raw --json src/ > raw-report.json || true'
                }
            }
        }
        
        stage('Quality Gate') {
            steps {
                sh '''
                    # Fail if high complexity functions found
                    if radon cc --min E src/; then
                        echo "High complexity functions found"
                        exit 1
                    fi
                    
                    # Fail if maintainability is critical
                    if radon mi --max C src/; then
                        echo "Low maintainability detected"
                        exit 1
                    fi
                '''
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: '*-report.json'
        }
    }
}
```

## Metrics Trending Script

Track metrics over time:

```python
#!/usr/bin/env python3
"""
Track code metrics over multiple runs.
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

def run_radon(path: str, metric_type: str):
    """Run radon command and return metrics."""
    cmd = ["radon", metric_type, "--json", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

def save_metrics(metrics: dict, output_dir: str):
    """Save metrics to dated file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    with open(output_dir / f"metrics_{timestamp}.json", "w") as f:
        json.dump(metrics, f, indent=2)

def analyze_trend(metric_dir: str):
    """Analyze metric trends."""
    metric_dir = Path(metric_dir)
    files = sorted(metric_dir.glob("metrics_*.json"))
    
    if len(files) < 2:
        print("Need at least 2 metric files for trend analysis")
        return
    
    # Load latest two files
    with open(files[-1]) as f:
        latest = json.load(f)
    with open(files[-2]) as f:
        previous = json.load(f)
    
    # Compare metrics
    print("Metric Trend Analysis:")
    print(f"Latest: {files[-1].name}")
    print(f"Previous: {files[-2].name}")
    print("")
    
    # Example: compare average complexity
    latest_avg = sum(
        b["complexity"] for f in latest.values() for b in f
    ) / sum(len(f) for f in latest.values())
    
    print(f"Average Complexity: {latest_avg:.2f}")

if __name__ == "__main__":
    path = "src/"
    output_dir = "metrics_history"
    
    # Collect metrics
    metrics = {
        "cc": run_radon(path, "cc"),
        "mi": run_radon(path, "mi"),
        "raw": run_radon(path, "raw"),
        "timestamp": datetime.now().isoformat(),
    }
    
    # Save and analyze
    save_metrics(metrics, output_dir)
    analyze_trend(output_dir)
```

## Dashboard Integration

Export metrics for visualization:

```python
#!/usr/bin/env python3
"""
Generate HTML dashboard from radon metrics.
"""
import json
from pathlib import Path

def generate_html_report(metrics_json: str) -> str:
    """Generate HTML report from metrics."""
    with open(metrics_json) as f:
        data = json.load(f)
    
    html = """
    <html>
    <head>
        <title>Code Quality Metrics</title>
        <style>
            body { font-family: sans-serif; margin: 20px; }
            .good { color: green; }
            .warning { color: orange; }
            .critical { color: red; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #4CAF50; color: white; }
        </style>
    </head>
    <body>
        <h1>Code Quality Metrics Dashboard</h1>
        <table>
            <tr><th>File</th><th>Complexity</th><th>Rank</th><th>Status</th></tr>
    """
    
    for file_path, blocks in data.items():
        for block in blocks:
            rank = block["rank"]
            status_class = {
                "A": "good", "B": "good",
                "C": "warning", "D": "warning",
                "E": "critical", "F": "critical"
            }[rank]
            
            html += f"""
            <tr>
                <td>{file_path}</td>
                <td>{block['complexity']}</td>
                <td class="{status_class}">{rank}</td>
                <td>{block['name']}</td>
            </tr>
            """
    
    html += "</table></body></html>"
    return html

if __name__ == "__main__":
    report = generate_html_report("metrics/cc-report.json")
    with open("metrics/dashboard.html", "w") as f:
        f.write(report)
    print("Dashboard generated at metrics/dashboard.html")
```
