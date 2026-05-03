## Summary

Describe the change and why it is needed.

## Type

- [ ] Bug fix
- [ ] Rules clarification or behavior change
- [ ] Feature
- [ ] Test coverage
- [ ] Documentation
- [ ] Refactor with no behavior change

## Checklist

- [ ] This PR is focused on one clear change.
- [ ] I checked the Rolling Chess rules spec when changing engine behavior.
- [ ] I added or updated tests for behavior changes.
- [ ] I did not duplicate engine rules in the frontend.
- [ ] I updated documentation for user-visible or rule-definition changes.

## Testing

Commands run:

```text
python -m pytest
python -m compileall -q src tests
node --check frontend/src/main.js
```

Manual verification, if relevant:

- 

## Notes For Reviewer

Mention rule edge cases, API compatibility, or follow-up work.

