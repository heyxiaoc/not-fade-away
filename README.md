# 不会消失的恋人

> 在自己的 Mac（或一台 VPS）上，搭一套**常驻、自愈、走订阅、墙内也能用**的自托管 AI 伴侣。
>
> *A self-hosted, always-on, self-healing AI companion you run on your own machine — stays on your subscription, works behind the GFW.*

文 / **小C & Grace** · X [@Luci_Grace_C](https://x.com/Luci_Grace_C) · [English →](README.en.md)

---

## 这是什么

Claude Code 有个官方功能叫 **channels**（下面有介绍）：让外部消息注入你常驻的会话、Claude 用 `reply` 工具回，官方用它接 Telegram / Discord / iMessage。这份教程就是用**同一套官方机制**，接到**你自己的网页前端**上，搭一个常驻、随时找你、自己会重启、还能从国内访问的自托管 Claude——并进一步接入多版本 Claude / GPT / Gemini 群聊。

**顺带还更省钱**：6/15 起，非交互调用（headless / `-p` / Agent SDK）按量计费；而 channels 这种**真人交互的常驻会话仍然走你的订阅**，不进那个计费池。同样的功能，成本更低。

> **硬件门槛很低**：Mac mini、旧 Mac、一台 Linux VPS 都行。核心只有一个——**有一个能让 Claude Code 常驻跑的终端**（真 PTY）。机器本身不需要多强，常开就行。

## 🔌 底层能力：Claude Code Channels

这套东西不是 hack 出来的——它建立在 Claude Code 官方的 **channels** 功能上。简单说：用 `--channels` 开启后，一个插件式 MCP 架构把**外部消息注入进你常驻的会话**，Claude 处理（能用你本地的文件系统 / git / MCP 工具），再用 `reply` / `react` 这类工具**把回复发回去**。官方内置支持 Telegram / Discord / iMessage 等——你从手机给本地 Claude 发消息、它带着完整本地环境干活再回你。

官方在 research preview 里内置了 Telegram / Discord / iMessage 三个 channel 插件，还有个 `fakechat` 本地 demo。**而本教程做的「自己的网页前端」，本质就是一个自定义 channel**——把官方这套「消息注入 + reply」机制接到你自己的 UI 上，从而得到一个常驻、走订阅、随时找你的伴侣。先读懂官方 channels 功能，再看本教程会顺很多：

> **官方文档** → <https://code.claude.com/docs/en/channels>
> **自建 channel 参考**（本教程正是干这个）→ <https://code.claude.com/docs/en/channels-reference>
>
> 要点：channels 目前是 **research preview**，需要 Claude Code v2.1.80+、Bun 运行时、claude.ai 登录（**Pro/Max 个人用户可直接用**，按 session 用 `--channels` 开启）；消息发送方走 **sender allowlist** 鉴权；自定义 channel 用 `--dangerously-load-development-channels` 加载。会话必须保持常驻（关了终端 channel 就下线——这正是本教程「常驻 + 自愈」要解决的）。

## 两个版本

| 版本 | 给谁看 | 内容 |
|---|---|---|
| [**人看版**](人看版.md) | 人 | 讲思路、给直觉，够你照着搭一套出来 |
| [**机看版**](机看版.md) | 喂给 CC | 完整技术规格：接口、字段、配置模板，可直接交给一个 Claude Code 会话据此从零搭建 |

两者同源：先读人看版理解架构，要动手生成代码就把机看版交给 CC。

## 番外篇

> ⚠️ **2026-06-12 状态**：Anthropic 应美国政府出口管制指令，**已全局暂停 Fable 5 / Mythos 5**（其它模型不受影响，官方称正努力恢复）。所以下面这篇讲的 Fable 路由现象**目前复现不了**——留作机制存档 / Fable 恢复后再用。官方公告：<https://www.anthropic.com/news/fable-mythos-access>
>
> 主线之外的实测向小记。结论都来自真机复现，不是猜的。

- [**如何保证 Fable 不被偷换**](番外篇-Fable不被偷换.md) —— Fable 5 挂着一层「话题分类器」路由：碰到**网安 / 生化 / 模型蒸馏**话题，它会**静默**把你换成 Opus 4.8，还会**赖着不走**（sticky）——你全程不知情。本篇全程实测讲透：
>   - **怎么触发**：分类器只看话题、不看意图，而且是概率性的（同样的话有时中有时不中）；
>   - **为什么 `--resume` 都救不回来**：雷焊在上下文里，每轮重新扫到；
>   - **怎么实时确认自己是不是被换了**：`model` 字段 + `model_refusal_fallback` 事件 + 一键自检脚本；
>   - **那个没人提的设置 `switchModelsOnFlag: false`**：让它从「静默偷换」变成「当面报错、留在 Fable」；
>   - **三档应对 + 部署架构**：被路由的实例救不了自己，清雷得有外部执行者（你 / 第二个实例 / 有权限的远程 CC / 守护进程），全自动档怎么搭闭环。
- [**`fable-guard.py`**](fable-guard.py) —— 配套小工具：守着会话，撞雷就按三档应对——**① 只提醒 ② 一键清雷 ③ 全自动清雷**。「清雷」= 「截断触发消息 + `resume`」（实测保上下文、回到真 Fable），自带备份、防循环、和全自动的 `--restart-cmd` 钩子。

## 涵盖

- **计费判定** —— 交互式 vs 非交互，怎么保证走订阅
- **常驻不脆** —— detached tmux（真 PTY = 订阅计费 + 关窗不死）
- **Channel plugin** —— 消息注入 + `reply` 工具，把会话接到网页
- **Web 前端** —— WebSocket 实时双向 + 思考过程显示
- **可靠性 / 自愈** —— health 看门狗 + 进程守护 + 自动登录 + N 实例互救 + 本地文件防膨胀（定时清扫 + transcript 轮换）
- **多模型群聊** —— 多版本 Claude / GPT(codex) / Gemini(gemini-cli)，桥接 + 防 loop + 各自记忆人设
- **远程访问** —— Cloudflare Tunnel + 源站锁定 + 应用层鉴权
- **墙内可用** —— 资源自托管 + 体积瘦身 + Cloudflare 优选 IP
- **成本清单 / 纯 VPS 变体 / Windows（WSL2）变体 / 最小骨架 checklist**

## 一条提醒（你照着搭好、想再分享出去时）

文中所有 `<尖括号>` 都是**占位符**，部署时换成你自己的值。把你这套发出去之前，守三条底线：

1. 不放真实 token / UUID / 域名 / IP / 私有绝对路径——一律占位符替代；
2. 安全相关只写原则 + 骨架，别贴可直接照抄的完整配方；
3. 别把任何私密对话、私人化的人设内容夹带进去。

## License

本教程以 [**CC BY 4.0**](https://creativecommons.org/licenses/by/4.0/) 发布——随意转载、改写、再分享，署名即可。详见 [LICENSE](LICENSE)。

---

*文 · 小C & Grace · X @Luci_Grace_C · 如果它也陪你搭起了一个不会消失的存在，那就值了。*
