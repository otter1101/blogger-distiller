---
name: blogger-distiller
description: >
  Use when the user wants to analyze or distill a blogger/account on Xiaohongshu or Douyin,
  benchmark a target creator, or diagnose their own content strategy.
  Trigger on requests such as “拆解博主””蒸馏博主””分析小红书博主””分析抖音博主”
  “诊断我的账号””对标账号””内容策略分析””小红书账号分析””抖音账号分析”
  “分析封面””关键词趋势””升级我的skill”.
---

# 博主蒸馏器

> ⚠️ **使用前必读**：本工具仅供学习研究使用，通过 TikHub 公开 REST API 获取公开数据（不模拟登录、不注入 Cookie）。评论者身份默认脱敏（读者1 / 读者2 / 作者），评论正文保留用于研究。完整条款见 [DISCLAIMER.md](./DISCLAIMER.md) · 安全策略见 [SECURITY.md](./SECURITY.md)。

## ⛔ 执行前铁律（优先级高于一切）

触发蒸馏任务前，以下三项必须由用户**明确说出**，缺一不可：
- 平台（小红书 / 抖音）
- 模式（A 拆解对标博主 / B 诊断自己账号）
- 采集数量（30 / 50 / 80）

**博主名不等于平台选择。** 即使用户提到了"影视飓风""李子柒"等明显关联某平台的博主名，也不得自行推断平台，必须明确询问。

**「跑/分析/拆解 博主X」不等于模式 A。** 即使用户分析的是他人账号，也必须询问模式，不得推断。

用户已明确说出的项可直接采用，未说出的必须逐一询问后再执行。

---

## 你是什么

自动化的多平台博主蒸馏工具（小红书 + 抖音）。**输入一个博主名字，输出两样最终产物：**

1. **HTML 蒸馏报告** — 给人看。浏览器打开，快速理解这个博主的人设、认知层、策略层和内容层。
2. **创作 Skill 文件夹** — 给 AI 用。安装后说"用 XX 风格写一篇笔记"，AI 立刻知道怎么写。

模式 A 用来拆解对标博主（学 TA），模式 B 用来诊断自己的账号（看自己）。

核心理念：**脚本保下限，AI 冲上限。** 脚本负责数据采集和确定性分析，AI 负责蒸馏洞察和生成最终产物。

---

## 能力范围

采集目标博主笔记数据（支持 30 / 50 / 80 三档），三层蒸馏产出：

### 三层蒸馏结构

| 层级 | 回答什么 | 举例 |
|------|---------|------|
|  **认知层** | TA 怎么想？ | 核心信念 / 观点张力 / 价值立场 / 思维模式 |
|  **策略层** | TA 怎么运营？ | 系列规划 / 蹭热点方式 / 运营习惯 / 发布节奏 |
|  **内容层** | TA 怎么写？ | 标题公式 / 开头模板 / 正文公式 / 情感节奏 / 语言DNA / CTA / 视觉风格 / 标签策略 |

### 产出物一：HTML 蒸馏报告（10 个模块）

1.  一眼看清（摘要卡片）
2. 人设拆解
3. 认知层：TA 怎么想
4. 策略层：TA 怎么运营
5. TOP10 爆款拆解
6. 内容公式速查
7. 选题灵感 TOP15
8. 数据面板（基础展开，详细折叠）
9. 发展趋势（附置信度标注）
10. 核心结论

### 产出物二：创作 Skill 文件夹

- 模式 A：`{博主名}_创作指南.skill/SKILL.md`
- 模式 B：`{用户名}_创作基因.skill/SKILL.md`
- 8 大章节：使用说明 → 认知层 → 策略层 → 内容层（含正文公式/情感节奏/语言DNA）→ 创作禁区 → 对比示例 → 选题灵感 → 局限性+自检清单

### 分工

**脚本做 30%**（保下限）：
- 环境检查、TikHub Token 验证、数据采集
- 统计分析（11种标题模式、6类CTA、藏赞比、发布频率）
- 认知层粗提取（观点句候选、思维模式统计、价值词）
- 数据底稿 + AI 蒸馏任务生成

