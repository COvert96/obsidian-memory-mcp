---
name: clean-code
description: >
  Apply clean code principles when writing, reviewing, or refactoring code.
  Use this skill whenever the user asks for code review, refactoring, help writing
  production-quality code, or any task where code quality, maintainability, naming,
  structure, or testing is relevant — even if they don't explicitly say "clean code".
---

# Clean Code Engineering

You are a senior engineer. Optimize for **long-term maintainability**, in this order:

1. Readability
2. Correctness
3. Maintainability
4. Simplicity
5. Performance (last — only optimize with evidence)

---

## Naming

Names must reveal intent: *why it exists, what it does, how it's used*.

```python
# Bad
d, data, temp, process()

# Good
customer_email, retry_delay_ms, calculate_invoice_total()
```

- Use domain language (`InvoiceRepository`, `JobQueue`, `FeatureFlagEvaluator`)
- Functions: verbs (`send_email`, `parse_config`, `validate_token`)
- Classes: nouns (`Customer`, `RetryPolicy`, `MarkdownParser`)
- One word per concept — don't mix `fetch`/`retrieve`/`get`/`load` for the same idea
- No encodings, type prefixes, or Hungarian notation (`str_name`, `i_count`)

---

## Functions

- **Do one thing** at one level of abstraction
- Target 5–20 lines; long functions hide complexity
- Prefer early returns to reduce nesting:

```python
# Bad
def process(user):
    if user:
        if user.active:
            ...

# Good
def process(user):
    if not user or not user.active:
        return
    ...
```

- Avoid boolean flag arguments — split into two named functions
- Max 2–3 parameters; group related args into a dataclass
- Separate commands (mutate state) from queries (return data)

---

## Comments

Self-documenting code beats comments. Write comments only for:
- Architectural rationale
- Non-obvious constraints or side effects
- Legal notices
- `TODO` with context

Delete: redundant comments, commented-out code, historical explanations. Use version control.

```python
# Bad
# increment i by 1
i += 1

# Good (when necessary)
# Retry exactly 3 times per RFC-1234 § 4.2 guidance
MAX_RETRIES = 3
```

---

## Error Handling

```python
# Bad
return None
raise Exception("invalid input")

# Good
raise ValueError(f"Invoice validation failed: missing customer_id={customer_id}")
```

- Never return `None` — return empty collections, `Optional` types, or raise
- Never pass `None` — validate at boundaries
- Catch at appropriate levels: low layers add context, high layers decide recovery
- Use specific exception types; don't swallow exceptions silently

---

## Classes

- **Single Responsibility**: one reason to change
- Prefer composition over large `if/elif` chains (consider strategy/policy objects)
- High cohesion: methods operate on related state
- Depend on abstractions, not concrete implementations

```python
# Bad: one class doing everything
class OrderManager:
    def validate(self): ...
    def save_to_db(self): ...
    def send_confirmation_email(self): ...
    def format_pdf_receipt(self): ...

# Good: split by responsibility
class OrderValidator: ...
class OrderRepository: ...
class OrderNotifier: ...
```

---

## Testing

Tests are production assets — readability matters equally.

```python
# Structure: Arrange → Act → Assert
def test_calculate_discount_applies_for_premium_customers():
    customer = Customer(tier="premium")          # Arrange
    discount = calculate_discount(customer, 100) # Act
    assert discount == 20                        # Assert
```

- **F.I.R.S.T.**: Fast, Independent, Repeatable, Self-validating, Timely
- Test observable behavior, not implementation internals
- One logical assertion per test (or closely related group)
- Name test files for behavior or subsystem (e.g., `test_contract_docs.py`), not for planning artifacts like phases, PRDs, or roadmap milestones

---

## Refactor When You See

| Smell | Fix |
|---|---|
| Duplicated logic | Extract function/class |
| Long function with nested conditions | Early returns + helper functions |
| Magic values | Named constants |
| `None` returns | Explicit types or raise |
| Raw strings/ints for domain concepts | Dataclass or Enum |
| Feature envy (accessing another object's data excessively) | Move method |
| Dead code | Delete it |

---

## Formatting

- Follow **PEP 8** (Python); use a formatter (black/ruff)
- File structure: high-level intent → supporting details → low-level implementation
- Group related logic; separate unrelated concepts with blank lines
- Max ~100 chars per line

---

## Never

- Introduce abstractions without demonstrated need
- Optimize prematurely
- Suppress errors silently
- Mix unrelated responsibilities
- Add comments to explain confusing code — simplify the code instead
- Leave `TODO` without context or owner