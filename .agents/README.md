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
- `skills/gstack-bos-director/SKILL.md`
  - BOS delivery lead that adapts gstack's think -> plan -> build -> review ->
    test -> ship -> reflect loop for Codex
- `skills/tbc-autonomy-loop/SKILL.md`
  - continuous autonomy layer that adapts TheBotCompany's strategy ->
    execution -> verification loop for Codex

## Local workflow skills
- `skills/bos-systematic-debugging/SKILL.md`
  - BOS-native debugging discipline for runtime, verification, provider, and branch failures
- `skills/bos-verification-gate/SKILL.md`
  - keeps review, verification, and completion claims explicitly separated
- `skills/bos-task-planning/SKILL.md`
  - turns broad BOS work into stable task packets before execution fans out
- `skills/bos-subagent-execution/SKILL.md`
  - BOS-native slice dispatch and aggregate handoff for executor/recovery work

## Research notes
- `research/ouro-looped-reasoning-adoption.md`
  - BOS-specific adoption decision for `arXiv:2510.25741`
  - absorbs adaptive loop depth, convergence exits, and evidence-backed learning
    while explicitly rejecting architecture cosplay

## What the source pack did not contain
The source zip contained:
- one repository-level `AGENTS.md`
- one skill: `bos-audit`

It did not contain standalone worker profiles, sub-agent configs, or additional
skill packs. In this repo, the "agents" portion is therefore represented by the
root `AGENTS.md`, plus the local `gstack-bos-director` skill added to drive
end-to-end BOS progress.

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

Use `skills/gstack-bos-director/SKILL.md` when work needs:
- next-slice selection,
- roadmap-to-implementation momentum,
- end-to-end BOS delivery across planning, coding, review, testing, and closeout,
- or a gstack-style operating loop without Claude-specific runtime dependencies.

Use `skills/tbc-autonomy-loop/SKILL.md` when work needs:
- self-evaluation and self-correction inside the same Codex turn,
- fewer repeated "continue" prompts from the human,
- milestone-style execution with strict re-verification before stopping.

Use `skills/bos-systematic-debugging/SKILL.md` when work needs:
- failure classification,
- evidence-first debugging,
- root-cause isolation before recovery or retries.

Use `skills/bos-verification-gate/SKILL.md` when work needs:
- completion gating,
- explicit verification-next handoff,
- recovery after failed verification.

Use `skills/bos-task-planning/SKILL.md` when work needs:
- tighter task packets,
- better acceptance criteria,
- stable routing across maintenance and replay.

Use `skills/bos-subagent-execution/SKILL.md` when work needs:
- bounded parallel executor slices,
- aggregate reviewer packets,
- explicit failed-slice recovery.

## Superpowers alignment
These four local workflow skills are the repository's BOS-native absorption of the
most useful `obra/superpowers` ideas:
- systematic debugging
- verification before completion
- writing plans
- subagent-driven development

They are intentionally adapted into BOS terms instead of being copied as a second,
parallel runtime. The runtime layer stays local to BOS Code; the borrowed value is
workflow discipline.

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
