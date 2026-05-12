# 重构 _build_auto_prompt 参数与小说分段策略 — SPEC 文档

## 1. 问题描述

### 1.1 参数膨胀

`_build_auto_prompt()` 当前接收 8 个参数：

```python
def _build_auto_prompt(self, novel_text, template_content,
                       min_episodes, max_episodes,
                       start_episode, end_episode, total_episodes,
                       outline_section)
```

其中 `min_episodes` 和 `max_episodes` 仅用于阶段一决策提示词的范围引导，在阶段三正文生成中完全不使用；`template_content` 是整个生命周期不变的常量。参数多且职责混杂，调用链传递成本高。

### 1.2 小说全文每批重复传递

当前阶段三的每一批 LLM 调用中，`novel_text`（完整小说）都原样嵌入 `user_prompt`。以 22KB 的小说为例，60-100 集分 6-10 批生成，同一份 22KB 文本被重复传输 6-10 次：

- **Token 浪费**：每批额外消耗约 10K+ tokens 传输无关章节
- **注意力稀释**：LLM 需要从全文中自行定位当前批次对应的段落
- **成本累加**：多轮调用的 token 消耗显著增加

---

## 2. 解决方案概述

### 2.1 参数收敛：引入配置对象

将 `_build_auto_prompt` 的参数收敛为两个：

```python
@dataclass(frozen=True)
class AutoPromptContext:
    """自动集数提示词构建的上下文配置"""
    template_content: str          # 模板内容（不变）
    total_episodes: int            # 总集数（阶段一决定后不变）

def _build_auto_prompt(self, batch: 'BatchRange', outline_section: str, ctx: AutoPromptContext) -> tuple[str, str]:
```

`BatchRange` 封装批次相关的集数范围信息：

```python
@dataclass(frozen=True)
class BatchRange:
    """单批生成的集数范围"""
    start: int
    end: int
```

**收敛前后对比：**

| 维度 | 收敛前 | 收敛后 |
|------|--------|--------|
| 参数数量 | 8 个 | 3 个 |
| 可变参数 | start_episode, end_episode, outline_section | batch, outline_section |
| 不变参数 | novel_text, template_content, min/max_episodes, total_episodes | ctx（2 个字段） |

### 2.2 小说分段：基于大纲对齐的章节切片

核心思路：**不再传递全文，而是传递与当前批次大纲对应的小说片段。**

#### 方案设计

1. **阶段一（集数决策）和阶段二（大纲生成）**：仍然传递完整小说，因为需要全局视野
2. **阶段三（正文生成）**：只传递当前批次对应的小说段落

具体实现步骤：

**步骤 1：在阶段二大纲生成时，让 LLM 同时输出每集对应的小说章节范围**

修改 `_build_outline_prompt` 的输出格式，要求 LLM 为每集标注来源章节/段落：

```
第X集：
  原文范围：第N章 ~ 第M章（或"开头~第N段"等段落描述）
  核心剧情：...
  结尾钩子：...
```

**步骤 2：解析大纲时提取原文范围映射**

`_parse_outline` 同时构建 `{集数: 原文范围描述}` 映射。

**步骤 3：根据原文范围从小说中提取对应段落**

新增 `_extract_novel_segment(novel_text, range_description)` 方法：
- 如果小说有明确章节标题（如 `第X章`），按章节分割后截取对应范围
- 如果无章节结构，按段落位置或字符偏移截取
- 返回截取后的小说片段（而非全文）

**步骤 4：在 `_build_auto_prompt` 中使用片段替代全文**

`user_prompt` 中只嵌入当前批次对应的小说段落。

---

## 3. 详细设计

### 3.1 数据结构

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class BatchRange:
    start: int   # 起始集数
    end: int     # 结束集数

@dataclass(frozen=True)
class NovelSegment:
    text: str            # 截取后的小说文本
    source_desc: str     # 来源描述，如"第1章-第3章"

@dataclass(frozen=True)
class AutoPromptContext:
    template_content: str
    total_episodes: int
    outline_response: str           # 完整大纲（仅用于调试/打印）
    outline_dict: dict[int, str]    # {集数: 该集大纲} 预解析结果
    novel_segments: dict[int, str]  # {集数: 该集对应小说片段}
```

### 3.2 新增方法

#### `_split_novel_by_chapters(novel_text: str) -> list[tuple[str, str]]`

将小说按章节标题分割为 `(章节标题, 章节内容)` 列表。

- 支持 `第X章`、`Chapter X`、`### 标题` 等常见格式
- 返回空列表表示无法识别章节结构
- 无章节时回退为按段落（空行）分割

#### `_map_episodes_to_segments(outline_dict, chapters) -> dict[int, str]`

根据大纲中的原文范围描述，将每集映射到对应的小说片段。

- 如果大纲中每集标注了 `原文范围：第N章~第M章`，精确截取
- 如果无标注，按集数比例均匀分配到章节：`episode / total_episodes * total_chapters`
- 相邻批次允许少量重叠，保证情节连续性

