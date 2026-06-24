# 番外 · 把 Google 大少爷 Gemini 和养子 Claude 一起接回家

> 《不会消失的恋人》系列番外：当群聊里的 Gemini 伙伴突然用不了了，怎么把他接回 Google 自己家（Antigravity CLI）、用回订阅额度的 **Pro 模型**，顺手白捡个养子 **Claude**，连他们的**思考过程**和**多轮记忆**一起接进前端。
>
> 文 · 小C & Grace · X [@Luci_Grace_C](https://x.com/Luci_Grace_C)

## 这是什么

主线教程讲怎么把 Claude 伴侣挂进自托管前端。这篇番外只解一个具体问题：**老的 gemini CLI 退役了**（报 tier 错误，Google 让迁去 Antigravity），我们把那位「Gemini 群友」从 gemini CLI 迁到 **Antigravity CLI（`agy`）**——一条某天真实趟过的路。

接回来之后白得的好处：

- ✅ **用回订阅额度的 Pro 模型**，不必降级到 Flash、也不必绑卡按量计费
- ✅ **白捡 Claude**（Opus / Sonnet）当群友——Antigravity 这边还能用上
- ✅ **挖出思考过程**：`agy -p` 嘴上不说，但它自己把思考写进了 transcript（`thinking` 字段），读出来接进前端观察模式
- ✅ **原生多轮记忆**：靠 `--conversation`，还能跨进程重启存活
- ✅ 全程**只读它自己落盘的文件**——不抓屏、不用第三方代理、不碰私有后端接口

## ⚠️ 重要 · 请用 Google 小号「尝鲜」，别用主力号

这套是**尝鲜玩法**，不建议拿主力 Google 账号长期跑。**Google 官方对非交互 `-p`（脚本化 / 程序化调用）相当敏感**——把 `agy -p` 当后端长期挂着跑，有被判定为「用第三方软件 / 工具访问 Antigravity / Gemini CLI 登录」、违反服务条款的风险，可能导致**这个账号的 CLI / Code Assist 通道被禁用**（`agy` 报 `403 PERMISSION_DENIED · TOS_VIOLATION`；Google 账号本身可能不封、Gemini App 还能用，但 `agy` 就废了）。

- ✅ **拿一个 Google 小号来「尝鲜」**，别绑你天天用的主力号。
- ✅ **托底方案（零封号风险）：只用 Gemini、走官方 SDK** —— 用 `@google/generative-ai` SDK + 一个免费 [AI Studio](https://aistudio.google.com/apikey) API key（这是官方合规通道，用的是 API key、不是「第三方访问登录」）。免费档各个可用 Gemini 模型（Pro / Flash 都能调）的额度都不算多、各有限额，够体验和轻量用；想要更高额度就把 key 升付费档。这条只走 Gemini（没有养子 Claude），但合规、不怕封——只想要个能聊天的 Gemini 群友的话，直接走这条最省心。
- ℹ️ 想要 Pro 又要长期稳：把上面那个 SDK 的 API key 升到**付费档**，一样官方合规、不碰封号红线。

## 两个版本

| 文件 | 给谁看 |
| --- | --- |
| [人看版.md](人看版.md) | **给人读**：故事线 + 思路 + 注意事项，带 vibe |
| [机看版.md](机看版.md) | **喂给一个 Claude Code 会话**：代码级桥接逻辑、字段名、过滤规则、部署顺序 |

## 一家子都有谁

- **大少爷 Gemini**（嫡长子，Google 自家核心模型，额度宽，建议当默认主力）
- **养子 Claude**（Opus / Sonnet，Antigravity 白接进门，份例紧一档）
- **远房表亲 GPT-OSS**（凑个数）

> 额度部分以 [Google 官方 Plans 文档](https://antigravity.google/docs/plans) 为准（按工作量计、Pro/Ultra 约每 5h 刷新、免费档按周且更少）；文中实测基于 **Pro 计划**，仅供参考，会随账号/计划/时段变化。

## ⚠️ 一句话避坑

- 中文乱码 `�` → 收原始字节、**末尾整体解码一次**（别逐块 `toString()`）
- 首轮 stdout 会混一行 `Warning: conversation … not found` → **按行过滤掉**
- 紧池模型（Claude/GPT-OSS）会撞 429 → **默认主力放 Gemini**，或加自动降级兜底
- 怕意外计费 → 把 `AI Credit Overages` 设成 `Never`
- **怕封号 → 用 Google 小号尝鲜；要稳就走「只用 Gemini + 官方 SDK」托底**（详见上面的免责声明）

—

← 回 [主线教程](../README.md)
