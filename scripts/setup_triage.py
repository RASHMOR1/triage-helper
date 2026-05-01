#!/usr/bin/env python3
"""Build setup artifacts for audit finding triage."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


VERSION = "1.0"

FINDING_ID_RE = re.compile(
    r"(?<![A-Za-z0-9])((?:H|M|L|I|G|NC|QA|R|C|S|A)-?\d{1,4})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

DOC_EXTS = {".md", ".mdx", ".rst", ".txt", ".adoc"}
SOURCE_EXTS = {
    ".sol",
    ".vy",
    ".rs",
    ".go",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".kt",
    ".cs",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".move",
}
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".cache",
    ".next",
    ".nuxt",
    ".turbo",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "out",
    "cache",
    "artifacts",
    "broadcast",
    "coverage",
    "typechain",
    "typechain-types",
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "but",
    "by",
    "can",
    "cannot",
    "could",
    "does",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "must",
    "not",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "their",
    "then",
    "there",
    "this",
    "to",
    "via",
    "when",
    "where",
    "which",
    "will",
    "with",
    "would",
}


def canonical_id(value: str) -> str:
    match = re.match(r"^([A-Za-z]+)-?0*(\d+)$", value.strip())
    if not match:
        return value.strip().upper()
    return f"{match.group(1).upper()}-{int(match.group(2))}"


def display_id(value: str) -> str:
    match = re.match(r"^([A-Za-z]+)-?(\d+)$", value.strip())
    if not match:
        return value.strip().upper()
    return f"{match.group(1).upper()}-{match.group(2)}"


def safe_read_text(path: Path, max_bytes: int = 1_000_000) -> str:
    data = path.read_bytes()[:max_bytes]
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def fetch_url(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "triage-helper/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        encoding = "utf-8"
        if "charset=" in content_type:
            encoding = content_type.split("charset=", 1)[1].split(";", 1)[0].strip()
        return response.read(1_000_000).decode(encoding, errors="replace")


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> set[str]:
    tokens = set()
    for raw in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", text):
        token = raw.lower()
        if token not in STOPWORDS and not token.isdigit():
            tokens.add(token)
    return tokens


def extract_identifiers(text: str) -> set[str]:
    identifiers = set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", text))
    identifiers.update(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*\(\))", text))
    identifiers.update(re.findall(r"\b([A-Z][A-Za-z0-9_]{3,})\b", text))
    return {item[:-2] if item.endswith("()") else item for item in identifiers}


def line_number_at(lines: list[str], index: int) -> int:
    return max(1, min(len(lines), index + 1))


def clean_title(line: str, finding_id: str) -> str:
    title = HEADING_RE.sub(r"\2", line).strip()
    title = re.sub(r"^\[?" + re.escape(finding_id) + r"\]?", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^[\s:.\-\]\[]+", "", title)
    return title.strip() or finding_id


def fallback_title(section_lines: list[str], finding_id: str) -> str:
    for line in section_lines[:8]:
        stripped = line.strip()
        if not stripped:
            continue
        if FINDING_ID_RE.search(stripped):
            title = clean_title(stripped, finding_id)
            if title and title != finding_id:
                return title
        if len(stripped) < 160 and not stripped.startswith("|"):
            return stripped.strip("# ")
    return finding_id


def parse_findings(findings_file: Path) -> list[dict]:
    text = safe_read_text(findings_file, max_bytes=5_000_000)
    lines = text.splitlines()
    starts: list[tuple[int, str, str]] = []

    for index, line in enumerate(lines):
        stripped = line.strip()
        heading = HEADING_RE.match(stripped)
        id_match = FINDING_ID_RE.search(stripped)
        starts_like_section = bool(heading) or bool(re.match(r"^\[?(?:H|M|L|I|G|NC|QA|R|C|S|A)-?\d{1,4}\]?\b", stripped, re.I))
        if id_match and starts_like_section:
            found_id = display_id(id_match.group(1))
            starts.append((index, found_id, clean_title(stripped, id_match.group(1))))

    if not starts:
        starts = [(0, "F-1", "Finding 1")]

    findings = []
    seen: Counter[str] = Counter()
    for offset, (start_index, found_id, title) in enumerate(starts):
        end_index = starts[offset + 1][0] if offset + 1 < len(starts) else len(lines)
        section_lines = lines[start_index:end_index]
        content = "\n".join(section_lines).strip()
        if not content:
            continue

        normalized_id = canonical_id(found_id)
        seen[normalized_id] += 1
        unique_id = normalized_id if seen[normalized_id] == 1 else f"{normalized_id}.{seen[normalized_id]}"
        title = title if title and title != found_id else fallback_title(section_lines, found_id)
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        severity = normalized_id.split("-", 1)[0] if "-" in normalized_id else "UNKNOWN"
        tokens = sorted(tokenize(title + "\n" + content))
        identifiers = sorted(extract_identifiers(content))

        findings.append(
            {
                "id": display_id(found_id),
                "canonical_id": normalized_id,
                "unique_id": unique_id,
                "title": title,
                "severity": severity,
                "start_line": line_number_at(lines, start_index),
                "end_line": line_number_at(lines, max(start_index, end_index - 1)),
                "content_hash": content_hash,
                "content": content,
                "tokens": tokens,
                "identifiers": identifiers,
            }
        )
    return findings


def should_skip(path: Path, root: Path, include_deps: bool) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    parts = set(rel.parts)
    if include_deps:
        return bool(parts & (IGNORED_DIRS - {"node_modules"}))
    return bool(parts & IGNORED_DIRS)


def iter_repo_files(root: Path, include_deps: bool = False) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, root, include_deps):
            continue
        yield path


def clean_comment(raw: str) -> str:
    text = raw
    text = re.sub(r"^\s*/\*\*?", "", text)
    text = re.sub(r"\*/\s*$", "", text)
    cleaned = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(///|//|#|--|/\*+|\*)\s?", "", line)
        cleaned.append(line.rstrip())
    return "\n".join(cleaned).strip()


def extract_comments(text: str, suffix: str) -> str:
    blocks: list[str] = []
    if suffix in {".sol", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".cs", ".c", ".cc", ".cpp", ".h", ".hpp", ".rs", ".go"}:
        patterns = [
            r"/\*\*[\s\S]*?\*/",
            r"(?m)^\s*///.*(?:\n\s*///.*)*",
            r"(?m)^\s*//\s*(?:@notice|@dev|TODO|Invariant|Assumption|Spec|NOTE).*$",
        ]
    elif suffix == ".py":
        patterns = [
            r'"""[\s\S]*?"""',
            r"'''[\s\S]*?'''",
            r"(?m)^\s*#\s*(?:TODO|Invariant|Assumption|Spec|NOTE).*$",
        ]
    else:
        patterns = [r"(?m)^\s*(?:#|--)\s*(?:TODO|Invariant|Assumption|Spec|NOTE).*$"]

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            comment = clean_comment(match.group(0).strip("\"'"))
            if len(comment) >= 20:
                blocks.append(comment)
    return "\n\n".join(blocks)


def headings(text: str) -> list[str]:
    values = []
    for line in text.splitlines():
        match = HEADING_RE.match(line.strip())
        if match:
            values.append(match.group(2).strip())
        if len(values) >= 12:
            break
    return values


def excerpt(text: str, max_chars: int = 500) -> str:
    compact = normalize_ws(text)
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def collect_local_doc(path: Path, source: str, repo_root: Path | None = None) -> dict | None:
    if path.stat().st_size > 2_000_000:
        return None
    text = safe_read_text(path)
    if path.suffix.lower() in DOC_EXTS:
        body = text
        kind = "document"
    elif path.suffix.lower() in SOURCE_EXTS:
        body = extract_comments(text, path.suffix.lower())
        kind = "source-comments"
        if not body:
            return None
    else:
        return None

    if not normalize_ws(body):
        return None

    display_path = str(path)
    if repo_root is not None:
        try:
            display_path = str(path.relative_to(repo_root))
        except ValueError:
            pass

    return {
        "source": source,
        "kind": kind,
        "path": str(path.resolve()),
        "display_path": display_path,
        "headings": headings(body),
        "excerpt": excerpt(body),
        "tokens": sorted(tokenize(body)),
        "identifiers": sorted(extract_identifiers(body)),
    }


def collect_docs(repo_root: Path, external_docs: list[str], include_deps: bool) -> list[dict]:
    docs: list[dict] = []
    seen_paths: set[str] = set()

    for path in iter_repo_files(repo_root, include_deps=include_deps):
        if path.suffix.lower() not in DOC_EXTS and path.suffix.lower() not in SOURCE_EXTS:
            continue
        doc = collect_local_doc(path, "repo", repo_root)
        if doc:
            seen_paths.add(doc["path"])
            docs.append(doc)

    for raw in external_docs:
        value = raw.strip()
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            try:
                body = fetch_url(value)
            except Exception as exc:  # pragma: no cover - network varies
                docs.append(
                    {
                        "source": "external",
                        "kind": "url-error",
                        "path": value,
                        "display_path": value,
                        "headings": [],
                        "excerpt": f"Could not fetch URL during setup: {exc}",
                        "tokens": [],
                        "identifiers": [],
                    }
                )
                continue
            docs.append(
                {
                    "source": "external",
                    "kind": "url",
                    "path": value,
                    "display_path": value,
                    "headings": headings(body),
                    "excerpt": excerpt(body),
                    "tokens": sorted(tokenize(body)),
                    "identifiers": sorted(extract_identifiers(body)),
                    "fetched_text": body[:80_000],
                }
            )
            continue

        path = Path(value).expanduser().resolve()
        if path.is_dir():
            for child in path.rglob("*"):
                if not child.is_file() or child.suffix.lower() not in DOC_EXTS | SOURCE_EXTS:
                    continue
                doc = collect_local_doc(child, "external")
                if doc and doc["path"] not in seen_paths:
                    seen_paths.add(doc["path"])
                    docs.append(doc)
        elif path.is_file():
            doc = collect_local_doc(path, "external")
            if doc and doc["path"] not in seen_paths:
                seen_paths.add(doc["path"])
                docs.append(doc)
        else:
            docs.append(
                {
                    "source": "external",
                    "kind": "missing",
                    "path": value,
                    "display_path": value,
                    "headings": [],
                    "excerpt": "Path did not exist during setup.",
                    "tokens": [],
                    "identifiers": [],
                }
            )

    return docs


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def pair_score(left: dict, right: dict) -> tuple[float, list[str], list[str]]:
    left_tokens = set(left.get("tokens", []))
    right_tokens = set(right.get("tokens", []))
    left_identifiers = {item.lower() for item in left.get("identifiers", [])}
    right_identifiers = {item.lower() for item in right.get("identifiers", [])}

    token_score = jaccard(left_tokens, right_tokens)
    identifier_score = jaccard(left_identifiers, right_identifiers)
    title_score = jaccard(tokenize(left.get("title", "")), tokenize(right.get("title", "")))
    score = (0.62 * token_score) + (0.28 * identifier_score) + (0.10 * title_score)

    shared_terms = sorted((left_tokens & right_tokens), key=lambda item: (len(item), item), reverse=True)[:12]
    shared_identifiers = sorted(left_identifiers & right_identifiers)[:12]
    if len(shared_identifiers) >= 2:
        score += 0.08
    if title_score >= 0.45:
        score += 0.08
    return min(score, 1.0), shared_terms, shared_identifiers


def union_find(items: list[str]):
    parent = {item: item for item in items}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    return parent, find, union


def group_findings(findings: list[dict]) -> dict:
    ids = [finding["unique_id"] for finding in findings]
    parent, find, union = union_find(ids)
    duplicate_pairs = []
    related_pairs = []

    by_id = {finding["unique_id"]: finding for finding in findings}
    for index, left in enumerate(findings):
        for right in findings[index + 1 :]:
            score, shared_terms, shared_identifiers = pair_score(left, right)
            pair = {
                "left": left["unique_id"],
                "right": right["unique_id"],
                "score": round(score, 3),
                "shared_terms": shared_terms,
                "shared_identifiers": shared_identifiers,
            }
            if score >= 0.42:
                duplicate_pairs.append(pair)
                union(left["unique_id"], right["unique_id"])
            elif score >= 0.22 or len(shared_identifiers) >= 3:
                related_pairs.append(pair)
                union(left["unique_id"], right["unique_id"])

    clusters: defaultdict[str, list[str]] = defaultdict(list)
    for item in ids:
        clusters[find(item)].append(item)

    related_groups = []
    standalone = []
    for group_ids in clusters.values():
        ordered = sorted(group_ids, key=lambda item: ids.index(item))
        if len(ordered) == 1:
            standalone.append(ordered[0])
            continue
        common_terms = set(by_id[ordered[0]].get("tokens", []))
        common_identifiers = {item.lower() for item in by_id[ordered[0]].get("identifiers", [])}
        for item in ordered[1:]:
            common_terms &= set(by_id[item].get("tokens", []))
            common_identifiers &= {identifier.lower() for identifier in by_id[item].get("identifiers", [])}
        related_groups.append(
            {
                "ids": ordered,
                "common_terms": sorted(common_terms, key=lambda term: (len(term), term), reverse=True)[:12],
                "common_identifiers": sorted(common_identifiers)[:12],
            }
        )

    duplicate_groups = []
    duplicate_parent, duplicate_find, duplicate_union = union_find(ids)
    for pair in duplicate_pairs:
        duplicate_union(pair["left"], pair["right"])
    duplicate_clusters: defaultdict[str, list[str]] = defaultdict(list)
    for item in ids:
        duplicate_clusters[duplicate_find(item)].append(item)
    for group_ids in duplicate_clusters.values():
        if len(group_ids) > 1:
            duplicate_groups.append(sorted(group_ids, key=lambda item: ids.index(item)))

    return {
        "duplicate_groups": duplicate_groups,
        "related_groups": related_groups,
        "standalone": standalone,
        "duplicate_pairs": duplicate_pairs,
        "related_pairs": related_pairs,
    }


def score_doc_for_finding(doc: dict, finding: dict) -> tuple[float, list[str], list[str]]:
    doc_tokens = set(doc.get("tokens", []))
    doc_identifiers = {item.lower() for item in doc.get("identifiers", [])}
    finding_tokens = set(finding.get("tokens", []))
    finding_identifiers = {item.lower() for item in finding.get("identifiers", [])}
    matched_terms = sorted(finding_tokens & doc_tokens)[:16]
    matched_identifiers = sorted(finding_identifiers & doc_identifiers)[:16]
    if not matched_terms and not matched_identifiers:
        return 0.0, [], []
    score = (len(matched_terms) / math.sqrt(max(1, len(finding_tokens)))) + (2.0 * len(matched_identifiers))
    return score, matched_terms, matched_identifiers


def add_doc_hits(findings: list[dict], docs: list[dict]) -> None:
    for finding in findings:
        hits = []
        for doc in docs:
            score, matched_terms, matched_identifiers = score_doc_for_finding(doc, finding)
            if score <= 0:
                continue
            hits.append(
                {
                    "path": doc["path"],
                    "display_path": doc["display_path"],
                    "source": doc["source"],
                    "kind": doc["kind"],
                    "score": round(score, 3),
                    "matched_terms": matched_terms,
                    "matched_identifiers": matched_identifiers,
                    "excerpt": doc["excerpt"],
                }
            )
        finding["doc_hits"] = sorted(hits, key=lambda item: item["score"], reverse=True)[:8]


def write_related_markdown(path: Path, context: dict) -> None:
    findings_by_id = {finding["unique_id"]: finding for finding in context["findings"]}
    lines = [
        "# Related Findings",
        "",
        f"Generated: {context['generated_at']}",
        f"Findings file: `{context['findings_file']}`",
        f"Repo root: `{context['repo_root']}`",
        "",
        "This file is a setup artifact for triage. Treat groups as candidates and revise them with code-aware judgment before making final calls.",
        "",
    ]

    duplicate_groups = context["groups"]["duplicate_groups"]
    lines.append("## Duplicate-like Groups")
    lines.append("")
    if duplicate_groups:
        for index, group in enumerate(duplicate_groups, 1):
            lines.append(f"### D{index}")
            for item in group:
                finding = findings_by_id[item]
                lines.append(f"- `{finding['id']}` {finding['title']}")
            lines.append("")
    else:
        lines.append("No high-similarity duplicate groups detected by the setup pass.")
        lines.append("")

    lines.append("## Related Groups")
    lines.append("")
    related_groups = context["groups"]["related_groups"]
    if related_groups:
        for index, group in enumerate(related_groups, 1):
            lines.append(f"### R{index}")
            if group["common_terms"] or group["common_identifiers"]:
                terms = ", ".join(f"`{term}`" for term in group["common_terms"][:8])
                identifiers = ", ".join(f"`{term}`" for term in group["common_identifiers"][:8])
                evidence = ", ".join(part for part in (terms, identifiers) if part)
                lines.append(f"Shared signals: {evidence}")
                lines.append("")
            for item in group["ids"]:
                finding = findings_by_id[item]
                lines.append(f"- `{finding['id']}` {finding['title']}")
            lines.append("")
    else:
        lines.append("No related groups detected by the setup pass.")
        lines.append("")

    lines.append("## Standalone Findings")
    lines.append("")
    standalone = context["groups"]["standalone"]
    if standalone:
        for item in standalone:
            finding = findings_by_id[item]
            lines.append(f"- `{finding['id']}` {finding['title']}")
    else:
        lines.append("No standalone findings detected.")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_docs_index(path: Path, context: dict) -> None:
    lines = [
        "# Triage Documentation Index",
        "",
        f"Generated: {context['generated_at']}",
        "",
        "## Inputs",
        "",
        f"- Repo root: `{context['repo_root']}`",
        f"- Findings file: `{context['findings_file']}`",
    ]
    if context["external_docs"]:
        for doc in context["external_docs"]:
            lines.append(f"- External docs: `{doc}`")
    else:
        lines.append("- External docs: none provided")
    lines.extend(["", "## Indexed Documentation", ""])

    if not context["docs"]:
        lines.append("No docs, NatSpec, or comment blocks were indexed.")
    else:
        for doc in context["docs"]:
            lines.append(f"- `{doc['display_path']}` ({doc['source']}, {doc['kind']})")
            if doc.get("headings"):
                lines.append(f"  - headings: {', '.join(doc['headings'][:5])}")
    lines.extend(["", "## Top Documentation Hits By Finding", ""])
    for finding in context["findings"]:
        lines.append(f"### `{finding['id']}` {finding['title']}")
        hits = finding.get("doc_hits", [])
        if not hits:
            lines.append("- No doc hits found.")
        for hit in hits[:5]:
            labels = []
            if hit["matched_identifiers"]:
                labels.append("identifiers: " + ", ".join(f"`{value}`" for value in hit["matched_identifiers"][:5]))
            if hit["matched_terms"]:
                labels.append("terms: " + ", ".join(f"`{value}`" for value in hit["matched_terms"][:5]))
            suffix = f" ({'; '.join(labels)})" if labels else ""
            lines.append(f"- `{hit['display_path']}` score {hit['score']}{suffix}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def build_context(args: argparse.Namespace) -> dict:
    repo_root = Path(args.repo).expanduser().resolve()
    findings_file = Path(args.findings).expanduser().resolve()
    if not repo_root.is_dir():
        raise SystemExit(f"Repo root is not a directory: {repo_root}")
    if not findings_file.is_file():
        raise SystemExit(f"Findings file does not exist: {findings_file}")

    output_dir = Path(args.output).expanduser().resolve() if args.output else findings_file.parent / "triage-helper-output"
    output_dir.mkdir(parents=True, exist_ok=True)

    external_docs = args.external_doc or []
    findings = parse_findings(findings_file)
    docs = collect_docs(repo_root, external_docs, include_deps=args.include_deps)
    add_doc_hits(findings, docs)
    groups = group_findings(findings)

    return {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "findings_file": str(findings_file),
        "external_docs": external_docs,
        "output_dir": str(output_dir),
        "findings_count": len(findings),
        "docs_count": len(docs),
        "findings": findings,
        "docs": docs,
        "groups": groups,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set up triage artifacts from a repo and findings.md.")
    parser.add_argument("--repo", required=True, help="Path to the repository under triage.")
    parser.add_argument("--findings", required=True, help="Path to the markdown findings file.")
    parser.add_argument(
        "--external-doc",
        action="append",
        default=[],
        help="Optional external documentation path, directory, or URL. Repeat for multiple inputs.",
    )
    parser.add_argument("--output", help="Output directory. Defaults to findings-file sibling triage-helper-output/.")
    parser.add_argument("--include-deps", action="store_true", help="Include dependency directories during indexing.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    context = build_context(args)
    output_dir = Path(context["output_dir"])

    context_path = output_dir / "triage-context.json"
    related_path = output_dir / "related-findings.md"
    docs_path = output_dir / "docs-index.md"

    context_path.write_text(json.dumps(context, indent=2), encoding="utf-8")
    write_related_markdown(related_path, context)
    write_docs_index(docs_path, context)

    print(f"Indexed {context['findings_count']} findings and {context['docs_count']} documentation sources.")
    print(f"Wrote context: {context_path}")
    print(f"Wrote related findings: {related_path}")
    print(f"Wrote docs index: {docs_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
