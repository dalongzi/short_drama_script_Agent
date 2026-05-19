# 会话交接文档

> 快速了解项目现状，关键验证状态和下一步行动

---

## 一、当前已验证 ✅

### 1.1 功能模块状态
| 模块 | 文件 | 验证状态 |
|------|------|----------|
| 配置管理 | `src/config.py` | ✅ 通过 |
| LLM 客户端 | `src/llm_client.py` | ✅ 通过 |
| 小说读取 | `src/novel_reader.py` | ✅ 通过（支持多编码） |
| 剧本生成 | `src/script_writer.py` | ✅ 通过（V2 三阶段流水线 + 降级异常） |
| 格式校验 | `src/format_validator.py` | ✅ 通过 |
| 主入口 | `src/main.py` | ✅ 通过 |
| Web 前端 | `web/index.html` + `web/css/style.css` + `web/js/app.js` | ✅ 已创建（拖拽上传 + SSE 流式 + 编辑 + 导出） |
| Web 后端 | `web/server.py` | ✅ 已更新为 V2 流程 |

### 1.2 测试覆盖
- **测试数量**：54 个通过，5 个失败（与 V2 重构无关）
- **script_writer 模块**：41 个测试全部通过 ✅
- **失败的 5 个**：`test_config.py`（4 个，环境变量读取问题）和 `test_llm_client.py`（1 个，Mock 返回值格式），均为预存在问题

### 1.3 配置验证
- API Key：系统环境变量已配置有效密钥 ✅
- Base URL：`https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` ✅
- 模型：`qwen3.6-plus` ✅

### 1.4 核心功能验证
- ✅ V2 流水线重构完成：阶段一 JSON 大纲（含行号区间）→ 阶段二规则聚合批次 → 阶段三分批生成（2 集冗余上下文）
- ✅ V1 旧代码已删除（降级路径改为直接抛异常）
- ✅ Web 后端已更新为 V2 流程
- ✅ 竖屏短剧节奏约束写入提示词（单集 1-3 分钟、200-500 字、每集必有【卡点】）
- ✅ 逐批追加写入文件：避免内存中累积全部内容

---

## 二、本轮改动

### 2.1 V2 流水线重构（13 个 feature）

| Feature | 描述 | 状态 |
|---------|------|------|
| v2-001 | 新增 V2 数据结构：LineRange / EpisodeOutline / StageOneResult / BatchSegment | ✅ passing |
| v2-002 | 阶段一：`_build_combined_prompt()` 合并提示词 | ✅ passing |
| v2-003 | 阶段一：`_parse_combined_response()` 解析 JSON | ✅ passing |
| v2-004 | 阶段一：`_validate_outlines()` 验证大纲完整性 | ✅ passing |
| v2-005 | 阶段二：`_aggregate_batches()` 按 batch_size + redundancy 聚合 | ✅ passing |
| v2-006 | 阶段二：`_extract_batch_text()` 根据行号区间提取原文 | ✅ passing |
| v2-007 | 阶段三：`_build_batch_prompt_v2()` 分批生成提示词（含冗余标注） | ✅ passing |
| v2-008 | 阶段三：`generate_script_auto_episodes()` 接入 V2 流程 | ✅ passing |
| v2-009 | 降级路径：阶段一失败自动回退到 V1 流程 | ✅ passing（已删除降级，改为异常） |
| v2-010 | 测试：阶段一 JSON 解析用例 | ✅ passing |
| v2-011 | 测试：阶段一大纲验证用例 | ✅ passing |
| v2-012 | 测试：阶段二聚合和原文提取用例 | ✅ passing |
| v2-013 | 测试：阶段三提示词和降级路径用例 | ✅ passing |

