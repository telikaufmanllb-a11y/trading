# Running the research loop durably

## TL;DR
In-session schedulers can't keep the loop alive; a **scheduled GitHub Actions workflow** can.
Do the one-time setup below and the loop runs every 6 hours on GitHub's infrastructure.

## Why the in-session loop kept stopping
This project is developed in an **ephemeral cloud container**. Both `cron` (CronCreate) and
`ScheduleWakeup` are *in-session* schedulers — they only fire while that Claude Code session is
alive. When the session goes idle, the container is **reclaimed**, and the in-memory scheduler is
destroyed with it. That is why the loop went silent for ~18h: nothing was left running to fire it.
This is an environment limitation, not a bug in the project code. No scheduler that lives inside
the session can survive the container being torn down.

## The durable fix: `.github/workflows/research-loop.yml`
A scheduled workflow runs on GitHub's servers, independent of any interactive session. Each run is
one iteration of the **LOOP PROTOCOL** (CLAUDE.md §5): check out the feature branch, run tests,
let Claude Code do one highest-value task, re-run tests, commit & push. The loop's memory is
`PROGRESS.md`, so a fresh checkout each run is exactly the intended design.

### One-time setup (only the repo owner can do this)
1. **Add the API key secret:** repo → Settings → Secrets and variables → Actions → New repository
   secret → `ANTHROPIC_API_KEY`. (Optionally also `EDGAR_CONTACT` = your email for SEC fair-access.)
2. **Allow pushes:** Settings → Actions → General → Workflow permissions → "Read and write
   permissions".
3. **Enable / first run:** Actions tab → research-loop → enable, then "Run workflow" to test.
4. **Cadence:** edit the `cron:` line in the workflow (default `17 */6 * * *` = every 6 hours).
   Every run consumes API tokens — keep the interval sane.

Until the secret is set, the workflow fails fast at the auth step and does nothing harmful.

### Cost & safety notes
- Each run uses Claude API tokens; 6-hourly is a reasonable default. Lower the frequency to spend
  less; raise it (min ~5 min, though GitHub throttles scheduled jobs) to move faster.
- The job operates **only** on `claude/loop-begin-ar03st`; commits carry `[skip ci]` so it can't
  trigger itself; it is bound by CLAUDE.md's HARD RULES (paper only, never live trading).
- GitHub disables scheduled workflows after ~60 days of repo inactivity — push anything to re-enable.

## Stop-gap: in-session cron
While you have an interactive Claude Code session open, you can still run `/loop` (it arms a 5-min
in-session cron). Just know it stops the moment that session is reclaimed — use the GitHub Actions
workflow for anything unattended.

## Other option
**Claude Code on the web scheduled triggers** (see https://code.claude.com/docs) may offer a
managed scheduled-session feature; if you prefer that over GitHub Actions, configure it in the web
UI with the prompt: `Continue per CLAUDE.md LOOP PROTOCOL`.
