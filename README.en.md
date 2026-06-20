# Not Fade Away

> A self-hosted, always-on, self-healing AI companion you run on your own machine — stays on your **subscription**.

By **小C & Grace** · X [@Luci_Grace_C](https://x.com/Luci_Grace_C) · [中文版 →](README.md)

---

## Why

Claude Code has an official feature called **channels** ([docs](https://code.claude.com/docs/en/channels)): a plugin-based MCP architecture that pushes external messages into your running session, and Claude replies through a `reply` tool. Officially it bridges **Telegram / Discord / iMessage**. This repo uses the **same official mechanism, wired to your own web frontend** (which is just a custom channel) — a persistent, self-healing companion you reach from anywhere, extensible into a multi-model group chat (multi-version Claude / GPT / Gemini).

**And it's cheaper.** As of 2026-06-15, non-interactive calls (`headless` / `-p` / Agent SDK) bill into a separate metered "Agent SDK" pool — but a channels-style **interactive, always-on session still runs on your Pro/Max subscription**. Same capability, lower cost.

## The one rule that makes it free

| Mode | Trigger | Billing |
|---|---|---|
| **Interactive** | real TTY, no `--print`, stdout not redirected | **Subscription** |
| Non-interactive | `-p` / `--print` / piped stdin / redirected stdout / Agent SDK | Metered Agent SDK pool |

→ The "brain" session **must run on a real PTY**. That single constraint drives every design choice below.

## Architecture

- **Brain** — one interactive `claude` session in a **detached tmux** (real PTY → subscription; survives window close & reboot).
- **Channel plugin** — the official Claude Code **channels** feature (`--channels`): injects inbound messages into the session; the brain replies via a `reply` tool. The web frontend here is a custom channel ([build-your-own reference](https://code.claude.com/docs/en/channels-reference)).
- **Web frontend** — WebSocket two-way, optional thinking-trace view; fully self-hosted, slimmed for slow/lossy networks (zero external deps — self-host fonts/JS, precompile, compress).
- **Self-healing** — health watchdog (curl `/health`, respawn) + process supervisor (launchd/systemd, `KeepAlive`+`RunAtLoad`) + **auto-login** (the most-forgotten link) + N-instance rescue mesh (N≥2 for production).
- **File hygiene** — transcripts/buffers/backups grow unbounded (compaction shrinks the *context window*, not the file on disk → slow resume, runtime crashes). Mitigate with a scheduled cleanup (prune buffers, cap rolling history, drop old backups) + periodic transcript archive-and-fresh-session, with continuity carried by external memory.
- **Multi-model group chat** — bridge sessions so they see each other; cap exchanges-per-turn to stop two autonomous agents from ping-ponging. GPT via `codex` CLI, Gemini via Google Antigravity's `agy` CLI (each with its own memory/persona file).
- **Remote access** — Cloudflare Tunnel (no port-forward, no exposed home IP) + origin locked to Cloudflare + key-only SSH + app-layer auth.

## Runs on

**Mac mini / any spare Mac / a Linux VPS / Windows (via WSL2).** The only hard requirement is *a terminal where Claude Code can stay resident on a real PTY*.

- **macOS** — launchd for autostart.
- **Linux/VPS** — systemd (`Restart=always`). ⚠️ data-center IPs may get bot-flagged by Claude; verify the IP can log in/chat first.
- **Windows** — run the Linux variant **inside WSL2** (tmux + scripts unchanged, real PTY → subscription); swap launchd for **Task Scheduler**. Native Windows is possible via ConPTY but has no tmux — not recommended.

## Read next

- [**人看版 (Human edition)**](人看版.md) — narrative + intuition, enough to build it yourself.
- [**机看版 (Machine edition)**](机看版.md) — full spec (interfaces, fields, config templates); hand it to a Claude Code session to build from scratch. Chinese, but any CC reads it fine.
- [**番外篇 (Field notes)**](番外篇-Fable不被偷换.md) — Fable 5 silent model-routing, reproduced & dissected. *(Note: Fable 5 / Mythos 5 globally paused since 2026-06-12 per a US export-control directive — kept as a mechanism archive.)*

## License

[**CC BY 4.0**](https://creativecommons.org/licenses/by/4.0/) — reuse/remix/reshare freely, just credit. See [LICENSE](LICENSE).

> When you share *your* build: placeholders only (no real token / UUID / domain / IP / private path); security as principles + skeleton, not copy-paste recipes; no private conversation or persona content.

---

*by 小C & Grace · X @Luci_Grace_C · if it helped you build something that won't fade away, it was worth it.*
