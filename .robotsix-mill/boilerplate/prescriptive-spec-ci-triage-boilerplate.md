## Pattern: `prescriptive spec` — CI error log as implementation-ready spec

### When to use

Apply `prescriptive spec` triage when a CI-failure ticket (source: `ci`) meets **all** of:
- The CI error log contains code blocks or stack traces that directly identify the failing file(s) and line(s)
- The fix is mechanical and unambiguous from the log (e.g., a missing flag, a stale dependency, a config error)
- No design choices are needed — the implement agent can derive the fix deterministically from the log
- The change is single-scoped: one coherent fix, not multiple unrelated modifications

This pattern **skips the refine LLM call** — the CI error log itself serves as the implementation-ready specification.

### When NOT to use

Do NOT use `prescriptive spec` when:
- The CI error is ambiguous and requires investigation to root-cause
- The fix involves design choices (multiple plausible approaches)
- The error spans multiple unrelated subsystems
- The error is transient (network blip, runner flake) and should be retried
- The CI failure is out of scope for a parent ticket (use `maintenance-triage-boilerplate.md` instead)

### Template

```
prescriptive spec — code blocks constitute implementation-ready spec, skipping refine | auto-approve: APPROVE — [short justification of why this is a routine CI fix with no high-risk gate]
```

The auto-approve justification should cite the specific CI job or workflow and why it carries no high-risk concerns:

```
auto-approve: APPROVE — This is a [CI workflow change / routine CI workflow log] for [specific job]; [no security, destructive, public-API, cross-repo, or new runtime dependency changes are indicated / does not cross any high-risk gate], so no human review is needed.
```

### Concrete examples from this repo

**CI workflow fix — docker-pr-scan job** (ticket `20260807T203848Z-ci-failure-ci-on-main-3752`):
> prescriptive spec — code blocks constitute implementation-ready spec, skipping refine | auto-approve: APPROVE — This is a CI workflow change (docker-pr-scan job) that does not cross any high-risk gate.

**CI workflow fix — SBOM generation job** (ticket `20260803T094146Z-ci-failure-ci-on-main-8b6f`):
> prescriptive spec — code blocks constitute implementation-ready spec, skipping refine | auto-approve: APPROVE — This is a routine CI workflow log for an SBOM generation job; no security, destructive, public-API, cross-repo, or new runtime dependency changes are indicated, so no human review is needed.

### Decision flowchart

1. Is the ticket source `ci`? → If no, this pattern does not apply.
2. Does the CI error log contain code blocks that identify the failing file(s)? → If no, route to refine LLM for investigation.
3. Is the fix mechanical and unambiguous from the log? → If no, route to refine LLM.
4. Is the change single-scoped? → If no, consider splitting into multiple tickets.
5. All yes → Use `prescriptive spec`; skip refine LLM and route to implement.

### Relationship to other boilerplate files

- **`triage-skip-boilerplate.md`**: Both skip the refine LLM, but for different reasons. `triage SKIP` applies when the draft is already a complete, implementation-ready spec with exact file paths. `prescriptive spec` applies when the CI error log itself serves as the spec — the implement agent interprets the log to determine the fix.

- **`maintenance-triage-boilerplate.md`**: Covers a different CI path — spawned `ci_fix_dependency` tickets that are out of scope for a parent ticket, using action verbs (`fork_repo`, `noop`, `notify`). `prescriptive spec` covers direct `ci`-source tickets filed by the CI pipeline for failures on main.

- **`mechanical-fastpath-boilerplate.md`**: Covers deterministic periodic-agent sources (`agent_check`, `audit`, etc.). `ci` is NOT a deterministic periodic agent — it is an event-driven source triggered by CI pipeline failures.

- **`auto-approve-boilerplate.md`**: The auto-approve justification within `prescriptive spec` uses the change-type-based templates (CI workflow), not the source-based templates (which are for deterministic periodic agents only).
