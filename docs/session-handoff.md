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
| 剧本生成 | `src/script_writer.py` | ✅ 通过（三阶段流程 + 精简参数 + 小说分段） |
| 格式校验 | `src/format_validator.py` | ✅ 通过 |
| 主入口 | `src/main.py` | ✅ 通过 |
| Web 前端 | `web/index.html` + `web/css/style.css` + `web/js/app.js` | ✅ 已创建（拖拽上传 + SSE 流式 + 编辑 + 导出） |
| Web 后端 | `web/server.py` | ✅ 已创建（Flask + SSE 流式输出） |

### 1.2 测试覆盖
- **测试数量**：42 个测试用例全部通过 ✅
- **测试文件**：`tests/test_config.py`、`tests/test_llm_client.py`、`tests/test_novel_reader.py`、`tests/test_script_writer.py`、`tests/test_format_validator.py`

### 1.3 配置验证
- API Key：系统环境变量已配置有效密钥 ✅
- Base URL：`https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` ✅
- 模型：`qwen3.6-plus` ✅

### 1.4 核心功能验证
- ✅ LLM 自主判断集数功能（60-100集）
- ✅ 三阶段生成机制：决定集数 → 生成逐集大纲 → 按大纲分批生成正文
- ✅ 竖屏短剧节奏约束写入提示词（单集1-3分钟、200-500字、每集必有【卡点】）
- ✅ 系统提示词打印功能（三个阶段均打印，统一辅助方法）
- ✅ 小说分段传递：阶段三每批仅传递对应章节片段，而非全文
- ✅ 逐批写入文件：避免内存中累积全部内容
- ✅ `_build_auto_prompt` 精简参数（8→4）+ 旧签名向后兼容
- ✅ Web 可视化改编 Agent：拖拽上传小说 → SSE 流式输出剧本 → 在线编辑 → 导出 txt

---

## 二、本轮改动

### 2.1 代码改动
| 文件 | 改动内容 |
|------|----------|
| `src/script_writer.py` | 新增 `BatchRange` / `AutoPromptContext` dataclass；新增 `_split_novel_by_chapters` / `_map_episodes_to_segments` / `_extract_novel_segment_range` 分段方法；新增 `_parse_outline` / `_get_outline_range` 大纲解析方法；`_build_auto_prompt` 重构为双签名（新签名 4 参数 + 旧签名兼容层）；`_build_outline_prompt` 新增"原文范围"标注要求；`_print_system_prompt` 统一辅助方法消除 4 处重复；`import re` 移至模块级；删除死代码默认值；阶段三使用片段替代全文传递；逐批追加写入文件 |
| `tests/test_script_writer.py` | 新增 13 个测试用例（dataclass、分段提取、新签名、集成测试）；42 个测试全部通过 |
| `.gitignore` | 添加 `.claude/` 忽略规则 |
| `web/index.html` | 新创建，前端主页面（方案 C 风格，拖拽上传 + 进度条 + 编辑器 + 导出） |
| `web/css/style.css` | 新创建，样式文件（CSS 变量驱动主题） |
| `web/js/app.js` | 新创建，前端交互逻辑（文件拖拽、SSE 流式接收、编辑器操作、导出） |
| `web/server.py` | 新创建，Flask 后端服务（文件上传、SSE 三阶段流式生成、停止接口） |
| `web/requirements.txt` | 新创建，Web 依赖（flask、openai、python-dotenv） |

### 2.2 文档更新
| 文件 | 新增/更新 |
|------|----------|
| `docs/ui-design-comparison.html` | 新创建，三套 UI 方案对比（极简工具风 / 专业工作台 / 现代卡片流） |
| `docs/ui-design-c-optimized.html` | 新创建，方案 C 可交互优化版（含 UI 设置面板 + 滑动控制 + 提示词复制） |
| `docs/refactor-auto-prompt-spec.md` | 新创建，重构 SPEC 文档（问题分析、解决方案、测试策略、5 步实施计划） |
| `docs/session-handoff.md` | 本交接文档更新 |
| `CLAUDE.md` | 项目主导航 |
| `docs/auto-episode-spec.md` | 自动集数三阶段流程设计 |

---

## 三、已知问题 ⚠️

### 3.1 LLM 早期结局问题
- **现象**：之前生成的剧本在第 10 集就出现 `（全剧终）`，后续集数重复断代
- **原因**：缺少大纲先行步骤，LLM 直接写正文时节奏失控，前紧后松
- **修复**：已引入三阶段流程（大纲先行 → 按大纲分批写正文），理论上可解决
- **待验证**：需实际运行一次 `--auto-episodes` 验证新流程输出质量

### 3.2 分段策略限制
- **现象**：当 `batch_size >= total_episodes` 时（单批生成完所有集），分段合并后仍接近全文
- **原因**：单批覆盖所有集数时，对应的片段自然覆盖所有章节
- **缓解**：实际使用中建议 `batch_size < total_episodes / 2`，分段效果更显著

### 3.3 Web 端待验证
- **现象**：Web 前端已创建，但尚未实际运行验证 SSE 流式连接和生成流程
- **待验证**：启动 Flask 服务后拖拽小说文件，确认三阶段流程正常执行、流式输出正确渲染

### 3.4 其他
- `.env` 文件中 `DASHSCOPE_API_KEY` 未配置（需用户手动设置）

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

# 自动集数模式（推荐，三阶段流程 + 分段传递）
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
# 所有测试
.venv\Scripts\python.exe -m pytest tests/ -v

# 特定模块测试
.venv\Scripts\python.exe -m pytest tests/test_script_writer.py -v
```

---

## 五、关键文档导航

| 文件 | 用途 |
|------|------|
| `CLAUDE.md` | 项目主导航（命令 + 架构 + 约束） |
| `docs/ip-short-drama-spec.md` | 项目总体规划与技术规格 |
| `docs/auto-episode-spec.md` | 自动集数三阶段流程设计 |
| `docs/refactor-auto-prompt-spec.md` | 参数精简与分段策略重构 SPEC |
| `docs/ui-design-comparison.html` | 三套 UI 方案对比 |
| `docs/ui-design-c-optimized.html` | 方案 C 可交互优化版（含 UI 设置面板） |
| `docs/session-handoff.md` | 本交接文档 |
| `data/短剧剧本写作格式模板.md` | 标准剧本格式模板 |