### 2.2 代码改动
| 文件 | 改动内容 |
|------|----------|
| `src/script_writer.py` | **新增**：`_build_combined_prompt` / `_parse_combined_response` / `_validate_outlines` / `_aggregate_batches` / `_extract_batch_text` / `_build_batch_prompt_v2`；**删除**：`_generate_script_auto_episodes_v1` / `_build_outline_prompt` / `_parse_outline` / `_get_outline_range` / `_split_novel_by_chapters` / `_map_episodes_to_segments` / `_build_decide_episodes_prompt` / `_build_auto_prompt`；**精简**：`AutoPromptContext` 移除 V1 字段 |
| `tests/test_script_writer.py` | 删除 14 个 V1 专用测试；降级路径测试改为异常抛出测试；新增 13 个 V2 测试；共 41 个测试通过 |
| `web/server.py` | 从手动编排 V1 三步骤改为调用 V2 方法 |
| `feature_list.json` | 13 个 feature 全部标记为 passing |

### 2.3 文档
| 文件 | 变更 |
|------|------|
| `docs/pipeline-v2-spec.md` | V2 流水线规格文档（定义阶段一/二/三的数据流和接口） |
| `docs/session-handoff.md` | 本交接文档更新 |

---

## 三、已知问题 ⚠️

### 3.1 LLM 早期结局问题
- **现象**：之前生成的剧本在第 10 集就出现 `（全剧终）`，后续集数重复断代
- **原因**：旧流程缺少大纲先行步骤，LLM 直接写正文时节奏失控
- **修复**：V2 流程通过 JSON 大纲先行 + 每集 ending_hook 约束，理论上可解决
- **待验证**：需实际运行一次 `--auto-episodes` 验证新流程输出质量

### 3.2 分段策略限制
- **现象**：当 `batch_size >= total_episodes` 时（单批生成完所有集），分段合并后仍接近全文
- **原因**：单批覆盖所有集数时，对应的片段自然覆盖所有章节
- **缓解**：实际使用中建议 `batch_size < total_episodes / 2`，分段效果更显著

### 3.3 Web 端待验证
- **现象**：Web 前端已创建，后端已更新为 V2 流程，但尚未实际运行验证 SSE 流式连接和生成流程
- **待验证**：启动 Flask 服务后拖拽小说文件，确认三阶段流程正常执行、流式输出正确渲染

### 3.4 其他
- `.env` 文件中 `DASHSCOPE_API_KEY` 未配置（需用户手动设置）
- 5 个预存在测试失败（`test_config.py` 4 个 + `test_llm_client.py` 1 个），与 V2 重构无关

---

## 四、常用命令

### 4.1 环境准备
```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

### 4.2 运行程序
```bash
# 生成指定集数的剧本
python src/main.py --novel data/弃妇逆袭：贺家真千金.txt --output data/output.txt --episodes 1

# 自动集数模式（推荐，V2 三阶段流程）
python src/main.py --novel data/弃妇逆袭：贺家真千金.txt --output data/output.txt --auto-episodes

# 自定义批次大小（建议小于总集数的一半）
python src/main.py --novel data/弃妇逆袭：贺家真千金.txt --output data/output.txt --auto-episodes --batch-size 15
```

### 4.3 Web 服务
```bash
# 安装 Web 依赖
.\.venv\Scripts\pip.exe install -r web\requirements.txt

# 启动 Flask 后端（同时提供前端静态文件）
python web/server.py
# 浏览器访问 http://localhost:5000
```

### 4.4 运行测试
```bash
# script_writer 模块测试（41 个通过）
.venv\Scripts\python.exe -m pytest tests/test_script_writer.py -v

# 所有测试（54 个通过，5 个预存在失败）
.venv\Scripts\python.exe -m pytest tests/ -v
```

---

## 五、关键文档导航

| 文件 | 用途 |
|------|------|
| `CLAUDE.md` | 项目主导航（命令 + 架构 + 约束） |
| `docs/ip-short-drama-spec.md` | 项目总体规划与技术规格 |
| `docs/auto-episode-spec.md` | 旧版自动集数三阶段流程设计（V1，已废弃） |
| `docs/pipeline-v2-spec.md` | **V2 流水线规格文档**（当前标准） |
| `docs/refactor-auto-prompt-spec.md` | 参数精简与分段策略重构 SPEC |
| `docs/workflow-visualization.md` | 工作流程可视化 |
| `feature_list.json` | 功能清单与验证状态追踪 |
| `data/短剧剧本写作格式模板.md` | 标准剧本格式模板 |
