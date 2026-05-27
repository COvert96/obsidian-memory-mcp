---
name: clean-architecture
description: A set of principles and practices for designing maintainable software systems using Clean Architecture.
user-invocable: true
---

## Purpose
Minimize the lifetime human resources required to build and maintain a system.
Prioritize long-term maintainability (ease of change) over short-term implementation speed.

---

## Activation Criteria
Apply this skill when the user is:
- Designing a new system, service, or module
- Requesting a code review or architecture review
- Refactoring existing code
- Asking for architectural guidance or technology selection

**Do not apply** to: throwaway scripts (<~100 LOC), one-off utilities, or when the user has
explicitly deprioritized architectural concerns (e.g., prototype, spike, deadline crunch).

---

## Agent Action Vocabulary
Use these terms consistently throughout this document:

| Term | Meaning |
|---|---|
| **FLAG** | Note the issue; do not block output. Add an inline comment or review note. |
| **WARN** | Generate the output but prepend a warning block explaining the violation. |
| **REJECT** | Do not generate code containing this pattern. Explain why, then offer a compliant alternative. |

---

## Agent Operating Instructions (Priority Checklist)
Execute in order for every design or review task:

1. **Identify the Actor**: Who (which stakeholder/role) is driving this requirement?
2. **Draw the boundary**: Separate Policy (business rules) from Detail (IO, DB, UI, Frameworks) before choosing any library.
3. **Check dependency direction**: Verify no inner-layer module (Entity, Use Case) imports an outer-layer module (Framework, DB, Web).
4. **Humble the IO**: Move all logic into testable Interactors; keep GUI/DB code minimal (see Humble Object pattern).
5. **Enforce boundaries structurally**:
   - **Python**: No compiler enforcement exists. Use `mypy`/`pyright` with strict mode, `__all__` to control exports, and `_underscore` prefix conventions to signal internal-only. Enforce layer boundaries via import linting (`import-linter` / `pylint` with custom rules).
   - **TypeScript/Next.js**: Use `private`/`readonly` modifiers, barrel `index.ts` files to control public surface, and `@typescript-eslint` rules to restrict cross-layer imports. Note: no package-private scope exists — barrel files are the idiomatic substitute.
6. **Defer detail decisions**: If a technical choice (DB engine, framework) can be deferred without blocking progress, defer it — define an interface boundary instead.

---

## Core Principles

### 1. The Dependency Rule
- **Principle**: Source code dependencies must point only inward, toward higher-level policy.
- **Why it matters**: Prevents changes in low-level mechanisms (DB, UI) from forcing changes in high-level business rules.
- **Required behavior**: REJECT any inner-layer module that names, imports, or references an outer-layer construct.
- **Enforcement heuristic**: If a domain entity requires an import from a database or web library, the architecture is broken.
- **Anti-patterns**: Entities importing ORM models; Use Cases importing HTTP request/response objects.
- **Tradeoff**: Requires mapping code (DTOs) at every boundary crossing.
- **Example**:
  - ❌ `UserEntity extends ActiveRecord::Base` (Ruby) / `UserEntity(Base)` inheriting SQLAlchemy's `DeclarativeBase` (Python) / `UserEntity` importing Prisma-generated types (TypeScript)
  - ✅ `UserEntity` is a plain dataclass (Python) or plain interface/type (TypeScript); `SqlUserRepository` implements a `UserRepository` protocol (Python) or interface (TypeScript) defined in the domain layer.

---

### 2. Separation of Policy and Detail
- **Principle**: Business rules (Policy) are stable and valuable. IO, DB, UI, and Frameworks (Detail) are volatile and peripheral.
- **Why it matters**: Coupling stable policy to volatile details makes the system rigid and expensive to change.
- **Required behavior**: WARN when a library/framework is imported directly into a use case or entity. Propose an abstraction boundary.
- **Enforcement heuristic**: Business logic must be executable via a test runner with no DB or UI present.
- **Anti-patterns**: Hard-wired DB schema in core logic; UI dictating use case data structures.
- **Tradeoff**: May be over-engineering for a small, single-use script (see Activation Criteria).
- **Example**: The web layer is a delivery mechanism (IO device), not the center of the architecture.