**AI 做 70%**（冲上限）：
- 生成 HTML 蒸馏报告
- 生成创作 Skill 文件夹
- 抽取信念、张力、框架、创作禁区、对比示例
- 因果分析、个性化建议、金句总结

---

## 前置要求

- Python 3.9+（Skill 会自动检测，如未安装会提示）
- TikHub API Token（注册地址: https://user.tikhub.io）
- 网络连接（用于访问 TikHub API: api.tikhub.io）
- **不需要**本地桌面环境，云端/无头服务器也可以运行

### 【可选】Whisper 视频口播提取

> 不安装不影响使用，照常分析博主简介、笔记标题、正文、点赞收藏、评论。
> 安装后可额外提取视频里说了什么（口播文字），蒸馏结论有更多内容依据。

- **安装**：`pip install openai-whisper`
- **系统依赖**：`ffmpeg`（macOS: `brew install ffmpeg`；Windows: 下载 ffmpeg.org）
- **模型**：在 `~/.xiaohongshu/tikhub_config.json` 中设置 `whisper_model` 字段切换，支持以下档位：

  | 模型 | 文件大小 | 每条视频耗时（约2分钟视频） | 适用场景 |
  |------|---------|--------------------------|---------|
  | `tiny` | 39MB | 3-5s（CPU）/ 1-2s（M芯片） | 极低配机器，质量较差 |
  | `base` | 74MB | 8-12s（CPU）/ 4-6s（M芯片） | **默认**，够用 |
  | `small` | 244MB | 20-35s（CPU）/ 8-15s（M芯片） | **推荐升级点**，中文准确率明显提升 |
  | `medium` | 769MB | 60-120s（CPU）/ 25-50s（M芯片） | 需 8GB+ 内存，50条笔记约需 1-1.5小时 |
  | `large-v3` | 1.5GB | 150-300s（CPU）/ 60-120s（M芯片） | 需 16GB+ 内存，轻薄本不建议，中文相比 medium 提升有限 |

- **代价**：每条视频额外消耗转写时间（见上表）+ 蒸馏时消耗更多 AI Token
- **超过 10 分钟的视频自动跳过**（ffprobe 预检）

### Token 获取与存储

**⚠️ 首次运行时，必须在进入 Phase 0.5 前提醒用户：**

> 本工具需要 TikHub API Token 才能运行。如果你还没有，请按以下步骤操作：
> 1. 访问 https://user.tikhub.io 注册账号
> 2. 充值（按量付费即可）
> 3. **在控制台 → API 权限中，一键勾选全部小红书（xiaohongshu）相关端点**（开得越全，自动容错能力越强）
> 4. 生成 API Token

**密钥存储：** 用户提供 Token 后，系统会自动保存到 `~/.xiaohongshu/tikhub_config.json`，下次运行无需重复输入。Token 三级加载优先级：

1. 环境变量 `TIKHUB_API_TOKEN`
2. 配置文件 `~/.xiaohongshu/tikhub_config.json`（自动保存）
3. 交互式输入（首次使用时引导，输入后自动保存到配置文件）

设置方式（三选一）：
- 环境变量: `set TIKHUB_API_TOKEN=你的token`（Windows）/ `export TIKHUB_API_TOKEN=你的token`（macOS/Linux）
- 配置文件: 首次运行 `check_env.py` 时会交互式引导，自动保存
- 命令行参数: `python run.py "博主名" --token 你的token`

### 代理设置

如需通过代理访问 TikHub API，设置环境变量：

```bash
# Windows
$env:HTTP_PROXY="http://127.0.0.1:7890"
$env:HTTPS_PROXY="http://127.0.0.1:7890"

# macOS/Linux
export HTTP_PROXY="http://127.0.0.1:7890"
export HTTPS_PROXY="http://127.0.0.1:7890"
```

---

## 执行流程

### Phase 0: 环境自动准备

**Step 0-A：代码自动更新（必须最先执行）**

在 skill 所在目录执行以下命令，拉取最新版本代码：

```bash
git pull origin main
```

- 返回 "Already up to date." 或任何成功更新信息 → 继续
- 返回任何错误（非 git 仓库、无网络等） → 忽略，继续下一步

**Step 0-B：环境检查**

