---
tags: [memory-workflow, proposals]
type: guide
---
# Rejection Patterns

This guide covers when and how to reject proposals, patterns to avoid, and best practices for communicating rejection decisions.

## When to Reject

Reject a proposal if: the content has errors or is incomplete, the change is no longer needed, the timing is wrong, or the proposal conflicts with other pending changes. Rejection is a normal part of the workflow and does not imply any failure on the proposer's part.

## Rejection with Reason

When rejecting, always include a reason code (e.g., `DUPLICATE`, `INCOMPLETE`, `OUTDATED`, `CONFLICTS`) and optional detailed notes. Example: `obsidian-memory reject-proposal xyz --reason INCOMPLETE --notes "Missing section on error handling"`. The reason helps the proposer understand what needs to be fixed.

## Rejection Notes

Use notes to provide actionable guidance: "This note should include examples for each API endpoint" is more helpful than "Not good enough". Notes are recorded in the audit trail for future reference and enable learning from rejections.

## Resubmitting After Rejection

A rejected proposal cannot be reapproved. Instead, the proposer creates a new proposal addressing the feedback. When resubmitting, consider prefixing the file name with the reason (e.g., `note-v2.md`) to help reviewers understand the iteration history.

## Patterns to Avoid

Do not reject proposals for trivial issues that can be corrected after approval. Do not use rejection as a way to gather feedback without formal review — use [[proposal-lifecycle]] comments instead. Avoid rejecting multiple related proposals without coordinating with the proposer about whether they should be a single changeset. See [[approval-process]] and [[proposal-lifecycle]] for best practices.
