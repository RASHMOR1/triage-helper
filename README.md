# Triage Helper

Triage Helper is a reusable AI-agent workflow for audit finding triage.

It is meant for audit folders shaped roughly like this:

```text
folder1/
├── repo/
└── findings.md
```

The helper sets up a local triage workspace, groups related findings, indexes docs and code comments, and then helps analyze individual findings in a consistent format.

## What It Does

During setup, it:

- asks for the findings markdown file
- asks for the repo path
- optionally accepts external docs
- indexes repo docs, NatSpec, and useful code comments
- indexes external docs if provided
- groups duplicate-like or related findings
- writes setup artifacts into `triage-helper-output/`

For single-finding triage, it helps produce:

- duplicate status first
- simple finding explanation
- docs/spec/prior-finding check
- human-understandable numerical example
- protocol analysis and verdict in one section
- caveats, assumptions, confidence, and severity notes

## Setup Output

The setup script writes:

```text
triage-helper-output/
├── triage-context.json
├── related-findings.md
└── docs-index.md
```

`related-findings.md` is the main human-readable grouping file.

`docs-index.md` shows indexed docs and likely docs hits per finding.

`triage-context.json` is used by the lookup script and AI agent workflow.

## Manual Usage

Run setup:

```bash
python3 /pashov/triage-helper/scripts/setup_triage.py \
  --repo ./repo \
  --findings ./findings.md
```

With external docs:

```bash
python3 /pashov/triage-helper/scripts/setup_triage.py \
  --repo ./repo \
  --findings ./findings.md \
  --external-doc ./docs \
  --external-doc https://example.com/protocol-docs
```

Look up one finding:

```bash
python3 /pashov/triage-helper/scripts/lookup_finding.py M-24 \
  --context ./triage-helper-output/triage-context.json
```

The lookup output is not the final triage answer. It is a focused packet the AI agent uses before reading the actual code, docs, and finding text directly.

## Codex Usage

Copy or symlink this folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -r /pashov/triage-helper ~/.codex/skills/triage-helper
```

Then invoke it from Codex:

```text
Use $triage-helper to set up triage.
```

After setup:

```text
/triage M-24
```

## Claude Code Usage

Install Claude Code support into one audit folder:

```bash
python3 /pashov/triage-helper/scripts/install_claude_support.py \
  --scope project \
  --project-dir /path/to/folder1
```

Or install for the current user:

```bash
python3 /pashov/triage-helper/scripts/install_claude_support.py --scope user
```

Claude Code commands:

```text
/triage-setup
/triage M-24
```

## Expected Triage Answer Format

Single-finding answers should use this order:

1. Duplicate Status
2. Finding Explanation
3. Docs/Spec Check
4. Numerical Example
5. Protocol Analysis And Verdict

The numerical example should explain the scenario before showing numbers. Arithmetic should be easy to scan, not buried in a wall of text.

The verdict should remain unbiased: try to validate and invalidate the finding before deciding.
