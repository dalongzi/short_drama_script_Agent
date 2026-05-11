# IP 改编短剧 Agent - AGENTS.md

> 本文件是项目导航入口（给 AI Agent 和开发者看的目录页）。
> 遵循 Harness Engineering "地图而非手册" 原则：~50 行入口，指向更深层文档。

## 项目定位



## 关键文件导航

| 文件 | 用途 |
|------|------|
| `docs/ip-short-drama-spec.md` | 项目总体规划文档（必读） |
| `docs/auto-episode-spec.md` | LLM自主判断集数功能设计文档 |
| `docs/session-handoff.md` | 会话交接文档（快速了解项目现状） |
| `docs/workflow-visualization.md` | 工作流程可视化（每个步骤的输入输出） |
| `data/短剧剧本写作格式模板.md` | 标准剧本格式模板（开发必须遵循） |

## 开发约定

1. **TDD 强制**：所有新功能必须先写失败的测试，再写实现
2. **Spec 同步**：修改报告结构时必须同步更新 `docs/**.md`
3. **测试隔离**：单元测试禁止调用真实 API，使用 Mock
4. **结构对称**：`src/` 下每个模块对应 `tests/` 下的 `test_` 同名文件
5. **格式严格**：输出剧本必须 100% 符合 `data/短剧剧本写作格式模板.md` 规范
6. **虚拟环境**：所有开发必须在虚拟环境中进行，避免依赖冲突 如：`./.venv/Scripts/python main.py`、`./.venv/Scripts/pip install -r requirements.txt`


## 架构约束

- 输出格式严格遵循红果/番茄投稿标准（参考《短剧剧本写作格式模板.md》
- 所有非对话内容必须用 △ 标注
- 场景格式必须为：`集数-场景号  日/夜  内/外  地点
- 角色语气神态必须用 `()` 标注
- 内心独白使用 VO/OS 标记，回忆使用【闪回】/【闪出】标记
- **所有大模型调用必须通过 OpenAI SDK 统一接入，支持多模型切换**
