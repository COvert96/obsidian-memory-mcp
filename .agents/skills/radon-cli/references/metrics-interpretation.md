# Metrics Interpretation Guide

Understand what Radon metrics mean and how to act on them.

## Cyclomatic Complexity (CC)

Measures the number of decision points in code (conditionals, loops, exception handling).

### Quick Assessment

| Rank | Score | Meaning | Action |
|------|-------|---------|--------|
| A | 1-5 | Simple, easy to understand and test | Maintain current style |
| B | 6-10 | Well-structured, manageable | Good target for new code |
| C | 11-20 | Moderately complex, testing required | Watch for growth |
| D | 21-30 | Complex, risky | Consider refactoring |
| E | 31-40 | Very complex, hard to test | Refactor required |
| F | 41+ | Unmaintainable, error-prone | Immediate refactoring |

### Common Complexity Culprits

```python
# High complexity pattern: Many conditions
def process_order(item, user, inventory):
    if item and user:                    # +1
        if inventory.has(item):          # +1
            if user.has_credits():       # +1
                if not user.is_banned():  # +1
                    if item.price > 0:    # +1
                        # ... handle logic
                    else:                # +1
                        # ... handle free item
                else:                    # +1
                    # ... handle banned
        else:                            # +1
            # ... handle missing

# Complexity = 8 (B rank)
```

**Refactor Strategy:** Extract nested conditions into helper functions

```python
def process_order(item, user, inventory):
    if not _can_purchase(item, user, inventory):  # +1
        return False
    return _complete_purchase(item, user)

def _can_purchase(item, user, inventory):
    return (item and user and 
            inventory.has(item) and 
            user.has_credits() and 
            not user.is_banned() and 
            item.price > 0)

# Complexity reduced to 2 per function
```

### Target Thresholds

```bash
# Enforce B-level complexity for new code
radon cc --min A --max B src/

# Flag anything D or worse
radon cc --min D src/
```

## Maintainability Index (MI)

Composite metric combining complexity, lines of code, and documentation. Higher is better (0-100).

| MI Score | Rank | Status | Risk |
|----------|------|--------|------|
| 100-20 | A | Maintainable | Low |
| 19-10 | B | Maintainability concerns | Medium |
| 9-0 | C | Difficult to maintain | High |

### Improving MI

1. **Reduce complexity** — Extract functions
2. **Reduce file size** — Split large modules
3. **Add documentation** — Module docstrings, function signatures
4. **Improve variable names** — Self-documenting code

```bash
# Monitor files with low MI
radon mi --max C src/
```

## Raw Metrics

### Lines of Code (LOC) Interpretation

```bash
# Total lines = SLOC + multi + comments + blank
# Should maintain: SLOC ~70%, comments ~15-20%, blank ~10-15%

# Example from radon output:
# LOC: 150
# LLOC: 95      (95 logical lines)
# SLOC: 100     (source lines - code)
# Comments: 25  (about 17%)
# Multi: 5      (multiline strings)
# Blank: 20     (about 13%)
```

### Healthy Ratios

- **Comments/LOC:** 15-25% for complex code, 10% for simple code
- **SLOC/LOC:** 60-80% actual code
- **Function length:** 50-100 LOC is typical; >200 is risky

## Halstead Metrics

Measures code effort, volume, difficulty, and estimated development time.

| Metric | Meaning | Target |
|--------|---------|--------|
| Volume | How much information the code contains | Lower is better |
| Difficulty | How hard code is to understand | Lower is better |
| Effort | Estimated effort to code (minutes) | Lower is better |
| Time | Estimated time to code (minutes) | Lower is better |

```bash
# High effort/difficulty indicates:
# - Too many distinct operators/operands
# - Overly complex algorithms
# - Redundant code patterns

radon hal -f src/  # Function-level analysis
```

## Decision Tree for Refactoring

```
Is CC > 10?
├─ Yes → Is file > 200 LOC?
│   ├─ Yes → Split into classes/functions
│   └─ No  → Extract nested conditions
└─ No  → Is MI < 20?
    ├─ Yes → Improve naming & add docs
    └─ No  → Monitor, no action needed

Is any function CC > 15?
├─ Yes → Extract sub-functions
└─ No  → Continue monitoring
```

## Setting Project Standards

```ini
# radon.cfg - Example standards
[radon]
# Don't analyze tests/build
ignore = tests,build,.venv

# Enforce max complexity
cc_max = C          # Functions should be <= 20 complexity

# Maintainability targets
mi_min = A          # All files should be >= 20 MI

# Reporting
show_complexity = True
average = True
```

## Reporting Standards

### Weekly Report Template

```bash
#!/bin/bash
echo "=== Radon Code Quality Report ==="
echo "Date: $(date)"
echo ""
echo "Cyclomatic Complexity:"
radon cc --min D --order SCORE src/
echo ""
echo "Maintainability Index:"
radon mi --max B src/
echo ""
echo "Lines of Code (top 10):"
radon raw src/ | head -20
```

### Tracking Trends

```bash
# Generate timestamped reports
radon cc --json src/ > cc-$(date +%Y%m%d).json
radon mi --json src/ > mi-$(date +%Y%m%d).json

# Create comparison
jq -r '.[] | select(.complexity >= 10) | "\(.name): \(.complexity)"' \
  cc-20260301.json > cc-top.txt
```
