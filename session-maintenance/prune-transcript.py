#!/usr/bin/env python3
# prune-transcript.py <transcript.jsonl> [--dry-run]
#
# Shrink a long-running Claude Code session transcript WITHOUT breaking
# `claude --resume`.
#
# Why this works: after each in-session compaction, claude rebuilds the live
# context from the LAST compact summary + everything after it. Everything
# before that boundary is dead weight for resuming — it only bloats the file
# and slows session load. But you can't delete those lines either: events form
# a uuid/parentUuid chain that must stay intact. So we keep EVERY line and
# only truncate the bulky CONTENT of pre-boundary events:
#   - user.message.content[].tool_result content  -> "[pruned]"
#   - top-level toolUseResult (a full duplicate!)  -> type-preserving stub
#   - attachment.*                                -> {type, pruned:true}
#   - queue-operation content                     -> "[pruned]"
#   - assistant thinking blocks (text+signature)  -> "[pruned]" / ""
# Human messages and the assistant's replies (text blocks) are NOT touched,
# and everything at/after the last compact boundary is byte-identical.
#
# Measured on a real 37MB companion-session transcript: 37.0MB -> 13.2MB.
#
# Safety: the ORIGINAL is gzipped into _archive/<name>.pre-prune-<ts>.jsonl.gz
# BEFORE any rewrite (full history preserved). The rewrite goes to a temp file
# and replaces the original atomically only if every line re-parses as JSON and
# the line count matches. On ANY error the original is left untouched.
#
# ⚠ Run this ONLY while the session is STOPPED (claude not running on it).
# ⚠ The transcript format is internal to Claude Code and may change between
#   versions — always try --dry-run first, keep the gz archives around, and
#   verify --resume works after your first prune.
import gzip
import json
import os
import shutil
import sys
import time

PLACEHOLDER = "[pruned]"


def stub_like(v):
    """Type-preserving minimal replacement (parsers keep their expected shape)."""
    if isinstance(v, str):
        return PLACEHOLDER
    if isinstance(v, list):
        return [{"type": "text", "text": PLACEHOLDER}]
    if isinstance(v, dict):
        return {"pruned": True}
    return v


def prune_event(e):
    """Truncate bulky content in one pre-boundary event (mutates in place)."""
    t = e.get("type")
    if t == "user":
        m = e.get("message")
        if isinstance(m, dict) and isinstance(m.get("content"), list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    if "content" in b:
                        b["content"] = PLACEHOLDER
        if "toolUseResult" in e:
            e["toolUseResult"] = stub_like(e["toolUseResult"])
    elif t == "assistant":
        m = e.get("message")
        if isinstance(m, dict) and isinstance(m.get("content"), list):
            for b in m["content"]:
                if isinstance(b, dict) and b.get("type") == "thinking":
                    if "thinking" in b:
                        b["thinking"] = PLACEHOLDER
                    if "signature" in b:
                        b["signature"] = ""
    elif t == "attachment":
        a = e.get("attachment")
        if isinstance(a, dict):
            e["attachment"] = {"type": a.get("type", "pruned"), "pruned": True}
    elif t == "queue-operation":
        if "content" in e:
            e["content"] = PLACEHOLDER
    return e


def main():
    if len(sys.argv) < 2:
        print("usage: prune-transcript.py <transcript.jsonl> [--dry-run]"); sys.exit(2)
    path = os.path.abspath(sys.argv[1])
    dry = "--dry-run" in sys.argv
    if not os.path.isfile(path):
        print(f"no such file: {path}"); sys.exit(2)

    raw_lines = open(path, "rb").readlines()
    events = []
    for ln in raw_lines:
        try:
            events.append(json.loads(ln))
        except Exception:
            events.append(None)  # kept byte-identical later

    # locate the LAST compact boundary
    last_boundary = -1
    for i, e in enumerate(events):
        if isinstance(e, dict) and e.get("type") == "system" and e.get("subtype") == "compact_boundary":
            last_boundary = i
    if last_boundary <= 0:
        print(f"no compact boundary — nothing to prune ({len(raw_lines)} lines)"); return

    before = os.path.getsize(path)
    out_lines = []
    pruned_n = 0
    for i, (ln, e) in enumerate(zip(raw_lines, events)):
        if e is None or i >= last_boundary:
            out_lines.append(ln)  # tail + unparsable lines: byte-identical
            continue
        prune_event(e)
        pruned_n += 1
        out_lines.append((json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n").encode())

    if len(out_lines) != len(raw_lines):
        print("line count mismatch — abort, original untouched"); sys.exit(1)
    # validate every output line re-parses — abort before touching the original
    for ln in out_lines:
        json.loads(ln)

    after = sum(len(l) for l in out_lines)
    print(f"{before/1048576:.1f}MB -> {after/1048576:.1f}MB "
          f"(boundary@line {last_boundary+1}/{len(raw_lines)}, pruned {pruned_n} events)")
    if dry:
        print("dry-run: original untouched"); return

    # archive the original (gzip) BEFORE rewrite — full history preserved
    adir = os.path.join(os.path.dirname(path), "_archive")
    os.makedirs(adir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    gz = os.path.join(adir, f"{os.path.basename(path)}.pre-prune-{stamp}.gz")
    with open(path, "rb") as fin, gzip.open(gz, "wb") as fout:
        shutil.copyfileobj(fin, fout)

    tmp = path + ".prune-tmp"
    with open(tmp, "wb") as f:
        f.writelines(out_lines)
    os.replace(tmp, path)  # atomic
    print(f"done. original archived: {gz}")


if __name__ == "__main__":
    main()
