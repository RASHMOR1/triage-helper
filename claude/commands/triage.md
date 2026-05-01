---
description: Triage one audit finding by ID
allowed-tools: Bash(python3:*), Bash(find:*), Bash(rg:*), Bash(npx hardhat test:*), Bash(forge test:*), Read, Glob, Grep
---

Triage one audit/security finding using Triage Helper.

Finding ID and optional extra instructions:

`$ARGUMENTS`

Triage Helper directory:

`{{TRIAGE_HELPER_DIR}}`

Instructions:

1. Read `{{TRIAGE_HELPER_DIR}}/SKILL.md`.
2. Read `{{TRIAGE_HELPER_DIR}}/references/triage-method.md`.
3. Locate `triage-helper-output/triage-context.json`. If setup has not been run, switch to setup behavior from `{{TRIAGE_HELPER_DIR}}/claude/commands/triage-setup.md`.
4. Run:

```bash
python3 {{TRIAGE_HELPER_DIR}}/scripts/lookup_finding.py <finding-id> --context <triage-context.json>
```

5. Use the lookup packet only as a starting point. Directly inspect the relevant finding text, docs, prior audit/known-issue notes, NatSpec/comments, and implementation.
6. Give the final triage response in exactly this order:

## Duplicate Status

State `Duplicate`, `Near-duplicate`, `Related`, or `No duplicate detected`. Name matching finding IDs and explain the root-cause relationship. If setup missed a duplicate but direct review finds one, say so.

## Finding Explanation

Explain the issue in simple terms for a smart reader who may not know this protocol yet. Do not make it brief or auditor-shorthand, and do not limit the length if more explanation is needed. Define the moving parts, explain what normally should happen, what goes wrong, and why it matters. Name the affected path and impact, but translate protocol jargon into everyday language when possible.

## Docs/Spec Check

Check external docs, repo docs, prior audit reports, known-issue files, uncovered-attack-vector docs, NatSpec, and comments for:

- the same or similar finding
- broader related issues
- intended behavior
- related invariants
- caveats that weaken or qualify the exploit path

Say clearly whether docs are silent, ambiguous, partially mention it, or identify a broader related issue. Cite paths and short snippets when useful.

## Numerical Example

Start with a short context paragraph that explains what the example is demonstrating, what the protocol/module is supposed to measure, and what goes wrong. Then use concrete numbers and a human-readable walkthrough with simple roles such as `user`, `depositor`, `withdrawer`, `attacker`, `keeper`, or named actors only when names make the example clearer. Do not repeat names unnecessarily. Prefer labels like `Initial state`, `What the protocol should count`, `What the code counts`, and `Why it matters`. Put important arithmetic on its own lines so calculations stand out instead of becoming a wall of text. Avoid dumping formulas or PoC variables without explaining them. Show only the arithmetic needed to understand the mechanism, and explain what each number means in plain language. Include important nuance about who is harmed, what is bounded, and whether the report overstates anything.

## Protocol Analysis And Verdict

Trace the implementation and decision together in one section. Cover entrypoints, state changes, invariants, guards, rounding, permissions, edge cases, tests, and counterpoints. Include caveats when relevant.

End with:

```text
Preliminary decision: Valid/Invalid/Partially valid/Needs more information
Confidence: Low/Medium/High
Why: <main reason from code/spec>
Assumptions: <deployment/user/role/oracle/token assumptions>
Notes: <duplicates, severity adjustment, caveats, tests, or docs mismatch>
```

Be unbiased. Try to prove and disprove the finding before deciding.
