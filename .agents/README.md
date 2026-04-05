# Codex Assets

These assets were extracted from `bos_codex_pack` and adapted for the current
`bos-pipeline-reconciled` repository on 2026-04-05.

## Imported assets
- `../AGENTS.md`
  - repository-wide Codex charter
  - defines BOS truth boundaries, invariants, and implementation priorities
- `skills/bos-audit/SKILL.md`
  - reusable skill for BOS audit hardening, release logic, and premium operator
    surfaces

## What the source pack did not contain
The source zip contained:
- one repository-level `AGENTS.md`
- one skill: `bos-audit`

It did not contain standalone worker profiles, sub-agent configs, or additional
skill packs. In this repo, the "agents" portion is therefore represented by the
root `AGENTS.md`.

## How to use these assets
Use `AGENTS.md` when work needs repository-wide guardrails such as:
- evidence boundaries,
- accounting integrity,
- release gating,
- auditability,
- premium operator UX with explicit uncertainty.

Use `skills/bos-audit/SKILL.md` when work needs a focused vertical slice such
as:
- Signal-API / Control-API contracts,
- release / reject / requalify workflows,
- audit packet generation,
- flight envelope gating,
- premium BOS dashboard or command-center surfaces.

## Best current targets in this repository
The current codebase already has dashboards, batch views, digital twin,
sustainability, audit routes, and flight logic. The highest-value follow-on
work is:

1. add typed `SignalBatch`, `ControlAPIProfile`, and `ReleaseDecision`
   contracts;
2. turn batch detail into a true Batch Command Center;
3. add a Signal Lab surface for potency, MTT, HAL, and stability;
4. make portability and requalification explicit rather than implicit;
5. connect release decisions to exportable audit packets.

## Maintenance rule
If `bos_codex_pack` is updated later, re-diff the pack before copying files.
Do not blindly overwrite local instructions if the repository has already
evolved.
