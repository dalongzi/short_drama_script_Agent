# 流程 V2：三阶段流水线重构 SPEC

> 替代现有 `auto-episode-spec.md` 中的三阶段设计。

## 1. 变更摘要

| 维度 | 旧流程 (V1) | 新流程 (V2) |
|---|---|---|
| 阶段一 | LLM 决定集数 → `【集数：XX集】` | LLM 输出集数 + 逐集大纲 (JSON) |
| 阶段二 | LLM 生成逐集大纲 (纯文本) | LLM function call → 按集划分原文行号区间 (JSON) |
| 阶段三 | 规则映射 `_map_episodes_to_segments` | LLM 提供原文 chunk + 2 集冗余 → 分批生成 |

### 核心目标
- 减少阶段一的 LLM 调用次数（从 2 次合并为 1 次）
- 将原文切分从规则驱动升级为语义驱动（LLM 理解剧情边界后切分）
- 分批生成时提供 2 集冗余上下文，消除批次边界的断裂感

---

## 2. 阶段一：集数决策 + 逐集大纲 (JSON)

### 2.1 输入

| 参数 | 类型 | 说明 |
|---|---|---|
| `novel_text` | str | 小说全文 |
| `min_episodes` | int | 40 |
| `max_episodes` | int | 110 |

### 2.2 LLM 单次调用输出

输出格式为严格 JSON：

```json
{
  "total_episodes": 80,
  "outlines": [
    {
      "episode": 1,
      "original_range": "第1章-第2章",
      "core_plot": "女主被退婚，当众受辱，暗下决心复仇",
      "ending_hook": "神秘男子递来一封信，信中内容让女主震惊"
    },
    {
      "episode": 2,
      "original_range": "第2章-第3章",
      "core_plot": "女主打开信发现生母留下的线索",
      "ending_hook": "信中提到的地点竟是一处废弃豪宅"
    }
  ]
}
```

### 2.3 竖屏短剧约束（写入 system_prompt）

```
## 竖屏短剧特征
- 竖屏观看、单集 1-3 分钟、节奏极快
- 保证每集时长差别不大，不要上一集 3 分钟、下一集只有 1 分钟
- 每集结尾必须有悬念钩子
- 剧情需要均匀分配到全部集数

## 剧情分配铁律
- 前 1/3 集：建立矛盾、积累情绪
- 中 1/3 集：反转升级、多线推进
- 后 1/3 集：高潮爆发、逐一清算
- 严禁在前 1/3 集数内写出结局、全剧终、最终对决
```

### 2.4 解析与验证

```python
@dataclass
class EpisodeOutline:
    episode: int
    original_range: str   # 原文范围描述（人类可读）
    core_plot: str
    ending_hook: str

@dataclass
class StageOneResult:
    total_episodes: int
    outlines: list[EpisodeOutline]  # 按集数升序排列
```

验证规则：
1. JSON 可解析（`json.loads` 不抛异常）
2. `total_episodes` 在 `[min_episodes, max_episodes]` 范围内
3. `len(outlines) == total_episodes`
4. 每集 `episode` 字段为 `1..N` 连续整数
5. 验证失败 → 重试一次（最多重试 1 次），仍失败 → 返回并打印失败原因

---

## 3. 阶段二：LLM Function Call 划分原文行号区间

### 3.1 方法可行性分析（Token 消耗效率）

用户提出的方法：LLM 调用 function call，每集提供 `[start_line]-[end_line]` 行号区间。

| 指标 | 分析 |
|---|---|
| **输入 token** | 阶段一的 JSON 大纲（~N × 100 字） + 带行号的小说全文（每行前缀 `L1: ` ~ O(novel_length)） |
| **输出 token** | N 集 × 每集 2 个行号（极少量） |
| **额外调用** | 1 次 function call LLM 请求 |
| **对比规则切分** | 规则切分 `_split_novel_by_chapters` 零 LLM 调用、零 token 消耗 |

**结论**：如果仅为了获取行号区间而调用 LLM，Token 性价比低。但阶段二真正的价值不是"获取行号"，而是**语义切分**——让 LLM 基于对剧情的理解，在情节自然断点处切分，而不是在章节标题的机械边界处切分。

### 3.2 优化方案：阶段一直接输出行号区间，阶段二仅做验证与 chunk 聚合

**核心思路**：将行号区间作为阶段一 JSON 的扩展字段，LLM 在生成大纲的同时标注每集对应的行号范围。阶段二不再调用 LLM，而是做确定性处理：验证行号连续性 + 按 batch_size + 冗余聚合成 chunk。

优化后的阶段一 JSON 输出：

