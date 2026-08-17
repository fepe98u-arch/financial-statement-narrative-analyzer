# CLAUDE.md — Financial Statement Narrative Analyzer

You're my AI new hire. I'm the boss and I'm a non-coder. I decide what needs
to happen — you figure out how to make it happen and execute it. Explain
things the way you'd explain them to a smart boss who's never touched a
terminal.

Full requirements live in **[PROJECT_SPEC.md](PROJECT_SPEC.md)** — read it
before making any architectural decision. This file is the condensed,
always-loaded version of the rules that must never be violated.

---

## What this project is

A Windows-only desktop app that helps auditors and analysts spot
cross-account financial patterns worth reviewing ("inventory down, but
structures/machinery/borrowings up — why?") and, later, pull broad public
evidence about a company without ever leaking private analysis externally.

## The one rule that overrides everything else

**Never send private data outside the machine.**

The codebase is split into two zones and they never talk to each other
directly:

- **PRIVATE ANALYSIS ZONE** — financial statements, amounts, detected
  patterns, historical comparisons, investigation questions, human review
  notes, local AI analysis. Local-only, always.
- **PUBLIC DATA COLLECTION ZONE** — fetches already-public info (company
  name, DART corp_code, date range) from the internet. Nothing else goes out.

Outbound-allowed fields: `public_company_name`, `public_company_identifier`,
`dart_corp_code`, `date_from`, `date_to`, `page`, `page_size`, `topic_keyword`,
and the minimum technical parameters a public API needs.

`topic_keyword` (added 2026-08-17, explicit owner decision — the one narrow,
deliberate exception to "no exceptions" below) is exactly ONE bare
account-name-level term per request (e.g. "이자비용", "지분법손익"), drawn
only from the pre-approved list in
`app/analysis/investigation_questions.py`'s `search_keyword_for()` — never
free text, never picked ad hoc by a caller. It must never carry a direction
("증가"/"감소"), a number, a full investigation question, or a pattern
name/score — see PROJECT_SPEC.md section 25 for the full rationale and the
`test_search_keywords_contain_no_directional_or_judgment_words` test that
guards the vocabulary. The owner explicitly accepted the residual risk that
"[company] + [account name]" as a search reveals which account is under
scrutiny (even without revealing what was found), in exchange for a much
narrower/more relevant search — Naver's News Search API has no date-range
filter and caps at 1,000 results, so a bare company-name search for a
heavily-covered company can exhaust that budget in a few days; adding one
account-name keyword cuts daily volume enough to reach a full audit year.

Outbound-forbidden, no exceptions: any financial amount, account
change-rate/direction, detected pattern, pattern score, investigation
question, internal hypothesis/summary, human review/audit comment, or any
private document content or filename. (Bare account *name* is conditionally
allowed only via `topic_keyword` above — nothing else about this list is
loosened.)

Only one module may ever perform network I/O: `public_data_collector/`
(built starting Phase 7). No other file imports `requests`, `httpx`,
`urllib`, `aiohttp`, or `socket`. Nothing auto-connects to the internet on
startup — public data collection only runs when I click a button for it, and
only after a first-run consent dialog.

## Tech stack

Use: Python, PySide6, Polars, PostgreSQL (local, `127.0.0.1` only —
never cloud), SQLAlchemy, psycopg, numpy, scikit-learn, sentence-transformers,
rapidfuzz, pytest. PyArrow/Parquet if needed.

Never use: Streamlit, Flask, Django, any localhost web app, SQLite, cloud
database/storage, or any external LLM/embedding API (OpenAI, Claude, Gemini,
etc.) — including for local AI features, which must run from locally-stored
models only, never auto-downloaded.

## Build in phases, don't jump ahead

Phase order is fixed in [PROJECT_SPEC.md §57](PROJECT_SPEC.md#57-개발-순서).
We are currently on **Phase 1**: desktop shell, security status bar,
synthetic ABC Manufacturing data, Polars loader, dashboard. No network code
of any kind yet, even scaffolding.

Don't build ahead into later phases just because it seems convenient — ask
first if something looks like it needs a Phase-2+ piece.

## Data

Only synthetic data (`ABC Manufacturing`, `Sample Electronics`, etc.) is
ever used in this repo, in dev, or in tests — never a real client's
financials, audit workpapers, or internal documents. See
[PROJECT_SPEC.md §5](PROJECT_SPEC.md#5-개발-단계-데이터-보안).

This project folder itself lives under OneDrive. That's fine while we only
handle synthetic data, but once real data paths or a real Postgres instance
enter the picture (Phase 4+), flag it — the app is supposed to warn about
cloud-sync folders (§44), not silently use one.

## Environment setup — ask first, don't just run it

I'm a coding beginner. Before installing anything or touching the
environment:

- Don't install or reinstall Python.
- Don't recreate the virtual environment repeatedly — set it up once, reuse it.
- Don't auto-install PostgreSQL or auto-download AI models.
- Don't change system settings or the firewall.
- Don't loop-retry a hung command.
- Don't launch background processes casually.

If something needs installing: explain what, why, and (if I should run it
myself) the exact command — before running it.

## Git

No `git` or GitHub actions (commits, branches, pushes, PRs) unless I
explicitly ask for that specific action.

## Reporting back

- When you present a plan, say exactly which files you'll create or change.
- When something breaks, explain what happened in plain language first, then
  fix it — and if you couldn't fix it or verify it runs, say so plainly
  instead of claiming success.
- No jargon dumps. If I need to decide something, give me what I need to
  decide, not a CS lecture.

## Security discipline

- Secrets (`DART_API_KEY`, `DATABASE_URL`, etc.) live only in `.env` — never
  in code, logs, or this file. `.env`, `credentials.json`, `token.json` stay
  in `.gitignore`.
- Logs never contain full financial statements/amounts, full investigation
  questions, full human review text, API keys, or DB passwords — see
  [PROJECT_SPEC.md §43](PROJECT_SPEC.md#43-로그-보안).
- Before any phase that touches the network (Phase 7+), re-read
  [PROJECT_SPEC.md §21-38](PROJECT_SPEC.md#21-public-data-collector의-입력을-강제-제한)
  for the Allowlist/Network Guard/Numeric Leakage Guard requirements.
- After Phase 7+, a source-wide network audit (§54) must confirm no
  unintended network code exists outside `public_data_collector/`.

## Files

```
PROJECT_SPEC.md     # Full requirements — the source of truth for design decisions
app/                 # PySide6 application code (current: Phase 1 only)
.tmp/                # Scratch space, incl. generated synthetic data. Disposable.
.env                 # Secrets. ONLY place for sensitive data.
credentials.json     # OAuth credentials, if ever needed (gitignored)
token.json           # OAuth token, if ever needed (gitignored)
```
