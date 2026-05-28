# PRD: Phase 5B - Advanced Proposal Workflows and Memory Supersession

## Introduction

Phase 5B extends the core proposal engine from Phase 5A into higher-level workflows that need more than a single-file write. Its main purpose is to support correct workflow semantics for agent-managed `Memory/` and other write flows where preserving history matters more than simple overwrite mechanics.

## Relationship to Phase 5A

Phase 5A provides the base proposal engine: proposal persistence, single-file approval, expiry, and minimal lifecycle logging. Phase 5B builds on that foundation for workflows that require:

- grouped logical changesets
- contradiction-resolving memory supersession
- richer operator tooling
- richer audit and review surfaces

Phase 5B should not be built until there is evidence that one of these higher-level workflows is needed in practice.

## Primary Problem

`Memory/` management introduces a semantic problem, not just a file-write problem. New information may contradict or supersede older information. In those cases, correctness often requires preserving the older record as archived or superseded while marking a new record as active source of truth. A single-file overwrite is insufficient for that workflow.

## Goals

- Support grouped multi-file logical approvals when correctness requires coordinated file mutations
- Preserve historical memory records when new memory supersedes prior information
- Add richer operator review surfaces where Phase 5A’s preview-only model is insufficient
- Extend lifecycle logging into audit/reporting only if operators need it

## Scope

Phase 5B may include:

- grouped logical changesets above the Phase 5A proposal primitive
- memory supersession workflows for `Memory/`
- frontmatter conventions for active, archived, and superseded memory
- optional CLI `show`, `cleanup`, and `audit` commands
- optional enrichment of `proposals reject` with structured reason/notes beyond the baseline Phase 5A reject behavior
- optional diff previews
- optional batch approval when a real workflow needs it

## User Stories

### US-5B-001: Approve one logical change spanning multiple files
**Description:** As an operator, I need to approve one workflow transition even when correctness requires modifying more than one file.

**Acceptance Criteria:**
- [x] A higher-level proposal model can represent more than one file mutation as one logical approval
- [x] Approval applies all file mutations atomically enough for the workflow, or fails without leaving the workflow half-applied
- [x] Review output shows all affected files before approval

### US-5B-002: Supersede contradictory memory safely
**Description:** As an operator using agent-managed `Memory/`, I need contradictory updates to preserve history instead of silently replacing the previous source of truth.

**Acceptance Criteria:**
- [x] The workflow distinguishes file-state conflicts from semantic contradictions
- [x] When a new memory item supersedes an existing one, the prior memory is archived or marked superseded rather than silently overwritten
- [x] The new active memory note records the relationship to the superseded note
- [x] The supersession transition is reviewable and approvable as one logical workflow
- [x] MVP for this phase may require explicit identification of the contradicted memory; automatic contradiction detection is not required

### US-5B-003: Provide richer operator review tools
**Description:** As an operator, I need better inspection and management tools once proposal volume or workflow complexity exceeds the minimal Phase 5A CLI.

**Acceptance Criteria:**
- [x] `mcp-memory proposals show` can display a full proposal or grouped changeset
- [x] If implemented in Phase 5B, `mcp-memory proposals reject` supports structured reason/notes in addition to the baseline reject behavior from Phase 5A
- [x] `mcp-memory proposals cleanup` can remove or finalize expired proposals according to retention policy
- [x] Diff-oriented review is available when preview-only output is insufficient

### US-5B-004: Provide richer audit visibility
**Description:** As an operator, I need richer audit visibility when proposal history becomes an operational concern.

**Acceptance Criteria:**
- [x] Audit records can be queried separately from the primary proposal list
- [x] Audit output is sufficient to reconstruct who approved what workflow and when
- [x] Retention policy is explicit rather than implicit

## Functional Requirements

- FR-5B-1: Workflows that require multiple coordinated file mutations must be represented as one logical approval unit
- FR-5B-2: Memory supersession must preserve prior source-of-truth records as archived or superseded
- FR-5B-3: New active memory records must point back to superseded records using agreed metadata conventions
- FR-5B-4: Phase 5B supersession workflows must treat semantic contradictions as a higher-level policy concern, not as a variant of `old_hash` file-state conflict detection — the two are different error paths and must not be conflated in code or error messages
- FR-5B-5: Richer operator tools are justified only when Phase 5A’s minimum tooling is insufficient in practice

## Non-Goals

- No automatic contradiction detection based on LLM judgment alone
- No collaborative approval workflow
- No generalized knowledge-graph model for memory
- No requirement that every proposal become a grouped changeset; single-file proposals remain valid for simpler workflows

## Technical Considerations

- Grouped logical changesets should be modeled above the core Phase 5A proposal persistence boundary rather than embedded as special cases in single-file write code
- Memory supersession needs explicit metadata conventions such as `status`, `supersedes`, `superseded_by`, and `archived_at`
- The system should preserve clear dependency direction: generic proposal storage below, workflow-specific memory policy above
- Audit and reporting surfaces should remain optional until operator usage proves they are needed

## Success Metrics

- [x] Contradictory memory is never silently overwritten in supported supersession workflows
- [x] Operators can review one grouped change as one logical decision
- [x] Historical memory records remain traceable after supersession
- [x] Phase 5B features are only built when Phase 5A proves insufficient for real workflows

## Open Questions

- What frontmatter conventions should define active versus archived memory?
  A: Make logical convention.
- Should grouped changesets be introduced as a new proposal type or as a container over existing proposal rows?
  A: New proposal type.
- Does the first 5B workflow need batch approval, or only grouped single-approval transitions?
  A: Grouped single-approval transitions(?)
- What retention policy should apply to audit data and rejected proposals?
  A: 7 day retention.

## Dependencies

- Phase 5A complete
- Evidence of at least one real workflow that needs grouped multi-file approval or contradiction-resolving memory semantics

## Deliverables

These modules sit **above** `proposals/` in the dependency stack. They import from `proposals/`; `proposals/` must not import from them.

- `src/obsidian_memory_mcp/changesets.py` — grouped logical changeset model and approval orchestration; depends on `proposals/` for single-file write primitives
- `src/obsidian_memory_mcp/memory_workflows.py` — memory supersession workflow for `Memory/`, including archival and frontmatter conventions; depends on `changesets.py`
- `docs/memory-supersession-guide.md` — operator guide for contradiction-resolving memory workflows, including frontmatter conventions (`status`, `supersedes`, `superseded_by`, `archived_at`)
- `src/obsidian_memory_mcp/cli.py` — optional additions: `proposals show`, `proposals reject` (with notes), `proposals cleanup`, `proposals audit`
- `tests/unit/test_changesets.py` — grouped approval unit tests
- `tests/integration/test_memory_supersession.py` — end-to-end supersession workflow tests

If either `changesets.py` or `memory_workflows.py` acquires internal structure (multiple sub-modules, private helpers), promote it to a `workflows/` sub-package at that point. Do not pre-create the package speculatively.
