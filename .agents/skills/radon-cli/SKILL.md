---
name: radon-cli
description: Python code complexity and metrics analysis tool. Use when analyzing cyclomatic complexity, maintainability index, raw metrics (LOC, SLOC, comments), or Halstead metrics for code quality assessment. Useful for identifying high-complexity functions, tracking code health metrics, generating quality reports, and working with configuration files.
---

# Code Metrics Analysis with radon-cli

Radon is a Python tool that computes code metrics including cyclomatic complexity, maintainability index, raw metrics (LOC, SLOC, comments, blank lines), and Halstead metrics. It supports both command-line usage and programmatic access.

## Quick start

```bash
# Analyze cyclomatic complexity
uv run radon cc path/to/code

# Analyze maintainability index
uv run radon mi path/to/code

# Analyze raw metrics (lines, comments, etc.)
uv run radon raw path/to/code

# Analyze Halstead metrics
uv run radon hal path/to/code

# Show results in JSON
uv run radon cc path/to/code --json

# Analyze with minimum complexity threshold
uv run radon cc --min B path/to/code
```

## Commands

### Core Commands

#### `cc` — Cyclomatic Complexity

Analyzes Python source files and computes cyclomatic complexity. Blocks are ranked from A (simplest, 1-5) to F (most complex, 41+).

```bash
# Basic usage
uv run radon cc path/to/code

# Analyze multiple paths
uv run radon cc path1 path2 path3

# Analyze from stdin
cat file.py | uv run radon cc -

# Show complexity scores alongside ranks
uv run radon cc -s path/to/code

# Filter by complexity rank
uv run radon cc --min B --max D path/to/code

# Order results by complexity (descending)
uv run radon cc path/to/code --order SCORE

# Order by lines
uv run radon cc path/to/code --order LINES

# Order alphabetically
uv run radon cc path/to/code --order ALPHA

# Show average complexity
uv run radon cc -a path/to/code

# Show total average (unfiltered)
uv run radon cc --total-average path/to/code

# Exclude assert statements
uv run radon cc --no-assert path/to/code

# Output to file
uv run radon cc -O report.txt path/to/code

# JSON output
uv run radon cc --json path/to/code

# XML output (for Jenkins)
uv run radon cc --xml path/to/code
```

**Complexity Ranks:**

| Score | Rank | Category |
|-------|------|----------|
| 1-5   | A    | Low - simple block |
| 6-10  | B    | Low - well structured and stable |
| 11-20 | C    | Moderate - slightly complex |
| 21-30 | D    | More than moderate - more complex |
| 31-40 | E    | High - complex, alarming |
| 41+   | F    | Very high - error-prone, unstable |

**Block Types:**

- `F` = Function
- `M` = Method
- `C` = Class

#### `mi` — Maintainability Index

Analyzes Python source code and computes maintainability index (0-100).

```bash
# Basic usage
uv run radon mi path/to/code

# Analyze multiple paths
uv run radon mi path1 path2

# Show MI values alongside ranks
uv run radon mi -s path/to/code

# Filter by MI rank
uv run radon mi --min B --max A path/to/code

# Do not count multiline strings as comments
uv run radon mi -m path/to/code

# JSON output
uv run radon mi --json path/to/code

# Output to file
uv run radon mi -O report.txt path/to/code
```

**MI Ranks:**

| Score | Rank | Category |
|-------|------|----------|
| 100-20| A    | Very high |
| 19-10 | B    | Medium |
| 9-0   | C    | Extremely low |

#### `raw` — Raw Metrics

Analyzes Python modules to compute raw metrics (LOC, LLOC, SLOC, comments, blank lines).

```bash
# Basic usage
uv run radon raw path/to/code

# Analyze multiple paths
uv run radon raw path1 path2

# Show summary at the end
uv run radon raw -s path/to/code

# JSON output
uv run radon raw --json path/to/code

# Output to file
uv run radon raw -O report.txt path/to/code
```

**Metrics Computed:**

