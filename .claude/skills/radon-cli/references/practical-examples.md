# Practical Examples and Project Patterns

Real-world usage patterns for code quality analysis in Meridian.

## Analyzing the Meridian Codebase

### Full Project Analysis

```bash
# Analyze all source code, excluding tests and migrations
radon cc -i "tests,migrations,.venv,build" src/

# Get detailed metrics with exclusions
radon mi -i "tests,migrations,.venv" src/
radon raw -i "tests,migrations,.venv" src/
```

### Configuration for Meridian

Create `radon.cfg` in project root:

```ini
[radon]
# Ignore test code and virtualenv
ignore = tests,migrations,.venv,build,__pycache__,.git

# Exclude specific test patterns
exclude = test_*.py,*_test.py,conftest.py

# Set standards for production code
cc_min = A
cc_max = D

# Maintainability targets
mi_min = A
mi_max = A

# Show averages
average = True
show_complexity = True
```

### Analyzing Specific Layers

```bash
# API layer complexity
radon cc src/meridian/api/

# Engine/core layer
radon cc src/meridian/engine/
radon cc src/meridian/core/

# Risk management layer
radon cc src/meridian/risk/

# Data layer
radon cc src/meridian/data/

# Strategy implementations
radon cc strategies/
```

## Finding Problem Areas

### Find Most Complex Functions

```bash
# Show top 10 most complex functions
radon cc --order SCORE src/ | head -30

# Only show functions with complexity >= 10 (C rank and above)
radon cc -s -n C --order SCORE src/

# Export to file for review
radon cc -s --order SCORE src/ > complexity-report.txt
```

### Identify Maintainability Issues

```bash
# Show files with low maintainability
radon mi --max B src/

# Show all files with MI values for comparison
radon mi -s src/

# Export for analysis
radon mi --json src/ | jq '.[] | select(.mi < 20)'
```

### Red Flags in Code Metrics

```bash
# Find F-rank complexity (unmaintainable)
radon cc --min F src/

# Find E-rank complexity (alarming)
radon cc --min E --max F src/

# Identify all complex functions across project
radon cc -n C --order SCORE src/ > high-complexity.txt
```

## Comparing Versions

### Before and After Refactoring

```bash
# Capture baseline
git stash
radon cc --json src/ > metrics-before.json

# Apply changes
git stash pop

# Capture after refactoring
radon cc --json src/ > metrics-after.json

# Compare (requires Python script)
python scripts/compare_metrics.py metrics-before.json metrics-after.json
```

### Python Script for Comparison

```python
#!/usr/bin/env python3
import json
import sys

def compare_metrics(before_file, after_file):
    with open(before_file) as f:
        before = json.load(f)
    with open(after_file) as f:
        after = json.load(f)
    
    print("=== Complexity Changes ===\n")
    
    for filepath in after:
        if filepath not in before:
            print(f"✓ NEW FILE: {filepath}")
            continue
        
        before_blocks = {b["name"]: b["complexity"] for b in before[filepath]}
        after_blocks = {b["name"]: b["complexity"] for b in after[filepath]}
        
        for name, after_cc in after_blocks.items():
            if name in before_blocks:
                before_cc = before_blocks[name]
                change = after_cc - before_cc
                
                if change < 0:
                    print(f"✓ IMPROVED: {name:<40} {before_cc} → {after_cc}")
                elif change > 0:
                    print(f"✗ REGRESSED: {name:<40} {before_cc} → {after_cc}")
```

## Workflow Integration

### Pre-Commit Quality Check

```bash
#!/bin/bash
# scripts/check-quality.sh

echo "Checking code quality..."

# Check complexity
if ! radon cc --min B --max E src/ &>/dev/null; then
    echo "✗ Functions exceed maximum complexity (E rank)"
    exit 1
fi

# Check maintainability
if radon mi --max C src/ &>/dev/null; then
    echo "✗ Some files have critical maintainability issues"
    exit 1
fi

echo "✓ Quality checks passed"
exit 0
```

### Generate PR Metrics Report

```bash
#!/bin/bash
# scripts/pr-metrics-report.sh

BRANCH="${1:-main}"

echo "# Code Quality Metrics"
echo ""
echo "## Cyclomatic Complexity"
echo ")"

# Show functions with complexity C or worse
if radon cc --min C src/ 2>/dev/null | grep -E "^src"; then
    echo "⚠️ Functions with elevated complexity (C-F ranks)"
else
    echo "✓ All functions have good complexity"
fi

echo ""
echo "## Maintainability Index"

# Show files with low MI
if radon mi --max B src/ 2>/dev/null | grep "^src"; then
    echo "⚠️ Files with maintainability concerns"
else
    echo "✓ All files have good maintainability"
fi
```

### Monitor Core Modules

```bash
# Regular check of critical modules
check_module() {
    echo "Analyzing $1..."
    radon cc --min B --order SCORE "$1"
    echo ""
}

echo "=== Critical Module Analysis ==="
check_module "src/meridian/core/"
check_module "src/meridian/engine/"
check_module "src/meridian/risk/"
```

## Performance and Optimization Guidance

### Large Module Analysis

For large modules, function-level analysis is more useful:

```bash
# Get metrics for each function individually
radon cc --output-file metrics.txt src/

# Raw metrics for understanding structure
radon raw --summary src/

# Halstead metrics to identify effort concentration
radon hal -f src/meridian/engine/
```

### Identifying Candidates for Refactoring

```bash
# Find long functions (high SLOC)
radon raw -s src/ | grep -E "^\s+LOC:" | awk '{print $NF}' | sort -rn

# Find functions with many responsibilities
# (high complexity + high LOC)
radon cc -s --order SCORE src/ > complexity.txt
# Then correlate with actual file sizes
```

## Testing Correlation

### Use Metrics to Guide Testing

```bash
# Heavily test high-complexity functions
radon cc -s -n C --order SCORE src/meridian/

# Document or refactor low-maintainability modules
radon mi --max B src/

# Prioritize test coverage for high-effort functions
radon hal -f src/meridian/strategies/
```

## Documentation Generation

### Create Markdown Report

```bash
#!/bin/bash

echo "# Meridian Code Quality Report" > METRICS.md
echo "Generated: $(date)" >> METRICS.md
echo "" >> METRICS.md

echo "## High Complexity Functions" >> METRICS.md
radon cc -s --order SCORE src/ | head -20 >> METRICS.md

echo "" >> METRICS.md
echo "## Maintainability Summary" >> METRICS.md
radon mi -s src/ >> METRICS.md
```

### JSON Report for Dashboards

```bash
# Generate all metrics in JSON for visualization
mkdir -p build/metrics

radon cc --json src/ > build/metrics/complexity.json
radon mi --json src/ > build/metrics/maintainability.json
radon raw --json src/ > build/metrics/raw.json
radon hal --json src/ > build/metrics/halstead.json

echo "Generated metrics in build/metrics/"
```

## Troubleshooting Common Issues

### Incremental Improvement

If current code is poor, set realistic initial targets:

```bash
# Month 1: Allow D rank functions
radon cc --min A --max D src/

# Month 2: Raise to C rank max
radon cc --min A --max C src/

# Month 3+: Maintain B/C as target
radon cc --min B --max C src/
```

### Excluding Generated or Legacy Code

```bash
# .radon.cfg - Exclude specific patterns
[radon]
exclude = *_pb2.py, generated_*, legacy_*
ignore = migrations, vendor, .venv
```

### Working with Large Codebases

```bash
# Analyze one module at a time
for module in src/meridian/*; do
    echo "=== $(basename $module) ==="
    radon cc "$module" --order SCORE
    echo ""
done
```
