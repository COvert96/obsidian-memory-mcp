---
tags: [concepts, context-packs, tokens]
type: concept
---
# Token Budgets

Token budgets limit the size of context packs to fit within Claude's context window. Each context pack is assigned a token limit, and the retrieval service truncates or rejects results that exceed the budget. Token counting is consistent across all packs to enable predictable behavior.

## Why Token Budgets Matter

Language models have finite context windows. Large result sets can exceed the window, requiring truncation or rejection. By enforcing budgets at the API level, the system prevents silent data loss and forces clients to make explicit choices about result volume.

## Budget Configuration

Each context pack specifies a `token_budget` in its configuration. Budgets are specified in approximate tokens. The retrieval service stops adding results when the cumulative token count approaches the limit, leaving a safety margin to account for token counting variance.

### Per-Pack Limits

Individual packs can have different budgets based on their use case. A "quick-reference" pack might have a 500-token limit, while an "onboarding" pack might allow 5000 tokens. Budgets are configured in `memory-mcp.yaml`.

### Global Defaults

If a pack does not specify a budget, a global default (typically 2000 tokens) is used. Global defaults can be overridden in the config file.

## Strict vs Soft Mode

The `strict_budget` parameter on context pack requests controls behavior when results exceed the budget. In strict mode (`true`), the request is rejected with `BUDGET_EXCEEDED`. In soft mode (`false`), results are truncated to fit the budget.

## Token Counting Method

Tokens are counted using the same method as the target Claude model (e.g., GPT-3.5 Turbo tokenizer). The service rounds up to account for tokenizer variance, ensuring actual token usage stays safely under budget.

## Budget Warnings

When soft mode truncates results, a warning is included in the response metadata. Clients can use these warnings to detect that they are missing relevant content and retry with a higher budget or narrower query. See [[context-pack-api]] and [[config-schema]] for configuration examples.
