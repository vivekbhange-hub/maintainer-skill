---
name: maintainer-pr-welcome
description: >-
  Reviews a pull request from a first-time or new contributor the way a good mentor would:
  correctness first, then the repo's conventions, with blocking issues separated from nits and
  every point specific and kind. Drafts the review comment (and optional suggested changes) for
  the maintainer to edit; posts only after confirmation. Use when the user says "review this PR
  from a new contributor", "help me respond to PR #123", "first-time contributor PR", "write a
  kind review", "how do I tell them this needs changes", or "welcome this contributor".
argument-hint: "<PR number or URL>"
---

# Welcoming PR review

A first PR decides whether someone becomes a regular contributor. The review has to be right
(you are still the gate on quality) and it has to be the kind of review that makes them want
to open a second PR. This skill does both: a real code review, written in a teaching voice.

## Steps

1. **Load the PR.**
   ```
   gh pr view <n> --json number,title,body,author,baseRefName,headRefName,files,additions,deletions,commits,labels,isDraft,closingIssuesReferences,url
   gh pr diff <n>
   gh pr checks <n>
   ```
   Check whether this is their first contribution:
   `gh pr list --state all --author <login> --limit 5 --json number,state`. One result means
   first PR; mention that in the welcome line. If `gh pr checks` shows failures, read the failing
   job log (`gh run view <run-id> --log-failed`) and explain the cause in plain words.

2. **Learn the house style** before judging style: CONTRIBUTING.md, PR template, lint/format
   config (`.editorconfig`, `ruff.toml`, `.eslintrc*`, `rustfmt.toml`), and two or three nearby
   files the PR touches. A convention only counts if the repo actually follows it.

3. **Review for correctness first.** Read every changed file in full context (Read the whole
   function, not only the hunk). Check, in order:
   - Does it do what the linked issue asks? Does it change behaviour the issue did not ask for?
   - Edge cases: empty input, None/null, errors, concurrency, Windows paths, unicode.
   - Tests: is there a test that fails without the change? If not, that is a blocking item.
   - Public API, CLI, or config changes: are they documented and backward compatible?
   - Security: untrusted input, secrets in code, new dependencies (check the license with `maintainer-license-check` if one is added).
   If you can, check out and run the tests locally (`gh pr checkout <n>` then the test command),
   and say whether you did.

4. **Sort findings** into three buckets. Be strict about what is blocking:
   - **Must change** (blocking): bugs, missing tests for new behaviour, broken CI, breaking changes
     without discussion, license problems.
   - **Should change** (please do, but discuss if you disagree): naming that misleads, duplication
     of an existing helper, missing docs.
   - **Nits** (optional, non-blocking): style the formatter does not enforce, wording.
   If there are more than 5 nits, keep the 3 that teach the most and drop the rest.

5. **Draft the review** to `maintainer/pr-<n>-review.md`:
   ```
   Hi @login, thanks for this, and welcome to <project>! <One specific thing the PR does well.>

   <One-sentence overall verdict: ready after small changes / needs a couple of fixes / needs a different approach, and why.>

   **Must change**
   1. `path/file.py` L42: <what is wrong> -> <what to do>. <Why, in one line, linking the convention or doc.>

   **Should change**
   - ...

   **Nits (optional)**
   - ...

   <How to update the PR: push more commits to the same branch; no need to open a new one.>
   <If they get stuck: offer to help or to push a fix to their branch if "Allow edits by maintainers" is on.>
   ```
   Every point names a file and line, says what to do, and why. Use GitHub suggestion blocks
   for small, exact fixes (one per inline comment):
   ````
   ```suggestion
   corrected line
   ```
   ````
   Collect inline comments in `maintainer/pr-<n>-inline.json` as `[{"path": ..., "line": ..., "body": ...}]`.

6. **Confirm, then post.** Show the draft and ask the maintainer to approve, edit, or pick the
   review type (comment, request changes, approve). Then run one of:
   ```
   gh pr review <n> --comment --body-file maintainer/pr-<n>-review.md
   gh pr review <n> --request-changes --body-file maintainer/pr-<n>-review.md
   gh pr review <n> --approve --body-file maintainer/pr-<n>-review.md
   ```
   For inline comments, post them as one review through the API after confirmation:
   `gh api repos/{owner}/{repo}/pulls/<n>/reviews --method POST --input <payload.json>` with
   `event`, `body`, and `comments` built from the inline file.

## Tone rules

- Talk about the code, never the person. "This loop skips the last item", not "you forgot".
- Use "we" for project conventions ("we keep imports sorted with ruff").
- Ask real questions when unsure ("Was the retry here intentional?") instead of asserting.
- No sarcasm, no "just", no "simply", no "obviously". No exclamation-mark pile-ups.
- Praise is specific or absent. "Nice test for the empty-file case" beats "Great job!".
- Small PR, small review. Do not turn a 10-line fix into a refactor request.

## What NOT to do

- Do not post, approve, request changes, merge, close, or push to the contributor's branch without confirmation.
- Do not soften a real bug into a nit to be nice. Kind and clear, not vague.
- Do not ask for changes that the repo's own code does not follow.
- Do not demand unrelated cleanup ("while you're here...") as blocking.

## Hand-off

For a longer back-and-forth with a newcomer, delegate to the `newcomer-buddy` agent. If the PR
adds a dependency, run `maintainer-license-check`. If it fixes an issue, `maintainer-release-notes`
will credit them at release time.
