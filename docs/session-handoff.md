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
| 剧本生成 | `src/script_writer.py` | ✅ 通过（三阶段流程） |
| 格式校验 | `src/format_validator.py` | ✅ 通过 |
| 主入口 | `src/main.py` | ✅ 通过 |

### 1.2 测试覆盖
- **测试数量**：29 个测试用例全部通过 ✅
- **测试文件**：`tests/test_config.py`、`tests/test_llm_client.py`、`tests/test_novel_reader.py`、`tests/test_script_writer.py`、`tests/test_format_validator.py`

### 1.3 配置验证
- API Key：系统环境变量已配置有效密钥 ✅
- Base URL：`https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` ✅
- 模型：`qwen3.6-plus` ✅

### 1.4 核心功能验证
- ✅ LLM 自主判断集数功能（60-100集）
- ✅ 三阶段生成机制：决定集数 → 生成逐集大纲 → 按大纲分批生成正文
- ✅ 竖屏短剧节奏约束写入提示词（单集1-3分钟、200-500字、每集必有【卡点】）
- ✅ 系统提示词打印功能（三个阶段均打印）
- ✅ 字数校验已取消

---

## 二、本轮改动

### 2.1 代码改动
| 文件 | 改动内容 |
|------|----------|
| `src/script_writer.py` | 自动集数模式升级为三阶段流程；新增 `_build_outline_prompt()` 和 `_extract_outline_section()` 方法；`_build_auto_prompt()` 新增 `outline_section` 参数；提示词加入竖屏短剧约束和严禁早期写结局铁律 |
| `tests/test_script_writer.py` | 新增 3 个测试用例（大纲提示词、带大纲的正文提示词、三阶段流程适配）；29 个测试全部通过 |

### 2.2 文档更新
| 文件 | 新增/更新 |
|------|----------|
| `CLAUDE.md` | 新创建，替代 AGENTS.md 作为项目主导航文档 |
| `docs/auto-episode-spec.md` | 同步三阶段流程和竖屏短剧约束 |
| `.gitignore` | 添加 `.claude/` 忽略规则 |
| `AGENTS.md` | 已合并到 CLAUDE.md，已删除 |

---

## 三、已知问题 ⚠️

### 3.1 LLM 早期结局问题
- **现象**：之前生成的剧本在第 10 集就出现 `（全剧终）`，后续集数重复断代
- **原因**：缺少大纲先行步骤，LLM 直接写正文时节奏失控，前紧后松
- **修复**：已引入三阶段流程（大纲先行 → 按大纲分批写正文），理论上可解决
- **待验证**：需实际运行一次 `--auto-episodes` 验证新流程输出质量

### 3.2 其他
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

# 自动集数模式（推荐，三阶段流程）
python src/main.py --novel data/弃妇逆袭：贺家真千金.txt --output data/output.txt --auto-episodes

# 自定义批次大小
python src/main.py --novel data/弃妇逆袭：贺家真千金.txt --output data/output.txt --auto-episodes --batch-size 15
```

### 4.3 运行测试
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
| `docs/session-handoff.md` | 本交接文档 |
| `data/短剧剧本写作格式模板.md` | 标准剧本格式模板 |