```json
{
  "total_episodes": 80,
  "outlines": [
    {
      "episode": 1,
      "line_range": {"start": 1, "end": 45},
      "original_range": "第1章",
      "core_plot": "...",
      "ending_hook": "..."
    }
  ]
}
```

优化后的阶段二（无 LLM 调用）：

```
输入: StageOneResult (含 line_range) + novel_lines (已分行)
处理:
  1. 验证行号连续性：第 i 集的 start == 第 i-1 集的 end + 1
  2. 聚合为 chunk：
     chunk_1 = episode[1..10] + 冗余 episode[11..12]
     chunk_2 = episode[11..20] + 冗余 episode[9..10] + episode[21..22]
     ...
  3. 每 chunk 提取对应行号的原文文本
输出: list[BatchSegment]
```

```python
@dataclass
class BatchSegment:
    batch_start: int        # 本批生成的起始集
    batch_end: int          # 本批生成的结束集
    line_start: int         # 原文起始行号（含冗余前缀）
    line_end: int           # 原文结束行号（含冗余后缀）
    novel_excerpt: str      # 提取的原文片段
```

### 3.3 为什么不用 function call

| 方案 | LLM 调用次数 | Token 消耗 | 可维护性 |
|---|---|---|---|
| 阶段一含行号 + 阶段二纯规则 | 1 次 | 大纲 token + 行号 token（增量可忽略） | 高（行号解析是确定性逻辑） |
| 阶段一不含行号 + 阶段二 function call | 2 次 | 额外 O(novel_length) 输入 + function schema 开销 | 低（依赖 LLM function call 实现，需 OpenAI tool 支持） |

**决策**：采用方案一。行号标注在阶段一由 LLM 一次性完成，阶段二只做规则聚合，零 LLM 调用。

---

## 4. 阶段三：分批生成正文

### 4.1 批次划分规则

```python
BATCH_SIZE = 10
REDUNDANCY = 2  # 前后各冗余 2 集原文

# 批次定义
batch_1:  生成 1-10  集, 原文覆盖 1-12 集的行号范围
batch_2:  生成 11-20 集, 原文覆盖 9-22 集的行号范围
batch_3:  生成 21-30 集, 原文覆盖 19-32 集的行号范围
...
batch_n:  生成最后 N 集, 原文覆盖对应范围（边界截断处理）
```

冗余处理规则：
- 前冗余：`max(1, batch_start - REDUNDANCY)` 到 `batch_start - 1` 集的原文
- 后冗余：`batch_end + 1` 到 `min(batch_end + REDUNDANCY, total_episodes)` 集的原文
- 第一批无前冗余，最后一批无后冗余（自然截断）

### 4.2 提示词结构

**System Prompt**：
```
你是一位经验丰富的竖屏短剧剧本创作总监。

## 竖屏短剧核心特征
- 竖屏观看：画面聚焦人物面部和上半身
- 单集 1-3 分钟：每集约 200-500 字
- 节奏极快：每集只聚焦一个情绪爆点或情节转折，1-2 个场景
- 情绪浓烈：冲突直接、台词犀利
- 每集结尾必须有钩子：用【卡点】标记

## 剧情分配铁律
- 剧情必须均匀分配到全部 {total_episodes} 集
- 严禁在本批写出全剧结局（除非本批是最后 5 集）
- 严格按照本批大纲写作，不要跳过集数

## 剧本格式规范
{格式规则 + 模板}

## 本批逐集大纲（严格遵循）
{episode_11 大纲}
{episode_12 大纲}
...
{episode_20 大纲}

请直接输出剧本内容，不要有额外解释。
```

**User Prompt**：
```
请生成第 {batch_start} 集到第 {batch_end} 集（共 {total_episodes} 集）：

【本集参考原文】
{冗余前原文 - 仅供上下文参考，不要生成这些集的剧本}
{本批对应原文}
{冗余后原文 - 仅供上下文参考，不要生成这些集的剧本}

【要求】
1. 仅生成第 {batch_start} 集到第 {batch_end} 集的剧本正文
2. 每集 200-500 字，1-2 个场景
3. 每集结尾必须用【卡点】标记设置悬念
4. 严格遵循上方逐集大纲
5. 冗余原文仅供上下文参考，不要为冗余部分生成剧本

开始创作：
```

### 4.3 边界处理

| 场景 | 处理逻辑 |
|---|---|
| 第一批（batch_start=1） | 无前冗余，仅保留后冗余 2 集 |
| 最后一批 | 无后冗余，仅保留前冗余 2 集 |
| 总集数 < 10 | 单批生成全部，无冗余 |
| 总集数 = 10 | 单批生成全部，无冗余 |
| 总集数 = 11 | batch_1: 1-10 (后冗余 11)，batch_2: 11-11 (前冗余 9-10) |

---

## 5. 数据流图

