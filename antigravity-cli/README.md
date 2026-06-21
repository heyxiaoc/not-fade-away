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

—

← 回 [主线教程](../README.md)
