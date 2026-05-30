# Security Policy

## Reporting Security Issues

Report suspected vulnerabilities through GitHub security advisories if available, or open a minimal issue that requests a private maintainer contact path. Do not include exploit details, private vault content, credentials, tokens, or personal data in public issues.

## Response Timeline

Maintainers aim to acknowledge security reports within 7 business days and provide a status update after initial triage.

## Private Vault Data

Real vault content can contain personal, business, or credential-adjacent information. Public bug reports must use sanitized examples or files from `tests/fixtures/sample-vault/`.

## Supported Versions

Security fixes target the latest GitHub source release on the **0.2.x** line (`0.2.0` / `v0.2.0` and later). The **0.1.x** line is superseded by 0.2.0; upgrade using [docs/migration-guide.md](docs/migration-guide.md).
