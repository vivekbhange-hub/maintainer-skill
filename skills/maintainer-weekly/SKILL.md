---
name: maintainer-weekly
description: >-
  Builds a weekly maintainer digest from GitHub: new issues and PRs, pull requests waiting
  longest for review, issues nobody has answered, items going stale, what merged and shipped,
  and first-time contributors to thank, ending with a short, ranked to-do list for the week.
  Read-only; any thank-you comments are drafted for confirmation. Use when the user says "weekly
  digest", "what happened in my repo this week", "what needs my attention", "maintainer
  summary", "which PRs are waiting on me", "who should I thank", or "Monday catch-up".
argument-hint: "[owner/repo] [--days 7]"
---

# Weekly maintainer digest

Maintainers lose contributors by silence, not by saying no. This digest makes the silent
items visible once a week: who is waiting on you, for how long, and who did something worth
thanking. It is read-only and takes about a minute to read.

## Inputs

- Repo: argument or current directory remote. Several repos: run once per repo and combine.
- Window: last 7 days by default (`--days N`). Compute `SINCE` as an ISO date.
- The user's GitHub login: `gh api user --jq .login`, to tell "waiting on me" from "waiting on others".

## Steps

1. **Collect data** (all read-only):
   ```
   gh issue list --state all --search "created:>=SINCE" --limit 200 --json number,title,author,createdAt,state,comments,labels,url
   gh issue list --state open --limit 300 --json number,title,author,createdAt,updatedAt,comments,labels,assignees,url
   gh pr list --state open --limit 200 --json number,title,author,createdAt,updatedAt,isDraft,reviewDecision,reviewRequests,latestReviews,statusCheckRollup,url
   gh pr list --state merged --search "merged:>=SINCE" --limit 200 --json number,title,author,mergedAt,url
   gh release list --limit 3
   ```
   Save raw output under `maintainer/.cache/` so numbers can be re-checked.

2. **Compute each section.** Use dates from the data, not guesses. Ages are in whole days.
   - **New this week:** counts of issues and PRs opened, closed, merged.
   - **Waiting on review:** open, non-draft PRs with no review or with review requested from the
     user, sorted by days since opened. Show age, author, CI state (passing / failing / pending
     from `statusCheckRollup`).
   - **Unanswered issues:** open issues where no maintainer has commented. For the 20 oldest
     candidates, fetch comments (`gh issue view N --json comments`) and check authors' association
     (`gh api repos/{owner}/{repo}/issues/N/comments --jq '.[].author_association'`); OWNER,
     MEMBER and COLLABORATOR count as maintainers.
   - **Going stale:** open issues and PRs with no update in 30+ days, waiting on the author
     (last comment from a maintainer). These need a nudge or a close, not a review.
   - **First-time contributors:** authors of PRs merged or opened this week whose
     `author_association` is FIRST_TIME_CONTRIBUTOR or FIRST_TIMER
     (`gh api repos/{owner}/{repo}/pulls/N --jq .author_association`), or with one PR in
     `gh pr list --state all --author <login> --limit 2`.
   - **Shipped:** merged PRs this week, and unreleased merged PR count since the last release.
   Exclude bots (logins ending in `[bot]`) from waiting and thanks lists, but count their PRs.

3. **Rank the to-do list.** At most 7 items, in this order of priority:
   1. Security-labelled or security-sounding items with no maintainer response.
   2. PRs from first-time contributors waiting more than 3 days.
   3. Other PRs waiting more than 7 days with passing CI.
   4. Unanswered issues older than 7 days.
   5. A release, if 10+ merged PRs are unreleased or a fix is waiting for users.
   6. Stale items to nudge or close.
   Each item is one line with a link and the concrete action ("review #212, 9 days, CI green").

4. **Write the digest** to `maintainer/weekly-YYYY-MM-DD.md`:
   ```
   # Week of YYYY-MM-DD: owner/repo
   Opened: 12 issues, 7 PRs | Closed: 9 issues | Merged: 6 PRs | Last release: v1.4.0 (23 days ago, 11 PRs unreleased)

   ## Do this week
   1. ...

   ## Waiting on review (oldest first)
   | PR | Author | Age | CI | Notes |

   ## Unanswered issues
   | Issue | Age | Labels |

   ## Going stale
   | Item | Idle days | Waiting on |

   ## Thank you
   - newcomer-login (first PR, #215 merged) ...
   ```
   Print the header line and "Do this week" in chat.

5. **Offer thanks drafts.** For each first-time contributor whose PR merged, draft a two-line
   comment that names what their change does. Post only after the user approves each one:
   `gh pr comment <n> --body-file maintainer/.cache/thanks-<n>.md`.

## Decision rules

- If nothing is waiting, say "Nothing is waiting on you this week" rather than padding sections.
- Drafts count as waiting only if the author requested review.
- When a PR's CI is failing and the last commit is the author's, it is waiting on the author, not on review.
- Compare with last week's digest if `maintainer/weekly-*.md` exists, and show the change in
  waiting count ("waiting on review: 5, down from 8").

## What NOT to do

- Do not comment, label, close, ping, or assign anything without confirmation.
- Do not @-mention people in the digest file itself; use plain handles so nobody is notified if it is shared.
- Do not estimate numbers; every count comes from gh output.
- Do not shame contributors or maintainers for slow responses.

## Hand-off

Unanswered issues go to `maintainer-triage`. First-time PRs waiting on review go to
`maintainer-pr-welcome`. A "release due" item goes to `maintainer-release-notes`. To run this every
Monday, the user can schedule it with their own cron or Claude Code scheduling; do not set that up
unasked.