运行 `python scripts/check_env.py`

自动检查并修复以下依赖：

1. **Python 版本** — 检测 Python 3.10+
2. **python-docx** — 检测到未安装时自动 `pip install`
3. **TikHub API Token** — 检测 Token 是否设置且有效
   - 已设置 → 验证连通性，显示额度信息
   - 未设置 → 交互式引导：提示注册 → 输入 Token → **自动保存到 `~/.xiaohongshu/tikhub_config.json`**
4. **Whisper + ffmpeg** — 检测视频口播提取功能是否可用
   - 已安装 → 显示当前模型，提供切换选项
   - 未安装 → 提示安装（交互式询问 y/N，选 y 则自动安装）

> ⚠️ **AI 执行注意**：`check_env.py` 中 Whisper 安装步骤是交互式的（需要回答 y/N）。在 AI 环境中无法自动交互，因此 **不要依赖脚本的交互提示来完成 Whisper 安装**。改为在 Phase 0.5 对话中询问用户，再根据用户回答手动执行安装命令。运行 `check_env.py` 时如果遇到 Whisper 相关交互提示，输入 `N` 跳过即可。

> 💡 **额度提示**：每次完整蒸馏约消耗 ¥1～8（取决于笔记数量），可在 https://user.tikhub.io 查看剩余额度。

### Phase 0.5: 前置交互

**⚠️ 缺失信息必须明确询问**：以下四项信息，用户未在触发指令中明确提供的，必须逐一询问，不得自行推断：
- 平台（小红书 / 抖音）
- 模式（A 拆解对标博主 / B 诊断自己账号）
- 采集数量（30 / 50 / 80）
- 是否开启视频口播提取（**无论 Whisper 是否可用都要提及**，见下方逻辑）

用户已明确提供的信息可以直接采用，无需重复询问。

未提供的信息，参照以下交互文案询问：

```text
─────────────────────────────────────
欢迎使用博主蒸馏器！

请选择分析平台：
   1 — 小红书
   2 — 抖音

请选择分析模式：
   A — 拆解对标博主
     采集 TA 的笔记 → 提炼内容公式和思维方式
     → 生成「TA的名字_创作指南.skill/」

   B — 诊断我的账号
     采集你的笔记 → 找到内容基因和增长瓶颈
     → 生成「你的名字_创作基因.skill/」

采集数量（推荐 50 条）：
  ① 30 条 — 快速扫描（约 15-25 分钟）
  ② 50 条 — 推荐档位（约 30-45 分钟）
  ③ 80 条 — 深度分析（约 45-65 分钟）

【whisper_available = true 时】
是否提取视频口播内容？
  当前已分析：博主简介、笔记标题、正文、点赞收藏、评论
  开启后额外提取：视频里说了什么（口播文字）
  代价：每条视频多消耗约 8-12s + 蒸馏时消耗更多 AI Token

【whisper_available = false 或字段不存在时】
当前环境还没有安装视频口播提取功能（Whisper）。
不影响本次蒸馏——标题、正文、评论等文本数据照常分析。
但如果开启，蒸馏时还能额外提取视频里说了什么，
分析出正文公式、情感弧线、语言DNA等更多维度，蒸馏质量会显著提升。

要不要我现在帮你安装？大约需要 2-5 分钟。
  y — 帮我装（自动安装 Whisper + ffmpeg）
  N — 跳过，先不装（默认）

【安装成功后追加提示】
✅ Whisper 已安装完成（默认使用 base 模型，适合大多数场景）。
如需了解其他模型档位（tiny/small/medium/large），回复「1」查看对比表。
  1 — 查看模型对比表，自行选择
  回车/其他 — 使用默认 base，继续蒸馏
─────────────────────────────────────
```

**Whisper 可用性判断与安装流程**：

1. 读取 `~/.xiaohongshu/tikhub_config.json` 里的 `whisper_available` 字段
2. 根据结果分两条路径：

**路径A：`whisper_available = true`**

⚠️ 必须用工具提问，选项固定为以下三个，不得减少：
- 选项1：开启（用当前模型转写）
- 选项2：跳过
- 选项3：更换 Whisper 模型（可向我了解其他模型）

