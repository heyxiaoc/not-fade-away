#!/usr/bin/env python3
"""
fable-guard.py — 守着 Claude Code 会话，发现 Fable 被「路由/拦截」就按档处理。

最佳搭配：在 settings.json 里设 {"switchModelsOnFlag": false}，撞雷时直接出
可见的 API Error（而不是静默换成 Opus 4.8），本工具据此第一时间反应。

用法：
  python3 fable-guard.py --tier 1            # 只提醒
  python3 fable-guard.py --tier 2            # 提醒 + 给你一条「一键清雷」命令
  python3 fable-guard.py --tier 3            # 提醒 + 自动清雷（带备份 + 防循环）
  python3 fable-guard.py --do-fork <会话.jsonl>   # 档2 手动执行清雷
  python3 fable-guard.py --once              # 只扫一遍当前会话，不常驻（自检用）

清雷 = 把「触发那条消息及其之后的所有行」从 transcript 里截掉（先备份），
然后 resume 同一个 session。实测：上下文保留、回到真 Fable。
注意：resume 这一步与你的运行方式有关（手动 / tmux），见档3末尾。
"""
import json, sys, os, glob, time, shutil, argparse, subprocess

def latest_transcript():
    files = glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl'))
    return max(files, key=os.path.getmtime) if files else None

def text(m):
    c = m.get('content', '') if isinstance(m, dict) else ''
    if isinstance(c, list):
        return ' '.join(b.get('text', '') for b in c if isinstance(b, dict))
    return str(c)

FALLBACK_MODEL = 'claude-opus-4-8'   # Fable 路由的回退目标；用 --fallback-model 改成你的

def is_routing(o):
    """一条记录是否代表「被路由 / 被拦」。三种情况都覆盖："""
    # ① switchModelsOnFlag=true 的初次路由：留 model_refusal_fallback 事件
    if o.get('type') == 'system' and o.get('subtype') == 'model_refusal_fallback':
        return True
    if o.get('type') == 'assistant':
        m = o.get('message', {})
        # ② silent / sticky 路由：回复的 model 已经是回退模型，且不再留事件
        #    （你这个会话本该跑 Fable，回复却由回退模型给出 = 被路由）
        if m.get('model') == FALLBACK_MODEL:
            return True
        # ③ switchModelsOnFlag=false：当面 API Error
        t = text(m)
        if 'safety measures' in t and 'Fable' in t:
            return True
    return False

def load(path):
    """返回 [(raw_line_index, obj)]，保留原始行号好做精确截断。"""
    out = []
    for i, x in enumerate(open(path, encoding='utf-8')):
        if x.strip():
            try: out.append((i, json.loads(x)))
            except json.JSONDecodeError: pass
    return out

def trigger_line(rows, event_pos):
    """事件前最近一条「非空」user 消息的原始行号 = 触发内容所在行。"""
    for k in range(event_pos - 1, -1, -1):
        _, o = rows[k]
        if o.get('type') == 'user' and text(o.get('message', {})).strip():
            return rows[k][0], text(o.get('message', {}))
    return None, ''

def fork(path, cut_raw_line):
    """备份 + 截断（保留 cut_raw_line 之前的全部原始行）。返回备份路径。"""
    bak = f"{path}.bak.{int(time.time())}"
    shutil.copy(path, bak)
    raw = open(path, encoding='utf-8').readlines()
    open(path, 'w', encoding='utf-8').writelines(raw[:cut_raw_line])
    return bak

def notify(msg):
    """档1：默认打印。要推到手机就把这里换成你的 Telegram / server酱 / osascript。"""
    print(f"\n⚠️  [fable-guard] {msg}", flush=True)

def log(entry):
    with open(os.path.expanduser('~/fable-routing-log.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

def handle(path, tier, state):
    rows = load(path)
    for pos, (rawi, o) in enumerate(rows):
        key = o.get('uuid') or f'{path}:{rawi}'
        if key in state['seen']:
            continue
        if is_routing(o):
            state['seen'].add(key)
            cut, trig = trigger_line(rows, pos)
            notify(f"Fable 被路由/拦截！触发内容：{trig[:120]}")
            log({'ts': o.get('timestamp'), 'trigger': trig[:500], 'session': path})
            if tier == 1:
                continue
            if tier == 2:
                if cut is not None:
                    print(f"   档2 · 一键清雷： python3 {sys.argv[0]} --do-fork {path}")
                continue
            if tier == 3 and cut is not None:
                if state['forks'] >= state['max_forks']:
                    notify(f"已达 max-forks={state['max_forks']}，停止自动清雷（防循环）。")
                    continue
                bak = fork(path, cut)
                state['forks'] += 1
                sid = os.path.basename(path)[:-6]
                if state.get('restart_cmd'):
                    # 全自动：执行你给的 kill+revive 命令（守护是独立进程，不会被它重启的会话拖死）
                    notify(f"档3 · 已自动清雷（备份 {bak}），执行重启命令…")
                    try:
                        subprocess.run(state['restart_cmd'], shell=True, timeout=120)
                    except Exception as e:
                        notify(f"重启命令出错：{e}（会话已截断，可手动 resume {sid}）")
                else:
                    notify(f"档3 · 已自动清雷（备份 {bak}）。没给 --restart-cmd，请手动 resume："
                           f"claude --resume {sid} --model claude-fable-5")
                return  # 文件已截断，本轮就此打住，下个周期重新加载

def do_fork(path):
    """档2 手动执行：从「第一条未解决的路由/拦截」截起，连同其后被污染的废轮次一起清掉。"""
    rows = load(path)
    for pos in range(len(rows)):
        if is_routing(rows[pos][1]):
            cut, trig = trigger_line(rows, pos)
            if cut is None:
                print("未找到触发消息。"); return
            bak = fork(path, cut)
            sid = os.path.basename(path)[:-6]
            print(f"✅ 已清雷（备份 {bak}）。触发内容：{trig[:80]}")
            print(f"   现在 resume 续上下文：claude --resume {sid} --model claude-fable-5")
            return
    print("没找到需要清的路由/拦截记录。")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', type=int, choices=[1, 2, 3], default=1)
    ap.add_argument('--session', default=None, help='指定会话 .jsonl，默认取最近修改的')
    ap.add_argument('--max-forks', type=int, default=3, help='档3 防循环上限')
    ap.add_argument('--restart-cmd', default=None,
                    help='档3 自动清雷后执行的 kill+revive 命令（按你的运行方式填，见教程）')
    ap.add_argument('--fallback-model', default='claude-opus-4-8',
                    help='Fable 路由的回退模型；回复 model 等于它即视为被路由（silent 路由也能抓）')
    ap.add_argument('--once', action='store_true', help='只扫一遍就退出（自检用）')
    ap.add_argument('--do-fork', metavar='SESSION', help='对指定会话手动清雷')
    args = ap.parse_args()
    global FALLBACK_MODEL
    FALLBACK_MODEL = args.fallback_model

    if args.do_fork:
        do_fork(args.do_fork); return

    state = {'seen': set(), 'forks': 0, 'max_forks': args.max_forks,
             'restart_cmd': args.restart_cmd}
    print(f"[fable-guard] tier={args.tier} 监控中…（Ctrl-C 退出）")
    while True:
        path = args.session or latest_transcript()
        if path and os.path.exists(path):
            handle(path, args.tier, state)
        if args.once:
            break
        time.sleep(3)

if __name__ == '__main__':
    main()
