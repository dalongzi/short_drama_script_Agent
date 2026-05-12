# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

IP 改编短剧 Agent — 将小说文本自动改编为符合红果/番茄投稿标准的短剧剧本。通过 OpenAI SDK 兼容接口调用通义千问 qwen3.6-plus 模型进行 AI 改编。

## 常用命令

```bash
# 激活虚拟环境
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行全部测试
.venv\Scripts\python.exe -m pytest tests/ -v

# 运行单个测试文件
.venv\Scripts\python.exe -m pytest tests/test_script_writer.py -v

# 指定集数生成剧本
python src/main.py --novel data/弃妇逆袭：贺家真千金.txt --output data/output.txt --episodes 1

# 自动集数模式（LLM 分析小说决定集数，分批生成）
python src/main.py --novel data/弃妇逆袭：贺家真千金.txt --output data/output.txt --auto-episodes

# 自定义批次大小
python src/main.py --novel data/弃妇逆袭：贺家真千金.txt --output data/output.txt --auto-episodes --batch-size 15
```

## 架构结构

```
src/
├── config.py           # 配置管理（环境变量 + .env，支持 DASHSCOPE_API_KEY/OPENAI_API_KEY）
├── llm_client.py       # LLM 客户端封装（OpenAI SDK，支持多模型切换）
├── novel_reader.py     # 小说读取（支持 utf-8/gbk/gb2312/cp1252 多编码）
├── script_writer.py    # 剧本生成器（固定集数 + 自动集数两种模式，分批生成机制）
├── format_validator.py # 格式校验器（检查集数标题、场景编号、△标记等）
└── main.py             # 主入口（argparse 命令行）
```

### 核心工作流

1. `config.py` 加载 API 配置 → 2. `novel_reader.py` 读取小说 → 3. `llm_client.py` 初始化客户端 → 4. `script_writer.py` 生成剧本 → 5. `format_validator.py` 校验格式

### 两种生成模式

- **固定集数模式**：`generate_script()` — 直接指定集数，一次性生成
- **自动集数模式**：`generate_script_auto_episodes()` — 三阶段流程：先让 LLM 分析决定总集数 → 生成逐集大纲（每集剧情+钩子）→ 按大纲分批生成正文

## 关键约束

输出剧本必须严格遵循 `data/短剧剧本写作格式模板.md` 规范：

- 集数标题：`第X集` 或 `第一集`
- 场景格式：`1-1 日 内 地点`（编号-子编号 日/夜 内/外 地点）
- 动作描述：`△` 符号开头
- 语气神态：`()` 括号标注
- 内心独白：`VO` / `OS` 标记
- 回忆镜头：`【闪回】` / `【闪出】`
- **所有大模型调用必须通过 OpenAI SDK 统一接入，支持多模型切换**

## 开发约定

1. **TDD**：新功能先写失败测试，再写实现
2. **测试隔离**：禁止调用真实 API，使用 Mock
3. **结构对称**：`src/` 每个模块对应 `tests/test_` 同名文件
4. **虚拟环境**：所有开发在 `.venv` 中进行
5. **格式严格**：输出剧本必须 100% 符合 `data/短剧剧本写作格式模板.md` 规范

## 配置说明

通过 `.env` 文件或环境变量配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DASHSCOPE_API_KEY` / `OPENAI_API_KEY` | 无 | API 密钥 |
| `OPENAI_BASE_URL` | `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` | 代理地址 |
| `OPENAI_MODEL` | `qwen3.6-plus` | 模型名称 |

## 关键文档

- `docs/ip-short-drama-spec.md` — 项目总体规划与技术规格
- `docs/auto-episode-spec.md` — LLM 自主判断集数功能设计
- `docs/workflow-visualization.md` — 工作流程可视化（每个步骤的输入输出）
- `docs/session-handoff.md` — 会话交接文档（快速了解项目现状）
- `data/短剧剧本写作格式模板.md` — 标准剧本格式模板（开发必须遵循）