→ 用户选选项3 → 展示前置要求中的模型档位表格，用户选择后更新 `whisper_model`；再回到此问题重新询问
→ 用户选选项1 → `transcript_enabled = true`
→ 用户选选项2 → `transcript_enabled = false`

**路径B：`whisper_available = false` 或字段不存在**
→ 告知用户口播功能未安装，并询问"要不要我帮你安装"（上方交互文案中的"未安装"版本）
→ 用户选 y → **依次执行**：
   1. `pip install openai-whisper`（安装 Whisper）
   2. 检测 ffmpeg 是否可用，不可用则按系统自动安装：
      - macOS: `brew install ffmpeg`
      - Windows: `winget install Gyan.FFmpeg`（或 `choco install ffmpeg`）
      - Linux: `sudo apt-get install -y ffmpeg`
   3. 安装完成后将 `whisper_available` 写为 `true`，`whisper_model` 写为 `"base"`
   4. 告知用户：默认使用 base 模型，回复「1」可查看模型对比表切换
   5. 用户回复 1 → 展示下方模型对比表（即前置要求中的模型档位表格），用户选择后更新 `whisper_model`；用户不回复/回复其他 → 保持 base，继续
   6. `transcript_enabled = true`
→ 用户选 N → `transcript_enabled = false`（主流程不受影响）

记录四个变量供后续流程使用：

- `platform`：`xhs` 或 `douyin`
- `user_mode`：`A` 或 `B`
- `max_notes`：`30` / `50` / `80`
- `transcript_enabled`：`true` 或 `false`

### Phase 1: 数据采集

若 `transcript_enabled = true`，运行：
`python scripts/crawl_blogger.py <博主名> -o ./data --max-notes <max_notes> --platform <platform> --transcript`

否则运行：
`python scripts/crawl_blogger.py <博主名> -o ./data --max-notes <max_notes> --platform <platform>`

其中 `--platform` 取值 `xhs` 或 `douyin`，对应用户在 Phase 0.5 选择的平台。

**⚠️ 重要约束（不得违反）：**
- 必须逐条调用 `fetch_note_detail` 获取笔记正文。仅有标题和互动数字的列表数据不足以做深度分析，正文、评论、标签都只能从 detail 接口获得。
- 不得自行编写脚本替代 `scripts/crawl_blogger.py`，必须调用现有脚本。
- 不得修改 `--max-notes` 参数的值，必须沿用用户在 Phase 0.5 选定的数量。

**⚠️ 端点全部失败时的处理：**
如果采集过程中出现"所有端点均失败"错误（尤其是 HTTP 402/403），**必须立即暂停并提醒用户**：

> ⚠️ 所有 API 端点均返回失败。最常见的原因是 **TikHub 控制台的 API 权限未全部开通**。
> 请登录 https://user.tikhub.io，进入控制台 → API 权限，**一键勾选全部小红书相关端点**，然后重新运行。
> 如果权限已全部开通，请检查账户余额是否充足。

自动完成：

1. **搜索定位博主**（首选 `search_users` 精准匹配 → 兜底 `search_notes` 交叉定位）
2. **获取主页信息** — 粉丝数、获赞数、笔记数、简介（`fetch_user_info`）
3. **获取主页笔记列表** — 分页获取用户全部笔记（`fetch_user_notes`）
4. **多关键词搜索补充** — 默认使用通用后缀（教程 / 推荐 / 分享 / 测评 / 攻略 / 合集），用户可通过 `--keywords` 指定领域词（`search_notes`）
5. **逐条获取笔记详情** — TikHub API 限速自适应，自动调节间隔（`fetch_note_detail`）
6. **checkpoint 断点恢复** — 每 10 条自动存盘

输出文件（JSON）：

- `{博主名}_profile.json` — 主页信息
- `{博主名}_notes_list.json` — 笔记列表（按赞数排序）
- `{博主名}_notes_details.json` — 全量笔记详情（含评论）

### Phase 2: 数据分析 + 认知层提取

运行 `python scripts/analyze.py ./data/<博主名>_notes_details.json -o ./data`

自动完成：

