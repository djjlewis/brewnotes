# Coding guidelines

These choices keep the code small enough to understand and change safely.

## Design

- Build vertical slices: one observable capability through only the boundaries it needs. Skip speculative layers of models, services, repositories, and controllers.
- Use functions for operations. Use a class when it owns state, an invariant, or a resource.
- Prefer composition. Add an interface or protocol when two real implementations exist; one adapter is a hypothetical seam.
- Keep business rules free of SDK objects, environment variables, network calls, and global state. Pass dependencies in at the entry point.
- Keep related code together. Split a module when it has two reasons to change. Splitting a function into forwarding functions adds files without making anything simpler.
- Tolerate small duplication until the shared concept is clear. Centralise an invariant at once when copies drifting apart would be a bug.
- Prefer plain control flow, guard clauses, and meaningful names over clever comprehensions and metaprogramming.

## Contracts and errors

- Type public functions and domain data. Validate external data at the boundary, then pass typed values inward.
- Catch only exceptions you can handle, and keep the cause when translating one. A failure never becomes an empty result or an unexplained null.
- Make configuration explicit at the entry point. No work at import time.

## Tests

- Test behaviour at a public boundary with real internal collaborators. Assert outcomes: return values, state changes, files written, specified errors.
- Each test must fail for a plausible fault. If you can't name the fault, delete the test.
- Use fakes only at external boundaries (network, cloud, clock, randomness). Assert on calls only when the call is the contract, such as an event published.
- Default tests run offline without credentials. Live checks are selected explicitly and reported separately.
- Keep fixtures small and inline. Local files in temporary directories are fine.

## Docs and comments

- Docstrings state what a public module, class, or function promises, including non-obvious inputs, failures, and side effects. They don't repeat the types.
- Comment a non-obvious constraint, workaround, or trade-off. If a comment explains confusing code, simplify the code instead.
- Domain terms live in `GLOSSARY.md`; consequential trade-offs in `docs/adr/`. Both are created when the first term or decision is agreed.

## Python

- Tooling: uv for dependencies, Ruff for formatting and linting, mypy in strict mode, pytest. Use a `src/` layout and a separate `tests/` tree that mirrors it.
- Gates: Ruff and mypy pass. Ruff `C901` with `max-complexity = 10`; aim for 5 or less.
- Use standard-library types, dataclasses, enums, and `pathlib.Path`. Add a validation library only for a concrete boundary need.
- Prefer immutable values (`frozen=True`) where mutation has no purpose. Use context managers for owned resources.
