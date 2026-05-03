# Pull Request Review

Pull requests should be small, focused, and testable. The maintainer is the final reviewer and merger.

## Review Checklist

Check every PR for:

- Clear description of the change.
- Link to an issue when the change is behavioral.
- No unrelated formatting or refactoring.
- Tests for engine, Web API, or behavior changes.
- No frontend-side duplication of chess rules.
- Passing CI.

## Engine Changes

Engine PRs must preserve the approved board topology:

- Files wrap from `a` to `h`.
- Ranks do not wrap.
- All pieces use wrapped files for movement and attacks.
- Sliding pieces may use any unobstructed valid route.
- Castling remains standard-only.
- En passant can cross the `a`/`h` boundary.

Required tests depend on the touched behavior. When in doubt, add a constructed-position test covering an `a`/`h` edge case.

## Web API Changes

Web API PRs should include HTTP-level tests when they add or change endpoints. The API should return structured JSON errors for invalid input.

The Python engine remains authoritative. API code should call public engine methods instead of private movement helpers unless there is a documented reason.

## Frontend Changes

Frontend PRs should keep the UI as a client of the backend rules engine.

A frontend PR should state:

- The user flow changed.
- Manual verification steps.
- Whether any API behavior is required.

Run:

```powershell
node --check frontend/src/main.js
```

## Docs-Only Changes

Docs-only PRs may skip adding tests, but CI should still pass. If docs clarify a rule, consider whether a test should also be added to lock the interpretation.

## Merge Criteria

A PR can be merged when:

- CI passes.
- Required tests are present.
- Review comments are resolved.
- The maintainer confirms the change does not contradict the rules spec.
- Rule-definition changes update documentation before or with implementation.

