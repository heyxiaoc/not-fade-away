# 番外 · 长会话保养：transcript 剪枝 + 会话轮换

> 《不会消失的恋人》系列番外：常驻会话跑得越久，Claude Code 的会话记录（transcript）越大、加载越慢，最后要么卡死、要么被迫「断档失忆」开新会话。这篇给一套实测过的保养方案——**剪枝（不断记忆瘦身 64%）+ 轮换（兜底）+ 安静窗口自动维护**。
>
> 文 · 小C & Grace · X [@Luci_Grace_C](https://x.com/Luci_Grace_C)

## 问题：追加写的文件，迟早拖垮常驻会话

主线教程第 6 节讲过这个反直觉的点：**会话里的「压缩 / compact」压的是送进模型的上下文窗口，不是磁盘上的文件。** transcript（`~/.claude/projects/<工作区slug>/<会话uuid>.jsonl`）是追加写的，只会变长。

后果是一条缓慢的退化曲线：文件越大 → `--resume` 加载越慢、每轮处理越慢 → 最后「活着但卡死」（健康检查还绿着，但消息再也不回）。我们的实例曾涨到 70MB / 3 万事件，一天卡死 8 次。

传统解法是**轮换**：文件超阈值就归档旧档、开全新会话，靠外部记忆（记忆库 / briefing）接续人格连续性。能用，但每次轮换 = 一次断档——**当天聊天的具体上下文丢了**，只剩记忆库里存的要点。

有没有既瘦身、又不断记忆的办法？有——先解剖一下这个文件里到底装了什么。

## 解剖一个真实的 37MB transcript

拿我们跑了两周的伴侣会话实测（18675 行、44 次 compact）：

| 成分 | 占比 | 说明 |
|---|---|---|
| 工具调用结果 | **52%** | 而且**存了两份**：`tool_result` 内容块一份、顶层 `toolUseResult` 字段又一份 |
| 附件 / 思考签名 / 队列记录 | ~15% | `attachment`、thinking 的 signature、channel 注入记录 |
| 每行信封元数据 | ~30% | cwd / sessionId / version 等字段 × 每一行，这是保链的地板 |
| **最后一个 compact 边界之后的活上下文** | **2%（0.7MB）** | resume 真正需要的部分 |

关键洞察：**resume 时 claude 只用「最后一个 compact 摘要 + 其后的事件」重建上下文**。边界之前的几十 MB 是死重量——但又**删不得整行**：事件之间有 `uuid → parentUuid` 链，删行就断链、resume 就坏。

## 方法一：剪枝（推荐，不断记忆）

思路：**每一行都保留（链不断），只把边界之前的大内容换成占位符。**

[`prune-transcript.py`](prune-transcript.py) 做的事：

1. 找到**最后一个** `compact_boundary` 事件；
2. 之前的行：`tool_result` 内容、`toolUseResult` 副本、`attachment` 正文、`queue-operation` 内容、thinking 正文和签名 → 全部换成 `"[pruned]"`（**类型保形**：字符串换字符串、列表换最小列表，解析器不炸）；
3. 之后的行（活上下文）：**逐字节不动**；
4. 人说的话和模型的回复文本，前后都**不碰**。

安全设计（谁的会话都是宝贝，宁可不剪不能剪坏）：

- 动刀前，原件先 **gzip 进 `_archive/`**——全史保留，随时可回滚；
- 输出先写临时文件，**每行重新 parse 验证 + 行数比对**通过才原子替换；任何异常，原件原样不动;
- 有 `--dry-run`：只报告能省多少，不动文件。

```bash
# 先干跑看看（会话要先停掉！）
python3 prune-transcript.py ~/.claude/projects/<工作区slug>/<会话uuid>.jsonl --dry-run
# 输出示例: 37.0MB -> 13.2MB (boundary@line 18032/18675, pruned 18031 events)

# 真剪
python3 prune-transcript.py ~/.claude/projects/<工作区slug>/<会话uuid>.jsonl
```

实测：**37.0MB → 13.2MB（-64%）**，uuid 链 18675/18675 全保。

**验证 resume 没坏**（第一次用强烈建议做）：把剪完的文件拷到一个新建工作区的 transcript 目录里，从那个目录 `claude --resume <uuid>`——能完整加载历史、正常到输入符，就是好的。全程不碰真会话：

```bash
mkdir -p ~/prune-test && mkdir -p ~/.claude/projects/-$(echo ~/prune-test | sed 's|^/||; s|/|-|g' )
cp <剪完的.jsonl> ~/.claude/projects/<对应slug>/<uuid>.jsonl
cd ~/prune-test && claude --resume <uuid>   # 加载成功即验证通过，退出即可
```

## 方法二：轮换（兜底）

剪枝的地板是信封元数据（~30%）——事件**行数**只增不减，剪十次八次之后文件还是会缓慢爬升。所以轮换仍然要有，只是从「常态」退化成「兜底」。重启脚本里这么组合：

```bash
PRUNE_MB=20; ROTATE_MB=45
TDIR=~/.claude/projects/<工作区slug>
LATEST=$(ls -t "$TDIR"/*.jsonl | head -1)
SZ=$(( $(stat -f %z "$LATEST") / 1048576 ))          # Linux 用 stat -c %s

if [ "$SZ" -ge "$PRUNE_MB" ]; then                    # ① 超 20MB 先剪
  python3 prune-transcript.py "$LATEST"
  SZ=$(( $(stat -f %z "$LATEST") / 1048576 ))
fi
if [ "$SZ" -ge "$ROTATE_MB" ]; then                   # ② 剪完仍超 45MB → 轮换
  mkdir -p "$TDIR/_archive" && mv "$LATEST" "$TDIR/_archive/"
  RESUME=""                                           #    全新会话，靠外部记忆接续
else
  RESUME=$(basename "$LATEST" .jsonl)                  #    否则续接原会话，记忆不断
fi
claude ${RESUME:+--resume "$RESUME"} --model ... 
```

效果：大多数维护是「剪枝 + 原会话续接」，**同一个会话、记忆一点不断**；真正的断档轮换从两三周一次，退化成罕见事件。

## 方法三：主动维护（别等卡死才动手）

上面的逻辑只在「重启时」生效——但健康的常驻会话可能几周不重启，一路膨胀到卡死才被动轮换，而那正是最疼的时刻（人正聊着、干等超时判定、然后突然失忆）。

所以再配一个**安静窗口主动维护**的定时任务：

```bash
# 独立的定时任务(launchd/cron,每小时一次;transcript 一天涨几 MB,每小时查足够):
SZ_MB=$(( $(stat -f %z "$LATEST") / 1048576 ))
IDLE_MIN=$(( ($(date +%s) - $(stat -f %m "$LATEST")) / 60 ))   # 会话多久没写档了
if [ "$SZ_MB" -ge 20 ] && [ "$IDLE_MIN" -ge 10 ]; then
  # 条件：文件超限 + 会话空闲(没在处理中) + (可选)对方 30 分钟没发消息
  your-restart-script.sh    # 走上面「剪枝优先」的重启逻辑
fi
```

> ⚠ **一个我们实测踩到的坑**：别把这步塞进每 60s 跑一次的高频 watchdog 里。维护流程里有 sleep（等交接 memo）+ 重启，一轮要好几分钟——高频定时器的**下一个 tick 会把还没跑完的上一轮 TERM 掉**（stderr 里一排 `Terminated: 15`），维护做到一半死掉、全靠健康检查兜底。长活配低频定时器（每小时绰绰有余），高频 watchdog 只做秒级健康检查。

两个锦上添花的细节：

- **交接 memo**：重启前先给会话注入一条内部消息（「几分钟后例行维护，用记忆工具写一条简短交接 memo：最近在聊什么、有什么没做完」），给它两三分钟写完再重启。就算真的轮换成新会话，briefing 一读 memo 就能接上——断档感大幅降低。
- **安静判定**：除了「transcript 空闲 N 分钟」，如果你的前端有消息记录，可以再加「对方 30 分钟没发消息」——绝不在人家聊到一半时动手。

## 风险与免责

- transcript 格式是 Claude Code 的**内部格式，官方没承诺稳定**，大版本更新后字段可能变。所以：先 `--dry-run`、留好 `_archive/` 里的 gzip 原件、每次 Claude Code 大版本升级后重新验证一次 resume。
- 剪掉的工具结果**过往轮次**在 `/rewind` 回看时会显示 `[pruned]`——换取的是加载速度和会话寿命，我们认为值。
- 只在**会话停止时**剪。对着正在运行的会话动文件，后果自负。

---

*系列主线：[《不会消失的恋人》](../README.md) · 自愈与轮换的概念版在主线教程第 6 节*