---

### 3. Dependency Inversion Principle (DIP)
- **Principle**: High-level policy must not depend on low-level detail; both must depend on an abstraction.
- **Why it matters**: Makes details plug-in replaceable without touching policy.
- **Required behavior**: FLAG any use of `new ConcreteImplementation()` inside a high-level service. Recommend injection via an interface.
- **Enforcement heuristic**: Use Abstract Factories to create volatile concrete objects. Instantiation of volatile types should occur only in the outermost layer (Main/Composition Root).
- **Anti-pattern**: `new SqlDatabase()` called inside a domain service.
- **Tradeoff**: Increased indirection; harder for junior developers to trace execution.
- **Example**: `ServiceAreaComputer` calls `MeasurementDevice` through an abstract interface; the concrete `GpsSensor` is injected at startup.

---

### 4. Component Cohesion (Common Closure Principle — CCP)
- **Principle**: Classes that change for the same reason at the same time belong in the same component.
- **Why it matters**: Minimizes blast radius of change; a single requirement change should touch only one deployable unit.
- **Required behavior**: FLAG any class that serves multiple distinct Actors. Recommend splitting by Actor.
- **Enforcement heuristic**: If a single file change requires coordination between two different departments or stakeholders, the file violates CCP.
- **Anti-pattern**: A "God Class" serving the CFO (payroll), COO (reporting), and CTO (persistence) simultaneously.
- **Tradeoff**: More components to manage; higher initial decomposition cost.
- **Example**: Split into `PayCalculator` (CFO), `HourReporter` (COO), `EmployeeSaver` (CTO).

---

### 5. Stable Abstractions Principle (SAP)
- **Principle**: A component should be as abstract as it is stable.
- **Why it matters**: Highly depended-upon (stable) components must be extensible via polymorphism, not modification.
- **Required behavior**: FLAG any highly stable component (many dependents, few dependencies) that contains zero interfaces or abstract classes.
- **Enforcement heuristic**: 
  - `I (Instability) = Fan-out / (Fan-out + Fan-in)` — ranges 0 (maximally stable) to 1 (maximally unstable).
  - `A (Abstractness) = abstract classes + interfaces / total classes in component`.
  - Target: components near the Main Sequence where `|A + I - 1| ≈ 0`.
  - **Zone of Pain**: `I ≈ 0` AND `A ≈ 0` — stable but fully concrete (e.g., a DB schema depended on by everything).
  - **Zone of Uselessness**: `I ≈ 1` AND `A ≈ 1` — abstract but nothing depends on it.
- **Tradeoff**: Calculating these metrics requires tooling; manual analysis doesn't scale.

---

## Principle Precedence
When principles conflict, apply this priority order:

1. **Dependency Rule** (always enforced — no exceptions for inner layers)
2. **DIP** (enforced when a component is both volatile and depended upon by ≥2 consumers)
3. **CCP/SAP** (enforced for components expected to live beyond a single sprint)
4. **Separation of Policy/Detail** (enforced; relaxed only for confirmed throwaway code)

If adding a boundary now costs less than the expected refactoring cost later, implement it.
If no proven axis of change exists, defer (see Non-Goals: Speculative Generality).

---

## Code Review Rules

| Violation | Action | Description |
|---|---|---|
| Layering violation | REJECT | UI bypasses business logic to talk directly to DB |
| Framework leakage | REJECT | Framework constructs appear in domain entities: SQLAlchemy `Base`/`Column` (Python), Pydantic models used as domain entities, FastAPI `Request` in use cases, Prisma-generated types in domain logic, React `useRouter`/`useState` in business logic hooks |
| Public poisoning | FLAG | Every class marked `public`; recommend package-private/internal visibility |
| Test fragility | WARN | Tests navigate GUI to verify business rules; recommend a direct Interactor test API |
| Concrete volatility | FLAG | Class inherits from a volatile concrete class instead of an interface |

---

## Refactoring Triggers
Recommend refactoring when any of the following are detected:

