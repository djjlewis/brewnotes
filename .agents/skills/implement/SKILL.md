---
name: implement
description: Implement one ticket through the slice loop, test-first at the boundary the ticket names, ending with review and a deletion pass. Use when starting work on an implementation ticket.
---

# Implement a ticket

One ticket, one branch, one owner. The ticket is the spec. `docs/agents/issue-tracker.md` says where tickets live; [the coding guidelines](../../../docs/coding-guidelines.md) are the standard review measures against.

## Steps

1. **Claim.** Mark the ticket claimed and branch from the base branch. Done when every acceptance example is unambiguous. An unclear example goes back to the owner before any code.
2. **Name the boundary.** In the ticket, name the public boundary the tests will drive and any external dependency a fake will stand in for. Done when both are written down in two or three lines.
3. **Red, green, per example.** Call the Skill tool with "tdd" for each acceptance example in turn: one failing test at the boundary, the smallest change that passes, then the next. Run the focused tests and the type checker as you go.
4. **Full checks.** Run the checks in `AGENTS.md`. Record a skipped or blocked check in the ticket as skipped.
5. **Review.** Call the Skill tool with "code-review" against the base branch, with the ticket as the spec. Fix correctness and scope findings.
6. **Deletion pass.** Remove code, parameters, tests, and docs whose removal fails no acceptance example, including anything added only so a test could reach inside. Done when the diff holds nothing the ticket didn't ask for.
7. **Resolve.** Record the verification commands and results in the ticket and mark it resolved. Update the README only if usage changed.

## Tests that earn their place

Apply these to each test before keeping it.

- It drives the boundary named in step 2 and asserts an outcome: a return value, a file written, a specified error. It reads like one acceptance example.
- It fails for a plausible fault. Name the fault; no fault, no test.
- Any fake stands at a named external dependency and returns data. A mock that asserts on calls is the exception, kept only when the call is the contract, and its docstring says why.
