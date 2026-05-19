# Security Policy

## Scope

BOS Platform is research software backing a peer-reviewed
manuscript. The security model assumes:

- Operator-trusted local execution (typed REST endpoints +
  LangGraph agent + frontend visualisations).
- No production-grade authentication / authorisation layer.
- No production-grade rate-limiting or DoS protection.
- No multi-tenant isolation stress testing at production load.

If you are evaluating BOS Platform for deployment beyond
single-operator research use, treat the software as alpha-
grade infrastructure. The deferred items above are Phase G
roadmap (`_reports/PHASE_B_HANDOFF_FOR_PAPER1_SUBMISSION.md`).

## Reporting a vulnerability

If you discover a security vulnerability in BOS Platform,
please report it privately. **Do not open a public GitHub
issue for security reports.**

- Email: exergyleizhou@gmail.com
- Subject prefix: `[SECURITY]`
- Expected first response: within 7 calendar days.

Please include:

- The version (tag or commit hash) you observed the issue on.
- A minimal reproducer (script, request, or attack vector
  description).
- Your assessment of severity and exploitability.
- Whether you are willing to be credited in the fix
  changelog.

## Disclosure timeline

Once a vulnerability is confirmed:

1. We aim to acknowledge within 7 days.
2. We aim to land a fix within 30 days for critical
   vulnerabilities, 90 days for non-critical.
3. We will coordinate public disclosure with you; default
   embargo is 90 days from initial report unless mutually
   adjusted.
4. The fix will be released in a numbered patch release with
   credit to you in the changelog (if you wish to be
   credited).

## Scope of accepted reports

We accept reports on:

- Code execution / injection in the REST surface or agent.
- Unauthorised data access in the multi-tenant generated
  directories (`backend/generated/`).
- Dependency vulnerabilities affecting our pinned set.
- Audit-chain bypass (e.g. mechanisms that allow the paper-
  SHA gate or OpenAPI drift gate to be silently disabled).

We do not accept reports on:

- Issues requiring operator-level write access to the
  repository (the operator is trusted by definition).
- Issues in third-party services we link to (Zenodo, OSF,
  GitHub itself).
- Performance / DoS issues at non-realistic load; Phase G
  roadmap will add production-grade rate-limiting.
- "Best practice" critiques unaccompanied by a concrete
  attack vector.

## Audit chain integrity

Because BOS Platform backs a peer-reviewed manuscript, any
security report that affects the audit chain — the paper-SHA
pin, the OpenAPI snapshot, the engine `SCHEMA_VERSION`
constants, or the test suite that gates them — will be treated
with the same priority as a critical code execution
vulnerability.

The audit chain is documented in `_reports/PAPER_PINNING.md`
and `_reports/PHASE_B_PLAN.md` §1.

## Acknowledgements

Security researchers who responsibly report vulnerabilities
will be credited in:

- The fix's commit message.
- The release notes for the patched version.
- A `SECURITY-CREDITS.md` file (added on first acknowledgement).

Thank you for helping keep BOS Platform's audit chain honest.