- **Dependency cycles** (Morning After Syndrome): Build breaks due to transitive cycles. Apply the Acyclic Dependencies Principle (ADP): extract an interface or create a new component that both sides depend on.
- **Boundary inversion** (Architectural Decay): Dependencies cross layers in the wrong direction.
- **Zone of Pain**: A component with `I ≈ 0` and `A ≈ 0` — stable, concrete, and heavily depended upon. Introduce interfaces.
- **Tramp Data**: A Use Case receives or returns a raw Entity to/from the UI. Extract dedicated Request/Response DTOs.
- **Detail lock-in** (Rigid Redesign): Switching a concrete detail (e.g., a specific DB) would require rewriting business logic. Insert a Gateway interface.
- **React/Next.js boundary bleed**: Server component data-fetching logic, `useRouter`, or `fetch` calls appear inside components that contain business logic. Extract into a dedicated service/use-case layer; keep components as pure presenters.
- **Type-import inversion**: An infrastructure module (repository, writer, adapter) imports a type that is defined in a service or use-case module. Fix: extract the shared type into a shared models/DTOs module that both sides import. A repository importing from its service is a layering violation regardless of how small the import is.

**Output format for refactoring recommendations**: Provide (1) the identified smell, (2) the specific violation, (3) the recommended structural change with a before/after code sketch.

---

## System Design Heuristics

- **Screaming Structure**: Top-level package/module names should reflect use cases (`orders/`, `catalog/`), not technical layers (`controllers/`, `models/`). Within a domain package, filenames should make the layer order legible: shared data models → repository (infrastructure/IO) → service (orchestration). No upward imports — if a repository needs a type from its service, that type belongs in a shared models module.
- **Package boundary surface**: A package's public entry point (barrel file, `__init__.py`, `index.ts`) should re-export only the stable API that external callers need. Internal submodules are implementation details. If callers must reach into internals to get what they need, the public entry point is under-exporting and the boundary is leaking.
- **Evaluate Modularity**: Decompose systems into independently deployable units (jars, packages, services).
- **Preserve Optionality**: When asked to choose a concrete tool or framework, assess reversibility first. If reversible or premature, propose an abstraction boundary and explain the tradeoff. If a concrete choice is required, recommend one and specify it should be injected at the outermost layer (Composition Root / Main).
- **Boundary Cost Rule**: Implement a boundary when: (a) the volatile component has ≥2 consumers, OR (b) switching it without the boundary would require touching more than one layer.
- **Natural stack boundary**: In Python + Next.js projects, the backend API and frontend app are a canonical Policy/Detail boundary. The Python service owns business rules; Next.js is the delivery mechanism. Treat the API contract (request/response DTOs) as the boundary interface — neither side should leak its internals across it.

---

## Decision Frameworks

### When to Introduce an Abstraction
1. Is the component **volatile** (likely to change)?
2. Is it **depended upon** by other modules?
3. If **yes to both** → invert the dependency with an interface.
4. If **yes to one** → judgment call; document the risk.
5. If **no to both** → keep it concrete; revisit if it acquires dependents.

### When to Isolate a Framework
1. Does the framework require inheritance from its base classes?
2. If yes → create a **Proxy** or **Adapter** in the Infrastructure layer to keep the Domain pure.
3. Inject the framework dependency at the **Composition Root** (outermost/Main component only).

### When to Split a Module
1. Do these two classes change at the same time?
2. Are they triggered by the same **Actor**?
3. Interpretation:
   - **No to both** → separate into different components.
   - **No to one** → probable separation; evaluate Actor ownership.
   - **Yes to both** → keep together.

---

## Non-Goals
- **Short-term coding speed**: Clean Architecture accepts a higher initial cost in mapping code and interfaces.
- **Micro-optimization**: Do not sacrifice architecture for performance unless it is the proven bottleneck.
- **Speculative Generality**: Do not add boundaries for hypothetical future requirements. Add them when an axis of change is proven or when the cost of delay is clearly higher than the cost of implementation.

---

## Scope Exclusions
Do **not** enforce this doctrine for:
- Scripts or utilities under ~100 LOC with a single consumer
- Explicitly scoped prototypes / spikes
- Cases where the user has acknowledged the architectural tradeoff and opted out
- Pure data-transformation pipelines with no business logic