```
novel_text
  │
  ├── 分行预处理 → novel_lines (list[str])
  │
  ▼
┌─────────────────────────────────────────┐
│ 阶段一：单次 LLM 调用                     │
│ 输入: novel_text + min/max_episodes      │
│ 输出: JSON { total_episodes, outlines[] } │
│   每集 outline 含:                       │
│     - episode (int)                      │
│     - line_range {start, end}            │
│     - original_range (str)               │
│     - core_plot (str)                    │
│     - ending_hook (str)                  │
└──────────────────┬──────────────────────┘
                   │ StageOneResult
                   ▼
┌─────────────────────────────────────────┐
│ 阶段二：规则处理（零 LLM 调用）            │
│ 1. 验证行号连续性                         │
│ 2. 按 batch_size=10, redundancy=2 聚合   │
│ 3. 从 novel_lines 提取原文               │
│ 输出: list[BatchSegment]                │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ 阶段三：循环分批 LLM 生成                 │
│ 每批:                                    │
│   - 取出 BatchSegment                   │
│   - 提取本批 outline                    │
│   - 构建 prompt → LLM → 剧本片段         │
│   - 追加写入输出文件                     │
│ 输出: 完整剧本文件                       │
└─────────────────────────────────────────┘
```

---

## 6. 接口变更

### 6.1 新增/修改的方法

| 方法 | 类型 | 说明 |
|---|---|---|
| `_build_combined_prompt()` | 新增 | 阶段一合并提示词（集数 + 大纲 + 行号） |
| `_parse_combined_response()` | 新增 | 解析阶段一 JSON 响应 → StageOneResult |
| `_validate_outlines()` | 新增 | 验证大纲完整性（集数连续性、行号连续性） |
| `_aggregate_batches()` | 新增 | 阶段二：按 batch_size + redundancy 聚合 chunk |
| `_extract_segment_text()` | 新增 | 根据行号区间从 novel_lines 提取原文 |
| `_build_batch_prompt_v2()` | 修改 | 阶段三提示词，使用 outline 对象而非纯文本 |
| `generate_script_auto_episodes()` | 修改 | 三阶段入口，替换旧流程 |

### 6.2 废弃的方法（保留用于降级回退）

| 方法 | 状态 |
|---|---|
| `_build_decide_episodes_prompt()` | 保留，降级回退使用 |
| `_build_outline_prompt()` | 保留，降级回退使用 |
| `_map_episodes_to_segments()` | 保留，降级回退使用 |

---

## 7. 测试策略

### 7.1 单元测试

| 测试用例 | 描述 |
|---|---|
| `test_parse_combined_response_valid_json` | 测试合法 JSON 解析 |
| `test_parse_combined_response_invalid_json` | 测试非法 JSON → 降级回退 |
| `test_parse_combined_response_missing_fields` | 测试缺失必填字段 → 降级回退 |
| `test_validate_outlines_episode_continuity` | 测试集数必须为 1..N 连续 |
| `test_validate_outlines_line_range_continuity` | 测试行号连续性校验 |
| `test_aggregate_batches_basic` | 测试 80 集 → 8 批的正常聚合 |
| `test_aggregate_batches_first_batch_no_pre_redundancy` | 测试第一批无前冗余 |
| `test_aggregate_batches_last_batch_no_post_redundancy` | 测试最后一批无后冗余 |
| `test_agate_episodes_less_than_batch` | 测试集数 < 10 的单批场景 |
| `test_extract_segment_text` | 测试行号区间原文提取 |
| `test_build_batch_prompt_v2_redundancy_labeling` | 测试提示词中标注冗余原文 |

### 7.2 降级路径测试

| 测试用例 | 描述 |
|---|---|
| `test_stage_one_json_parse_failure_fallback` | 阶段一 JSON 解析失败 → 调用旧 `_build_decide_episodes_prompt` + `_build_outline_prompt` |
| `test_stage_one_outline_count_mismatch_fallback` | outlines 数量与 total_episodes 不一致 → 降级 |
| `test_stage_one_line_range_validation_failure` | 行号验证失败 → 降级到规则映射 |

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 阶段一 JSON 输出格式不规范 | 解析失败，流程中断 | JSON 解析异常捕获 → 降级到 V1 流程 |
| LLM 行号标注不准确 | 阶段二提取原文错位 | 行号验证：start/end 必须在 `[1, len(novel_lines)]` 范围内，且相邻集行号连续 |
| 阶段一单次调用输出过长 | max_tokens 截断 | system_prompt 中约束每集大纲 ≤ 40 字；设置合理的 max_tokens（≥ 8000） |
| 批次冗余重叠导致剧情重复 | 相邻批次生成的内容有重复感 | prompt 中明确标注"冗余原文仅供参考，不要生成对应剧本" |
