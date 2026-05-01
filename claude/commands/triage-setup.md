---
description: Set up audit finding triage for this repo
allowed-tools: Bash(python3:*), Bash(find:*), Bash(rg:*), Read, Glob, Grep
---

Set up the Triage Helper workflow for audit findings.

Triage Helper directory:

`{{TRIAGE_HELPER_DIR}}`

User arguments:

`$ARGUMENTS`

Instructions:

1. Read `{{TRIAGE_HELPER_DIR}}/SKILL.md`.
2. Identify the findings markdown file. If the user did not provide it and it is not obvious, ask for it.
3. Identify the repo root. Common layout is `<audit-folder>/repo` plus `<audit-folder>/findings.md`. If ambiguous, ask for the repo path.
4. Ask whether the user wants to provide external docs. If they provide none, use only repo docs, NatSpec, and comments.
5. Run:

```bash
python3 {{TRIAGE_HELPER_DIR}}/scripts/setup_triage.py --repo <repo> --findings <findings.md>
```

Add one `--external-doc <path-or-url>` for each external doc source.

6. After setup, open and briefly summarize:

- `triage-helper-output/related-findings.md`
- `triage-helper-output/docs-index.md`

7. Tell the user the exact `triage-context.json` path and that they can now run `/triage M-24`.