- `LOC` — Total lines of code
- `LLOC` — Logical lines of code
- `SLOC` — Source lines of code (excluding comments/blanks)
- `comments` — Python comment lines (#)
- `multi` — Lines with multiline strings
- `blank` — Blank or whitespace-only lines

**Equation:** SLOC + multi + comments + blank = LOC

#### `hal` — Halstead Metrics

Analyzes Python files and computes Halstead complexity metrics (effort, volume, difficulty, time).

```bash
# Basic usage
uv run radon hal path/to/code

# Analyze at function level (instead of file level)
uv run radon hal -f path/to/code

# JSON output
uv run radon hal --json path/to/code

# Output to file
uv run radon hal -O report.txt path/to/code
```

## Common Options

All commands support the following options:

```bash
# Exclude files matching glob patterns
uv run radon cc -e "tests/*,docs/*" path/to/code

# Ignore directories matching glob patterns
uv run radon cc -i "tests,docs,.venv" path/to/code

# Include Python cells from Jupyter notebooks
uv run radon cc --include-ipynb path/to/code

# Report on individual cells in .ipynb files
uv run radon cc --ipynb-cells path/to/code

# Output to file
uv run radon cc -O output.txt path/to/code

# JSON format
uv run radon cc --json path/to/code
```

## Configuration Files

Create a configuration file to set default arguments. Radon looks for:

- `radon.cfg`
- `setup.cfg`
- `~/.radon.cfg`

**Format:** INI-style, under `[radon]` section

```ini
[radon]
exclude = test_*.py,*/tests/*
ignore = .venv,docs,build
cc_min = B
cc_max = F
mi_min = A
mi_max = C
average = True
output_file = metrics-report.txt
```

**Available Config Keys:**

- `exclude` — Exclude file patterns
- `ignore` — Ignore directory patterns
- `cc_min` / `cc_max` — Cyclomatic complexity thresholds
- `mi_min` / `mi_max` — Maintainability index thresholds
- `average` — Show average complexity
- `total_average` — Show total average (unfiltered)
- `show_complexity` — Show complexity scores with ranks
- `show_mi` — Show MI values with ranks
- `order` — SCORE, LINES, or ALPHA
- `no_assert` — Don't count assert statements
- `output_file` — Save output to file
- `summary` — Show summary for raw metrics
- `include_ipynb` — Include Jupyter notebooks
- `ipynb_cells` — Report on individual cells

## Output Formats

### Human-Readable

Default text output with colored complexity ranks:

```bash
uv run radon cc src/
```

### JSON

Export for processing by other tools:

```bash
uv run radon cc --json src/ > metrics.json
uv run radon mi --json src/ | jq .
```

### XML

Targeted for Jenkins CCM plugin:

```bash
uv run radon cc --xml src/ > ccm-report.xml
```

### File Output

Save to text file:

```bash
uv run radon cc -O report.txt src/
```

## Jupyter Notebook Support

Radon can analyze Python code within `.ipynb` files (requires `nbformat`):

```bash
# Include notebook cells in analysis
uv run radon cc --include-ipynb notebooks/

# Report on individual cells (shows cell numbers)
uv run radon cc --ipynb-cells notebooks/

# Combined: analyze code and notebooks
uv run radon mi --include-ipynb --ipynb-cells .
```

## Practical Examples

### Find Most Complex Functions

```bash
# Show complexity scores, minimum B (complexity 6+), ordered by score
uv run radon cc -s -n B --order SCORE src/

# Output to JSON for further processing
uv run radon cc --json src/ | jq '.[] | select(.complexity >= 10)'
```

### Analyze Entire Project

```bash
# All metrics, excluding tests and virtualenv
uv run radon cc -i ".venv,tests,build" src/
uv run radon mi -i ".venv,tests,build" src/
uv run radon raw -i ".venv,tests,build" src/
```

### Track Code Health Over Time

```bash
# Generate dated reports
uv run radon mi --json src/ > metrics-$(date +%Y%m%d).json
uv run radon raw --json src/ > raw-$(date +%Y%m%d).json

# Compare metrics between runs
jq '.[] | {filename, mi}' metrics-20260331.json > current.txt
```

### Generate HTML Reports

```bash
# JSON output for custom HTML generation
uv run radon cc --json src/ > cc-report.json
uv run radon mi --json src/ > mi-report.json

# Use external tools (e.g., jq) to format
cat cc-report.json | jq -r '.[] | "\(.name): \(.complexity)"' > summary.txt
```

### CI/CD Pipeline Integration

```bash
# Fail if complexity is too high
uv run radon cc --max D src/ || exit 1

# Generate metrics as artifacts
uv run radon cc --json --output-file build/cc-metrics.json src/
uv run radon mi --json --output-file build/mi-metrics.json src/
```

## Environment Variables

```bash
# Set file encoding (useful on Windows)
export RADONFILESENCODING=utf-8
uv run radon cc src/
```

## Tips & Best Practices

1. **Automate threshold enforcement** — Use `--min` and `--max` to enforce standards in CI/CD
2. **Configure defaults** — Create `radon.cfg` to avoid repeating flags
3. **Monitor trends** — Generate JSON reports periodically to track metrics over time
4. **Focus on critical code** — Use `--order SCORE` to find the most complex functions first
5. **Combine with CI/CD** — Export JSON/XML for dashboard visualization
6. **Exclude test code** — Use `--ignore` to focus on production code quality
7. **Review notebooks** — Use `--include-ipynb` for data science projects

## Common Troubleshooting

### Unicode Issues on Windows

If encountering Unicode errors, set the file encoding:

```bash
set RADONFILESENCODING=utf-8
uv run radon cc src/
```

### High Complexity Scores

If functions consistently score high (E or F):

```bash
# Identify problematic functions
uv run radon cc --min E src/

# Show detailed complexity information
uv run radon cc -s --order SCORE src/
```

### Configuration Not Applied

Check configuration file location:

```bash
# Radon searches in order:
# 1. ./radon.cfg
# 2. ./setup.cfg
# 3. ~/.radon.cfg

# Verify configuration is valid INI format
cat radon.cfg
```