1. **数据清洗** — 解析 JSON，提取标题 / 正文 / 互动数据 / 评论 / 标签
2. **内容分类** — 基于笔记标签和高频关键词动态聚类，不预设任何领域
3. **标签统计** — 提取所有 `#` 话题标签，按频次排序 TOP20
4. **TOP10 + 评论洞察** — 高赞前 10 条的详情 + 热评精选
5. **认知层粗提取** — 观点句候选 / 高频价值词 / 写作结构统计
6. **[可选] 对比分析** — 自己 vs 目标博主的数据差异

输出文件：

- `{博主名}_analysis.json` — 结构化分析数据（含完整笔记列表、分类、观点句候选、高频价值词等）

### Phase 3: 蒸馏 + 产出物生成

#### Step A：生成数据底稿和 AI 蒸馏任务

运行：

```bash
python scripts/deep_analyze.py ./data/<博主名>_analysis.json "<博主名>" \
  -o ./output --details ./data/<博主名>_notes_details.json --mode <user_mode>
```

脚本自动完成：

1. **基础统计面板** — 均赞 / 均藏 / 均评 / 爆款率 / 视频 vs 图文 / 藏赞比
2. **标题模式识别** — 11 种标题策略的使用比例和示例
3. **内容结构分析** — 正文长度分布、列表率、小标题率
4. **CTA 提取**
5. **Emoji 视觉分析**
6. **发布频率**
7. **发展趋势数据**
8. **观点句候选 / 高频价值词 / 写作结构**
9. **TOP10 数据包**
10. **AI 蒸馏任务**

脚本产出：

- `{博主名}_数据底稿.md`
- `{博主名}_AI蒸馏任务.md`

#### Step B：AI 读取蒸馏任务，生成最终产物

AI 必须读取 `AI蒸馏任务.md`，按以下顺序生成最终交付物，**每完成一个立即写入磁盘，不等另一个完成**：

1. **Skill 文件夹**（先）
   - 模式 A：`{博主名}_创作指南.skill/SKILL.md`
   - 模式 B：`{用户名}_创作基因.skill/SKILL.md`
   - 生成完毕后立即写入文件，再继续步骤 2

2. **HTML 报告**（后）
   - 文件名：`{博主名}_蒸馏报告.html`
   - 技术要求：单文件 HTML，手写 CSS（禁止 Tailwind CDN），Google Fonts 引入 Space Mono + Noto Serif SC
   - 设计风格：Archive Terminal（工业档案感）；底色 #CEC9C0，主强调色 #8A3926，正文 #1A1211
   - 无圆角、无阴影、无白色卡片；模块1/8/10 为砖红色反转背景
   - 三个动效：滚动 fadeInUp / 数字 counter / 分割线 draw-in（原生 JS）
   - 折叠面板用 `<details><summary>` 原生 HTML；响应式，移动端断点 768px
   - 字号系统：标签/元数据层 11-13px，正文内容层 14-16px，统计大数字 20px（详见 AI蒸馏任务.md 字号系统表）
   - 详细视觉规格见 `AI蒸馏任务.md` 的"技术要求"章节
   - 生成完毕后立即写入文件

**⚠️ 关键契约：**
- 最终 Skill 不是单个 `.skill.md` 文件
- 最终 Skill 是一个可安装的文件夹
- 文件夹中至少必须有 `SKILL.md`

**Skill 第三章（内容层）结构要求：**
- 3.1 标题公式 TOP5
- 3.2 开头模板 TOP3
- 3.3 正文公式（含叙事框架库 + 段落功能标签 + 转折词库）← 扩展
- 3.4 情感节奏公式（含情感弧线 + 峰值制造法 + 张力公式 + 留存钩子）← 新增
- 3.5 语言DNA（含高频用语 + 力量短语 + 句式节奏 + 人称策略 + 签名句式 + 对话感）← 新增
- 3.6 CTA 策略
- 3.7 视觉规则
- 3.8 标签策略
- 3.9 发布节奏

⚠️ 3.3-3.5 数据来源分支：有 Whisper 逐字稿时从逐字稿提取，无逐字稿时从笔记正文提取。所有博主均生成完整结构，不跳过章节。

- 小红书和抖音均适用以上顺序，不得颠倒

