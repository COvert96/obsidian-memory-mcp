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

## Module & Package Structure

### When to split a file into a package

File size is a **weak signal**. Split when the file has two distinct audiences — callers who need concern A and callers who need concern B, and neither group ever needs the other.

**Split triggers:**
- A helper at the bottom of the file is only called by one of two classes in the same file
- Different callers import different, unrelated subsets of the module
- The file serves more than one distinct change-reason or Actor

**Do not split when:**
- The single responsibility is intact even though the file is 400+ lines
- Splitting would require a `_common.py` holding fewer than ~30 lines
- The resulting sub-files would each be under 50 lines

### Package topology for a domain package

When promoting a module to a package, make the layer order legible from the filenames:

```
my_package/
  __init__.py      # re-exports the stable public API only
  _models.py       # shared dataclasses/enums — imported by everyone below
  repository.py    # persistence / IO layer — imports _models only
  service.py       # orchestration — imports _models and repository
```

Dependency direction within the package: `_models` ← `repository` ← `service`. Nothing below imports from something above.

### Service vs. Repository naming

When a package contains both orchestration and persistence, name them explicitly:

| Role | Name |
|---|---|
| Workflow orchestration (coordinates, decides) | `service.py` or `{domain}_service.py` |
| Reads / writes to storage or IO | `repository.py` or `{domain}_repository.py` |
| Shared data types used by both | `_models.py` |

**Type-import inversion**: if `repository.py` needs a type that lives in `service.py`, that type belongs in `_models.py`. A repository importing from its service is a layering violation — extract immediately.

### `__init__.py` export discipline

- Export only the **stable public API** that callers outside the package need
- Internal submodule names use an underscore prefix (`_models.py`, `_io.py`, `_errors.py`) — this signals they are not part of the external contract
- If callers must reach into a submodule to get what they need, the `__init__.py` is under-exporting

### The `_common.py` anti-pattern

Resist creating `_common.py`, `_shared.py`, or `_utils.py` for a handful of shared helpers. Instead:
- If fewer than ~3 functions are shared: put them in the upstream module and have the downstream module import them directly
- If the shared code is genuinely cross-cutting (>3 distinct importers, or non-trivial logic): a `_common.py` is warranted
- A grab-bag `_utils.py` that grows without a defined responsibility is a maintenance liability

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