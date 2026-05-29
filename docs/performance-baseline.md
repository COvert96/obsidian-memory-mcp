# Performance Baseline

Measured on 2026-05-28 on Windows 11, Python 3.12.13, local NVMe storage, using `tests/fixtures/sample-vault/` copied to an isolated temporary directory.

These values are fixture baselines, not universal promises. Hardware, antivirus scanning, filesystem sync tools, and vault size will change absolute times.

| Operation | Baseline |
|---|---:|
| Full indexing time | 303 ms |
| Search latency, `direct write workflow` | 8 ms |
| Read latency, `wiki/architecture/system-overview.md` | 2 ms |
| Context pack load time | 272 ms |
| Proposal creation latency | 33 ms |
| Token-count check, default pack | 13,191 tokens |
| Indexed markdown files | 34 |
| Index size | 659 KB |

Measure a fresh baseline with:

```powershell
uv run mcp-memory benchmark performance C:\path\to\fixture-vault
```

CI should reserve performance failures for regressions of 10x or greater against fixture-based baselines. Absolute time thresholds are documented here for operator context but are not enforced in CI for the MVP.
