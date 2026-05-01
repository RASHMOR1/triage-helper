---
name: triage-helper
description: Audit and security finding triage workflow for repositories with a findings markdown file. Use when Codex needs to set up triage from repo plus findings.md, index optional external documentation, group duplicate or related findings, or answer commands like /triage M-24, "triage finding M-24", or "assess H-01" with duplicate status first, an explanation, docs/spec check, numerical example, and combined protocol analysis plus unbiased verdict.
---

# Triage Helper

## Overview

Use this skill to set up and run an audit-finding triage workflow for a code repository plus a markdown findings file. The workflow has two modes:

- Setup mode: identify inputs, index repo docs/NatSpec/comments plus optional external docs, group duplicate or related findings, and write setup artifacts.
- Single-finding mode: handle `/triage <finding-id>` by stating duplicate status first, explaining the finding, checking docs/specs, giving a numerical example, and combining implementation analysis with a preliminary verdict.

For detailed triage standards and decision criteria, read `references/triage-method.md` when starting single-finding analysis or when the validity call is subtle.

## Setup Mode

Run setup when the user invokes the skill for a repo that does not already have `triage-helper-output/triage-context.json`, or when they explicitly ask to re-run setup.

1. Ask the user to identify the markdown findings file if it is not already clear. Common layouts are `folder/findings.md` and `folder/repo/`.
2. Ask whether they want to provide external documentation. If they do not provide any, use only repo docs, NatSpec, and code comments as documentation.
3. Identify the repo root. If there is one obvious repository directory next to the findings file, use it; otherwise ask for the repo path.
4. Run the setup script from this skill directory:

```bash
python3 /path/to/triage-helper/scripts/setup_triage.py \
  --repo /path/to/repo \
  --findings /path/to/findings.md \
  --external-doc /optional/doc/or/dir/or/url
```

Omit `--external-doc` when the user provides none. Repeat `--external-doc` for multiple docs. Add `--output /path/to/output` only if the user wants a custom output location; otherwise the script writes next to the findings file under `triage-helper-output/`.

The setup script writes:

- `triage-context.json`: parsed findings, docs index, and machine-readable grouping hints.
- `related-findings.md`: duplicate-like and related finding groups.
- `docs-index.md`: indexed docs/NatSpec/comment sources and top doc hits by finding.

After the script runs, open `related-findings.md` and review the groups. The script uses lexical similarity and identifier overlap; refine the file when code-aware judgment clearly shows findings should be merged, split, or marked uncertain. Keep uncertain groups labeled as candidates.

## Single-Finding Mode

Use this mode when the user says `/triage M-24`, `triage M-24`, or gives any similar request with a finding ID.

1. Locate `triage-context.json`. Default to `<findings-dir>/triage-helper-output/triage-context.json`. If setup has not been run, run Setup Mode first.
2. Run the lookup script:

```bash
python3 /path/to/triage-helper/scripts/lookup_finding.py M-24 \
  --context /path/to/triage-helper-output/triage-context.json
```

3. Use the lookup packet as a starting point, not as the final answer. Open relevant finding text, docs, NatSpec/comments, prior audit notes, known-issue files, and code references directly when needed.
4. If the finding belongs to a duplicate or related group, make that the first section of the response and consider whether the same root cause affects the decision.
5. Analyze neutrally. Try to prove the finding valid and try to disprove it before deciding.

## Required Single-Finding Answer

Structure each triage response with these sections, in this order:

- Duplicate status: first line/section. State `Duplicate`, `Near-duplicate`, `Related`, or `No duplicate detected`. Name the matching finding IDs and the root-cause relationship. If setup did not auto-cluster something but code/finding review shows a match, say that explicitly.
- Finding explanation: explain the issue in simple terms for a smart reader who may not know this protocol yet. Do not make it brief or auditor-shorthand, and do not limit the length if more explanation is needed. Define the moving parts, explain what normally should happen, what goes wrong, and why it matters. Name the affected path and impact, but translate protocol jargon into everyday language when possible.
- Docs/spec check: state whether external docs, repo docs, NatSpec, comments, prior audit reports, known-issue notes, or uncovered-attack-vector docs mention this finding, a similar finding, the intended behavior, or a related invariant. Cite local paths and short snippets when helpful. Say clearly when docs are silent, ambiguous, partially mention the issue, or identify a broader related issue.
- Numerical example: start with a short context paragraph that explains what the example is demonstrating, what the protocol/module is supposed to measure, and what goes wrong. Then use a human-readable walkthrough with concrete roles such as `user`, `depositor`, `withdrawer`, `attacker`, `keeper`, or named actors only when names make the example easier. Do not repeat names unnecessarily. Prefer readable blocks like `Initial state`, `What the protocol should count`, `What the code counts`, and `Why it matters`. Put important arithmetic on its own lines so calculations stand out instead of becoming a wall of text. Avoid dumping formulas or PoC variables without explaining them. Show only the arithmetic needed to understand the mechanism, and explain what each number means in plain language.
- Protocol analysis and verdict: combine the code trace and decision in one final section. Trace entrypoints, state changes, invariants, guards, rounding, permissions, edge cases, tests, and counterpoints. Include caveats before the final decision when relevant, such as bounded impact, deployment-specific assumptions, mitigations already present, non-applicable configurations, severity limits, or ways the report overstates the issue. End the same section with `Preliminary decision: Valid/Invalid/Partially valid/Needs more information`, confidence, assumptions, and severity/duplicate notes.

Do not create a standalone `Preliminary Decision` section. The verdict belongs at the end of `Protocol analysis and verdict`.

## Decision Discipline

Do not anchor on the report's conclusion. A finding is not valid merely because it is plausible, and it is not invalid merely because docs are silent.

Use this rough evidence hierarchy:

1. Executable behavior: tests, reproductions, direct code traces.
2. Official external docs or specs provided by the user.
3. Repo docs and design docs.
4. NatSpec and code comments.
5. Naming conventions and inferred intent.

Prefer precise conditional language when the evidence is mixed. For example: "Valid if deposits can be made through X without Y check; invalid for the documented flow because Z always clamps the value first."

## Output Artifacts

During setup, write grouping artifacts in the output directory instead of inside the skill directory. During single-finding triage, do not edit the original findings file unless the user explicitly asks. If you create notes, place them in the setup output directory.

## Claude Code Support

Claude Code does not discover Codex `SKILL.md` files directly. Use the bundled installer to copy equivalent Claude Code slash commands and a subagent into Claude's supported `.claude/` layout.

For one audit/project folder:

```bash
python3 /path/to/triage-helper/scripts/install_claude_support.py \
  --scope project \
  --project-dir /path/to/audit-folder
```

For all Claude Code sessions for the current user:

```bash
python3 /path/to/triage-helper/scripts/install_claude_support.py --scope user
```

Use `--force` to overwrite existing command or agent files.

Installed Claude Code features:

- `.claude/commands/triage-setup.md` provides `/triage-setup`.
- `.claude/commands/triage.md` provides `/triage <finding-id>`.
- `.claude/agents/triage-helper.md` provides a specialized `triage-helper` subagent.

The installer replaces template paths with the absolute path to this helper folder so Claude Code can run the same setup and lookup scripts.
