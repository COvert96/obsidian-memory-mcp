---
name: devops
description: Instructions and templates for devops-related tasks, including git operations, CI/CD pipeline management, and deployment strategies.
---

## Scope

Use this skill for any request that includes git operations, branch management, CI checks, release steps, or deployment workflow updates.

## Required Git Workflow

When asked to verify, commit, and/or push, follow this exact sequence:

1. Run `git status --short --branch` first and report what will change.
2. Run relevant verification commands (tests/lint/build) before committing.
3. If verification fails, stop and report failures before committing.
4. Stage changes intentionally:
   - If user says "all changes", use `git add -A`.
   - Otherwise stage only requested files.
5. Create a commit using Conventional Commits format.
6. Push to the correct remote/branch and confirm the pushed commit SHA/range.
7. Run `git status --short --branch` again and confirm clean/expected state.

Do not skip verification or status reporting unless the user explicitly asks to skip checks.

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(engine): add cross-sectional backtest path with rebalance scheduling
feat(risk): add basket-level validation for long/short portfolios
feat(data): add panel feature computation with z-scores and ranks
feat(ml): add Optuna optimization framework with parallel trials
fix(broker): handle partial fill edge case in batch order submission
fix(universe): correct off-by-one in membership date boundary query
docs(adr): document cross-sectional strategy review
test(regression): update expected results for new cost model
chore(docker): bump PostgreSQL to 16.3
chore(data): update S&P 500 constituents through Q1 2026
```

Format:

```
<type>(<optional-scope>): <imperative summary>
```

Common types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`, `ci`, `build`.

## Push Reporting

After push, always report:

- branch pushed
- remote pushed to
- resulting commit SHA
- verification command(s) run and outcome