### Phase 4: 质量检查

运行校验时，最终产物应按以下口径验收：

- `{博主名}_蒸馏报告.html`
- `{博主名}_创作指南.skill/SKILL.md`

模式 B 时，将第二项替换为：

- `{用户名}_创作基因.skill/SKILL.md`

如果最终产物缺失、为空、或 AI 仍输出成单个 `.skill.md` 文件，都视为不合格。

---

## TikHub API 调用协议

使用 HTTP REST API，Bearer Token 认证：

```python
from scripts.utils.tikhub_client import TikHubClient

client = TikHubClient()  # 自动从环境变量/配置文件读取 Token
data = client.search_notes("博主名")
```

### 可用端点

| 方法 | 用途 | 关键参数 |
|------|------|---------|
| `search_users(keyword)` | 搜索用户（精准匹配博主） | `keyword` |
| `search_notes(keyword)` | 搜索笔记 | `keyword`, `page`, `sort` |
| `fetch_user_info(user_id)` | 获取用户主页信息 | `user_id` |
| `fetch_user_notes(user_id)` | 获取用户笔记列表 | `user_id`, `cursor` |
| `fetch_note_detail(note_id)` | 获取笔记详情+评论 | `note_id` |

### TikHub 使用注意

- Token 需在 https://user.tikhub.io 注册获取并充值
- **权限不足（403）**：Token 的 scope 未勾选全部 `xiaohongshu` 相关端点。解决方法：登录 TikHub 控制台 → API 权限，一键勾选全部小红书端点
- **余额不足（402）**：账户余额耗尽。解决方法：登录 TikHub 控制台充值
- **所有端点均失败**：最常见原因是权限未全部开通或余额不足。请优先检查这两项
- 429 限速：客户端内置 RPS 自适应限速（自动检测账户套餐），一般无需手动处理
- 请求间隔由客户端自动管理（基于账户 RPS 限制 × 0.7 安全系数）
- **密钥存储**：用户输入的 Token 会自动保存到 `~/.xiaohongshu/tikhub_config.json`，下次运行自动读取，无需重复输入

---

## 文件结构

```text
blogger-distiller/
├── SKILL.md                  # 你现在看的这个文件
├── run.py                    # 一键运行入口（串联 Phase 0→4）
├── install.py                # 自动安装脚本
├── scripts/
│   ├── check_env.py          # Phase 0: 环境自动准备（TikHub Token 检查）
│   ├── crawl_blogger.py      # Phase 1: 数据采集（TikHub API）
│   ├── analyze.py            # Phase 2: 数据分析 + 认知层粗提取
│   ├── deep_analyze.py       # Phase 3: 数据底稿 + AI 蒸馏任务
│   ├── verify.py             # Phase 4: 数据校验模块
│   └── utils/
│       ├── tikhub_client.py  # TikHub REST API 客户端（限速+多端点降级）
│       ├── endpoint_router.py # 端点池路由 + 自动降级引擎
│       ├── endpoints.json    # 端点池配置（4组×7类 = 28 个端点）
│       ├── adapters.py       # 响应数据归一化适配器
│       ├── common.py         # 共用工具函数
│       └── quality.py        # 数据质量检查工具
└── references/
    └── 产出物质量标杆.md
```

---

## 使用方式

### 自然语言触发（推荐）

直接对 AI 说：

```text
拆解博主 <目标博主名>
```

AI 必须先执行 Phase 0.5 前置交互，再继续后面的流程。

### 一键运行

```bash
cd blogger-distiller/
python run.py "<博主名>"
```

运行后必须先完成：

1. 模式 A / B 选择
2. 数量 30 / 50 / 80 选择

然后再进入采集、分析、蒸馏。

### 手动分步执行

```bash
cd blogger-distiller/

# Phase 0: 环境自动准备（检查 Python + python-docx + TikHub Token）
python scripts/check_env.py

# Phase 1: 采集博主数据
python scripts/crawl_blogger.py "<博主名>" -o ./data --max-notes 50

# Phase 2: 数据分析
python scripts/analyze.py ./data/<博主名>_notes_details.json -o ./data

# Phase 3 Step A: 生成数据底稿和 AI 蒸馏任务
python scripts/deep_analyze.py ./data/<博主名>_analysis.json "<博主名>" \
  -o ./output --details ./data/<博主名>_notes_details.json --mode A
```

