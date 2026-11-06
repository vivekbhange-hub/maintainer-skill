---
name: maintainer-triage
description: >-
  Triages the open issues of a GitHub repo. Reads them with gh, sorts each into bug, feature,
  question, duplicate, needs-repro or stale, finds likely duplicates, and drafts labels plus a short,
  human reply for every issue. Writes a triage report first and only applies labels, comments or
  closes after the user confirms. Use when the user says "triage my issues", "go through the issue
  backlog", "which issues are duplicates", "label these issues", "help me answer open issues",
  "clean up the issue tracker", or "what needs my attention in issues".
argument-hint: "[owner/repo] [--limit N] [--label L]"
---

# Issue triage

Turn a pile of open issues into a decision list: what each issue is, what label it needs, what
to say back, and which ones are the same report twice. The maintainer reviews one report and
approves actions in bulk instead of opening fifty tabs. Nothing touches GitHub until they say so.

## Inputs

- Repo: the argument, or the current directory's remote (`gh repo view --json nameWithOwner`).
- Scope: default is open issues, newest 100. Respect `--limit` and `--label` if given.
- Requires `gh` authenticated. If `gh auth status` fails, stop and tell the user to run `gh auth login`.

## Steps

1. **Collect.** Run, in the repo or with `-R owner/repo`:
   ```
   gh issue list --state open --limit 100 --json number,title,body,labels,author,createdAt,updatedAt,comments,url > maintainer/.cache/open.json
   gh issue list --state all --limit 500 --json number,title,body,state,createdAt > maintainer/.cache/all.json
   gh label list --limit 200 --json name,description
   ```
   Create `maintainer/.cache/` if needed. Use the repo's existing label names; never invent a
   label when an equivalent exists (`type: bug` beats a new `bug`).

2. **Read the house rules.** Skim CONTRIBUTING.md, `.github/ISSUE_TEMPLATE/`, and SECURITY.md if
   present. Note the version-support policy and where questions belong (Discussions, forum, chat).

3. **Find duplicates.** Run:
   ```
   python3 "${CLAUDE_SKILL_DIR}/dupes.py" maintainer/.cache/all.json --threshold 0.45
   ```
   Treat the output as a shortlist. Open both issues with `gh issue view N --json title,body,comments`
   and confirm they describe the same root cause before calling it a duplicate. Same symptom,
   different cause is not a duplicate. The older issue is the one to keep unless the newer one
   has the better reproduction; say so when you pick the newer one.

4. **Classify each open issue** into exactly one primary class:

   | Class | Rule |
   |---|---|
   | bug | Describes behaviour that contradicts docs or intent, with enough detail to act |
   | needs-repro | Looks like a bug but lacks version, steps, or expected vs actual |
   | feature | Asks for new behaviour or an option |
   | question | Asks how to do something the project already supports |
   | duplicate | Confirmed in step 3 |
   | stale | No activity for 90+ days (`updatedAt`) and waiting on the reporter |
   | security | Mentions a vulnerability, leaked secret, or exploit. Flag only; see below |

   Add a priority guess (`p1` crash/data loss/regression, `p2` broken feature with workaround,
   `p3` minor) only for bugs. Add `good first issue` candidates to a separate list for
   `maintainer-good-first-issue` instead of labelling them now.

5. **Draft a reply per issue**, 2 to 5 sentences, written as the maintainer:
   - Thank the reporter once, by handle, without gushing.
   - needs-repro: ask for the 2-3 specific missing facts (version, OS, minimal snippet), not a generic template.
   - question: answer it if the docs or code answer it (cite the file or doc link), then point to the right channel.
   - duplicate: link the kept issue and invite them to add details there.
   - feature: restate the request in one line, say whether it fits the project scope as you read it, ask about the use case.
   - stale: ask whether it still reproduces on the latest release; say it will be closed in 14 days otherwise.
   - Do not promise fixes, dates, or releases.

6. **Write the report** to `maintainer/triage-YYYY-MM-DD.md`:
   ```
   # Triage report: owner/repo (YYYY-MM-DD)
   Open issues reviewed: N | bugs: a | needs-repro: b | features: c | questions: d | duplicates: e | stale: f

   ## Needs you first
   - #123 (p1 bug) one-line why

   ## Duplicates
   | Close | Keep | Why they match |

   ## All issues
   ### #123 Title
   Class: bug (p1) | Labels to add: bug, p1 | Labels to remove: needs-triage
   Reply draft:
   > ...
   Action: comment + label | close as duplicate of #98 | none
   ```
   Then print the summary line and the "Needs you first" list in chat.

7. **Ask for confirmation**, listing the exact commands grouped by type, for example:
   ```
   gh issue edit 123 --add-label "bug,p1" --remove-label "needs-triage"
   gh issue comment 123 --body-file maintainer/.cache/reply-123.md
   gh issue close 140 --reason "not planned" --comment "Duplicate of #98 ..."
   ```
   Accept "all", "only labels", "all except #140", or edits to any reply. Write each reply to
   its own body file to avoid shell quoting problems, then run only what was approved. Report
   what ran and anything that failed.

## Security reports

If an issue appears to disclose a vulnerability publicly, do not discuss details in a reply.
Draft a short note asking the reporter to use the private channel from SECURITY.md (or GitHub
private vulnerability reporting), and recommend the maintainer consider hiding or editing the
issue. Put it at the top of "Needs you first".

## What NOT to do

- Do not label, comment, close, lock, assign, or transfer anything before explicit confirmation.
- Do not close an issue as a duplicate on the script score alone; read both.
- Do not create new labels unless the user approves the label name and colour.
- Do not paste the reporter's private data (tokens, emails, logs with secrets) into the report or replies.
- Do not argue with or lecture reporters, and do not write replies that sound like a bot template.
- Do not touch pull requests here; that is `maintainer-pr-welcome` and `maintainer-weekly`.

## Hand-off

- Candidates for newcomers go to `maintainer-good-first-issue`.
- If the tracker lacks issue templates (many needs-repro issues), suggest `maintainer-community-files`.
- For a read-only pass that never runs write commands, delegate to the `triage-captain` agent.