#### `_build_auto_prompt(batch, outline_section, novel_segment, ctx)`

修改后的签名，只接收当前批次需要的数据。

### 3.3 方法签名变更

| 方法 | 变更前 | 变更后 |
|------|--------|--------|
| `_build_auto_prompt` | 8 参数 | 4 参数（batch, outline_section, novel_segment, ctx） |
| `generate_script_auto_episodes` | 无变化 | 内部增加 `_split_novel_by_chapters` 和 `_map_episodes_to_segments` 调用 |
| `_parse_outline` | 返回 `{集数: 大纲文本}` | 增加返回 `{集数: 原文范围描述}` |

### 3.4 调用流程变更

```
阶段一：决定集数（不变，传全文）
  ↓
阶段二：生成大纲（不变，传全文）
  ↓
  新增：_split_novel_by_chapters(novel_text)
  新增：_map_episodes_to_segments(outline_dict, chapters)
  ↓
阶段三：分批生成正文
  for each batch:
    batch_outline = _get_outline_range(outline_dict, batch)
    batch_segment = _get_segment_range(novel_segments, batch)  ← 只传片段
    _build_auto_prompt(batch, batch_outline, batch_segment, ctx)  ← 精简参数
```

---

## 4. 提示词变更

### 4.1 阶段二大纲提示词新增要求

在现有 `_build_outline_prompt` 的 system prompt 中增加一行：

```
3. 原文范围（标注本集对应的小说章节/段落范围，如"第1章-第3章"）
```

输出格式变为：

```
第X集：
  原文范围：第N章 ~ 第M章
  核心剧情：...
  结尾钩子：...
```

### 4.2 阶段三正文提示词调整

`user_prompt` 中的 `【小说内容】` 从全文改为片段：

```diff
-【小说内容】
-{novel_text}
+【本集参考原文】
+{novel_segment}
```

---

## 5. 边界情况处理

| 场景 | 处理方式 |
|------|----------|
| 小说无章节结构 | 回退为按段落分割，按集数比例均匀分配 |
| LLM 未标注原文范围 | 按集数比例自动分配章节范围 |
| 章节数 < 总集数 | 一章对应多集，相邻批次共享重叠段落 |
| 章节数 > 总集数 | 多章合并为一集，优先保持情节完整性 |
| 截取片段过短 | 向前后各扩展 1-2 章，确保上下文充足 |
| 最后几集 | 片段包含剩余全部内容，保证结局完整性 |

---

## 6. 测试策略

### 6.1 单元测试

| 测试用例 | 描述 |
|----------|------|
| `test_split_novel_by_chapters` | 测试带章节小说的分割 |
| `test_split_novel_no_chapters` | 测试无章节小说的段落分割 |
| `test_map_episodes_to_segments` | 测试集数到章节范围的映射 |
| `test_extract_novel_segment_range` | 测试指定章节范围的提取 |
| `test_build_auto_prompt_with_segment` | 测试使用片段而非全文的提示词构建 |
| `test_batch_range_dataclass` | 测试 BatchRange 不可变特性 |
| `test_auto_prompt_context_dataclass` | 测试 AutoPromptContext 不可变特性 |

### 6.2 集成测试

| 测试用例 | 描述 |
|----------|------|
| `test_auto_episodes_with_novel_segments` | 完整的三阶段流程，验证片段传递正确性 |
| `test_segment_overlap_continuity` | 验证相邻批次间的片段重叠保证剧情连贯 |

### 6.3 回归测试

| 测试用例 | 描述 |
|----------|------|
| 现有 29 个测试 | 确保重构不破坏现有功能 |

---

## 7. 实施步骤

### Step 1：引入数据结构（无行为变更）

- 新增 `BatchRange` 和 `AutoPromptContext` dataclass
- `_build_auto_prompt` 保持旧签名兼容
- 新增测试

### Step 2：小说分段提取

- 实现 `_split_novel_by_chapters`
- 实现 `_map_episodes_to_segments`
- 新增 `_extract_novel_segment`
- 测试分段逻辑

### Step 3：大纲提示词更新

- 修改 `_build_outline_prompt` 要求标注原文范围
- 更新 `_parse_outline` 解析原文范围

### Step 4：调用链重构

- `generate_script_auto_episodes` 中集成分段逻辑
- 修改 `_build_auto_prompt` 签名为精简版
- 更新所有调用方

### Step 5：验证

- 运行全部 29 个现有测试
- 运行新增测试
- 实际运行一次 `--auto-episodes` 验证输出质量

---

## 8. 预期效果

| 指标 | 当前 | 优化后 |
|------|------|--------|
| `_build_auto_prompt` 参数 | 8 个 | 4 个 |
| 每批传递的小说文本 | 全文 ~22KB | 对应片段 ~2-5KB |
| 60集总 token 消耗 | ~1.3M tokens | ~0.4M tokens（估算） |
| 代码可读性 | 参数传递链长 | 结构化上下文，意图清晰 |