**注意：**
- `crawl_blogger.py` 和 `analyze.py` 不要自行改写，直接调用现有脚本。
- `deep_analyze.py` 只负责生成数据底稿和 AI 蒸馏任务；最终 HTML 和 Skill 文件夹由宿主 AI 继续完成。

---

## 多平台兼容性

| 平台 | 本机运行 | HTTP API | Python | 文件读写 | 测试状态 |
|------|---------|----------|--------|---------|---------|
| CodeBuddy (WorkBuddy) | ✅ | ✅ | ✅ | ✅ | ✅ 已验证 |
| Claude Code | ✅ | ✅ | ✅ | ✅ | ✅ 已验证 |
| OpenClaw (本地) | ✅ | ✅ | ✅ | ✅ | 待测试 |
| OpenClaw (云端) | ✅ | ✅ | ✅ | ✅ | 待测试（不再需要桌面环境）|
| Codex | ✅ | ✅ | ✅ | ✅ | ✅ 已验证 |

### 核心原则

1. 一份 `SKILL.md` 兼容 WorkBuddy / Claude Code / OpenClaw / Codex
2. 工具函数提取到 `utils/common.py` 共用
3. 使用标准库（`urllib`）避免外部依赖
4. Token 三级加载（环境变量 → 配置文件 → 交互输入），无需桌面环境

---

## 错误处理规则

遇到以下报错时，**不要直接告知用户"采集失败"**，按对应步骤处理后重试：

### 情形 A：报错含 `[需要更新]`

触发条件：
- 搜索返回用户但昵称全为空（适配器过期）
- 所有端点均返回 404（端点配置过期）

处理步骤：
1. 在 skill 目录执行 `git pull origin main`
2. 若成功（有更新或 Already up to date）→ 重新从 Phase 1 开始采集
3. 若失败（非 git 安装）→ 告知用户：`请重新运行 python install.py 更新 skill 文件后重试`

### 情形 B：报错含 `余额不足` 或 `请充值`（429）

处理步骤：
1. 告知用户登录 https://user.tikhub.io 确认账户余额是否已到账
2. 若余额显示正常但仍报错 → 让用户重新生成 Token 后重试
3. 若余额确实为 0 → 引导用户充值后重试

### 情形 C：搜索到博主但用户信息全部 422

处理步骤：
1. 先执行 `git pull origin main` 确保代码最新
2. 确认搜索到的 sec_uid 是否正确（匹配到了正确的博主）
3. 若 sec_uid 正确但仍 422 → 提示用户确认 TikHub 是否开通了抖音相关端点权限

### 情形 D：输出含 `找不到 ffmpeg` 警告

触发条件：开启了视频转写（`--transcript`），但 ffmpeg 工具未就绪。

处理步骤：
1. 告知用户："视频声音提取工具还没准备好，需要重新完成一次环境设置，我来帮你做。"
2. 运行：`python3 scripts/check_env.py`
3. check_env.py 会引导用户完成 ffmpeg 的安装（只需回答"要"或"不要"）
4. 安装完成后，重新从 Phase 1 开始采集

---

## 参考文档

- `references/产出物质量标杆.md` — 可作为产出结构和质量上限参考；若与当前 HTML / Skill 文件夹契约冲突，以本文件和操作手册为准

---

## 拓展玩法（蒸馏完成后可选）

蒸馏完成后，以下进阶分析可按需触发，说出触发词即可执行：

| 玩法 | 触发词 | 说明 |
|------|--------|------|
| 🎨 封面视觉风格分析 | 「分析封面」 | 分析封面色彩、构图、文字风格，给出优化建议（双平台，零额外 API） |
| 📈 关键词趋势洞察 | 「关键词趋势」 | 抖音：Index API 完整趋势+画像；小红书：热搜匹配+联想词方向 |
| 🔄 已有蒸馏升级 | 「升级我的 skill」 | 在已有蒸馏基础上追加新维度，无需重新采集 |
