#!/usr/bin/env python3
# prune-transcript.py <transcript.jsonl> [--dry-run]
#
# Shrink a luci-web claude session transcript WITHOUT breaking --resume.
# Everything before the LAST compact boundary is dead weight for the live
# context (claude rebuilds context from the last compact summary + tail), but
# it still bloats the file and slows session load. We keep every line and its
# uuid/parentUuid chain intact, and only truncate the bulky CONTENT of
# pre-boundary events:
#   - user.message.content[].tool_result content  -> "[pruned]"
#   - top-level toolUseResult                     -> type-preserving stub
#   - attachment.*                                -> {type, pruned:true}
#   - queue-operation content                     -> "[pruned]"
#   - assistant thinking blocks (text+signature)  -> "[pruned]" / ""
# Her words and cc's replies (text blocks) are NOT touched.
#
# Safety: the ORIGINAL is gzipped into _archive/<name>.pre-prune-<ts>.jsonl.gz
# BEFORE any rewrite (full history preserved). The rewrite goes to a temp file
# and replaces the original atomically only if every line re-parses as JSON and
# the line count matches. On ANY error the original is left untouched.
# Run this ONLY while the instance is stopped (start.sh restart path).
import gzip
import json
import os
import shutil
import sys
import time

PLACEHOLDER = "[pruned]"
TRUNC_LIMIT = 80  # 短字符串(type/id/日期等)原样保留;超过的才是要剪的肥肉


def deep_trunc(v):
    """Shape-preserving deep truncation: every structure stays EXACTLY as-is
    (arrays stay arrays, every key survives) — only long strings become the
    placeholder. This is the whole fix for claude ≥2.1.201: its history
    renderer calls .map / reads fields on these objects, so replacing
    structures with stubs (the old approach) crashes the session with
    "undefined is not an object (evaluating 'e.content.map')"."""
    if isinstance(v, str):
        return v if len(v) <= TRUNC_LIMIT else PLACEHOLDER
    if isinstance(v, list):
        return [deep_trunc(x) for x in v]
    if isinstance(v, dict):
        return {k: deep_trunc(x) for k, x in v.items()}
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
                        b["content"] = deep_trunc(b["content"])
        if "toolUseResult" in e:
            e["toolUseResult"] = deep_trunc(e["toolUseResult"])
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
            e["attachment"] = deep_trunc(a)
    elif t == "queue-operation":
        if isinstance(e.get("content"), str) and len(e["content"]) > TRUNC_LIMIT:
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
            events.append(None)  # keep byte-identical later

    # locate LAST compact boundary
    last_boundary = -1
    for i, e in enumerate(events):
        if isinstance(e, dict) and e.get("type") == "system" and e.get("subtype") == "compact_boundary":
            last_boundary = i
    if last_boundary <= 0:
        # 无边界兜底(2026-07-16):从未 compact 过的会话(如常驻代理会话)没有边界,
        # 老逻辑直接放弃 → transcript 只涨不减 → 维护系统陷入"超限→重启→没剪动→
        # 下小时再来"的死循环。改为:保最后 TAIL_KEEP 行原样(远大于 resume 真正
        # 载入上下文的量),更早的行照样做形状保持深截断。她的话和回复文本永远不动。
        TAIL_KEEP = 400
        if len(events) <= TAIL_KEEP + 100:
            print(f"no compact boundary & only {len(raw_lines)} lines — nothing to prune"); return
        last_boundary = len(events) - TAIL_KEEP
        print(f"no compact boundary — fallback: keep last {TAIL_KEEP} lines intact, prune the rest")

    before = os.path.getsize(path)
    out_lines = []
    pruned_n = 0
    for i, (ln, e) in enumerate(zip(raw_lines, events)):
        if e is None or i >= last_boundary:
            out_lines.append(ln)  # tail + unparsable: byte-identical
            continue
        prune_event(e)
        pruned_n += 1
        out_lines.append((json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n").encode())

    if len(out_lines) != len(raw_lines):
        print("line count mismatch — abort, original untouched"); sys.exit(1)
    # validate every output line re-parses
    for ln in out_lines:
        json.loads(ln)  # raises -> abort before touching original

    after = sum(len(l) for l in out_lines)
    print(f"{before/1048576:.1f}MB -> {after/1048576:.1f}MB "
          f"(boundary@line {last_boundary+1}/{len(raw_lines)}, pruned {pruned_n} events)")
    if dry:
        print("dry-run: original untouched"); return

    # archive original (gzip) BEFORE rewrite — full history preserved
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
