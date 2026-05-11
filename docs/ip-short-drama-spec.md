# IP 改编短剧剧本 Agent - 技术规格说明书 (SPEC)

## 1. 项目概述

本项目旨在开发一个 AI 工具，能够将小说文本自动改编为符合特定格式的短剧剧本。

### 1.1 核心目标
- 输入：小说文本文件（.txt）
- 输出：符合 `data/短剧剧本写作格式模板.md` 规范的短剧剧本文件（.txt）
- 模型：使用 qwen3.6-plus 大语言模型

### 1.2 技术栈
- 编程语言：Python 3.x
- LLM SDK：OpenAI SDK（兼容通义千问接口）
- 项目结构：src/（主代码）、tests/（测试代码）、data/（输入输出数据）

---

## 2. 功能需求

### 2.1 核心功能
1. **小说读取**：读取输入的小说文本文件
2. **AI 改编**：调用 qwen3.6-plus 模型将小说改编为短剧剧本
3. **格式校验**：确保输出剧本 100% 符合指定格式模板
4. **文件输出**：将改编后的剧本保存为 txt 文件

### 2.2 格式要求（严格遵循）
输出剧本必须严格符合以下格式规范：

#### 2.2.1 集数与场景格式
```
第x集：集数标注
夜/日：晚上/白天
外/内：室外/室内
地点：广场/车站/酒店等
场1-1：第一场第一个场景剧情
场1-2：第一场第二个场景剧情
```

#### 2.2.2 标记规范
- **动作描述**：使用 △ 符号开头，标注除对话外的其他内容
- **语气神态**：使用 () 括号，描写人物说话时的语气、神态、动作等
- **内心独白**：使用 VO 或 OS 标记
- **回忆镜头**：开始用【闪回】，结束用【闪出】

#### 2.2.3 示例格式
```
第一集

【女主林雨欣：九天玄女因为话痨被罚下诛仙台，魂穿林府真千金身上】
【转折：九天玄女要代替林府千金扭转上一世悲剧，才能重返天庭】
【卡点：女主哥哥发现自己能听到女主心声，得知养妹想要全家人的命】

1-1   日  内  九重天
人物：女主林雨欣  天将X2
△（字幕：九重天，诛仙台）
△诛仙台上，仙气缭绕，两个天将架着林雨欣走到诛仙台上。
林雨欣惊恐的往后挣扎：两位大哥，从这跳下去会死仙女的！
```

---

## 3. 架构设计

### 3.1 目录结构
```
CASE-short_drama_script4/
├── data/                          # 数据目录
│   ├── 短剧剧本写作格式模板.md  # 剧本格式模板
│   └── *.txt                      # 输入小说文件 / 输出剧本文件
├── docs/                          # 文档目录
│   └── ip-short-drama-spec.md     # 本文档
├── src/                           # 源代码目录
│   ├── __init__.py
│   ├── config.py                  # 配置管理
│   ├── llm_client.py              # LLM 客户端封装
│   ├── novel_reader.py            # 小说文件读取
│   ├── script_writer.py           # 剧本生成与写入
│   ├── format_validator.py        # 格式校验器
│   └── main.py                    # 主入口
├── tests/                         # 测试目录
│   ├── __init__.py
│   ├── test_llm_client.py
│   ├── test_novel_reader.py
│   ├── test_script_writer.py
│   └── test_format_validator.py
├── requirements.txt               # Python 依赖
└── AGENTS.md                      # 项目导航
```

### 3.2 模块职责

#### 3.2.1 config.py
- 管理项目配置（API Key、模型名称、文件路径等）
- 从环境变量或配置文件加载配置

#### 3.2.2 llm_client.py
- 封装 OpenAI SDK 调用
- 支持模型切换（qwen3.6-plus 等）
- 提供统一的调用接口
- 处理 API 请求与响应

#### 3.2.3 novel_reader.py
- 读取小说文本文件
- 支持大文件分块处理
- 提取小说基本信息（标题、主角等）

#### 3.2.4 script_writer.py
- 构建 LLM 提示词（Prompt）
- 调用 LLM 生成剧本
- 保存剧本到文件

#### 3.2.5 format_validator.py
- 校验生成的剧本格式
- 检查必要标记是否正确使用
- 报告格式问题（可选自动修复）

#### 3.2.6 main.py
- 程序主入口
- 协调各模块工作流程
- 处理命令行参数

---

## 4. 接口设计

### 4.1 llm_client.py - LLM 客户端

#### 4.1.1 类：LLMClient

```python
class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str = "qwen3.6-plus"):
        """
        初始化 LLM 客户端
        
        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称，默认为 qwen3.6-plus
        """
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        调用 LLM 生成文本
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            
        Returns:
            生成的文本内容
            
        Raises:
            LLMCallError: LLM 调用失败时抛出
        """
```

### 4.2 novel_reader.py - 小说阅读器

#### 4.2.1 函数：read_novel

```python
def read_novel(file_path: str) -> str:
    """
    读取小说文件
    
    Args:
        file_path: 小说文件路径
        
    Returns:
        小说文本内容
        
    Raises:
        FileNotFoundError: 文件不存在时抛出
        IOError: 文件读取失败时抛出
    """
```

### 4.3 script_writer.py - 剧本生成器

#### 4.3.1 类：ScriptWriter

```python
class ScriptWriter:
    def __init__(self, llm_client: LLMClient, template_path: str):
        """
        初始化剧本生成器
        
        Args:
            llm_client: LLM 客户端实例
            template_path: 剧本格式模板文件路径
        """
    
    def generate_script(self, novel_text: str, output_path: str, num_episodes: int = 1) -> str:
        """
        从小说生成短剧剧本
        
        Args:
            novel_text: 小说文本内容
            output_path: 输出剧本文件路径
            num_episodes: 生成的集数，默认为 1
            
        Returns:
            生成的剧本内容
            
        Raises:
            ScriptGenerationError: 剧本生成失败时抛出
        """
    
    def _build_prompt(self, novel_text: str, template_content: str) -> tuple[str, str]:
        """
        构建 LLM 提示词
        
        Args:
            novel_text: 小说文本
            template_content: 模板内容
            
        Returns:
            (system_prompt, user_prompt) 元组
        """
    
    def save_script(self, script_content: str, output_path: str) -> None:
        """
        保存剧本到文件
        
        Args:
            script_content: 剧本内容
            output_path: 输出文件路径
        """
```

### 4.4 format_validator.py - 格式校验器

#### 4.4.1 函数：validate_script_format

```python
def validate_script_format(script_content: str, template_path: str) -> tuple[bool, list[str]]:
    """
    校验剧本格式是否符合规范
    
    Args:
        script_content: 剧本内容
        template_path: 模板文件路径
        
    Returns:
        (is_valid, issues) 元组，is_valid 表示是否有效，issues 是问题列表
    """
```

### 4.5 main.py - 主入口

#### 4.5.1 主函数

```python
def main(novel_path: str, output_path: str, num_episodes: int = 1):
    """
    主函数
    
    Args:
        novel_path: 输入小说文件路径
        output_path: 输出剧本文件路径
        num_episodes: 生成的集数
    """
```

---

## 5. 使用流程

### 5.1 命令行使用
```bash
# 激活虚拟环境
.venv\Scripts\activate

# 运行程序
python src/main.py --novel data/弃妇逆袭：贺家真千金.txt --output data/弃妇逆袭：贺家真千金_剧本.txt --episodes 1
```

### 5.2 程序化使用
```python
from src.config import Config
from src.llm_client import LLMClient
from src.novel_reader import read_novel
from src.script_writer import ScriptWriter

# 加载配置
config = Config()

# 初始化组件
llm_client = LLMClient(
    api_key=config.api_key,
    base_url=config.base_url,
    model=config.model
)
script_writer = ScriptWriter(llm_client, template_path="data/短剧剧本写作格式模板.md")

# 读取小说
novel_text = read_novel("data/弃妇逆袭：贺家真千金.txt")

# 生成剧本
script_content = script_writer.generate_script(
    novel_text=novel_text,
    output_path="data/弃妇逆袭：贺家真千金_剧本.txt",
    num_episodes=1
)
```

---

## 6. 配置管理

### 6.1 配置项
- `API_KEY`: 通义千问 API 密钥
- `BASE_URL`: API 基础 URL（如 https://dashscope.aliyuncs.com/compatible-mode/v1）
- `MODEL`: 模型名称（默认为 qwen3.6-plus）
- `TEMPLATE_PATH`: 剧本格式模板路径

### 6.2 配置方式
1. 环境变量
2. `.env` 文件
3. 命令行参数（优先级最高）

---

## 7. 依赖项

```txt
openai>=1.0.0
python-dotenv>=1.0.0
pytest>=7.0.0
```

---

## 8. 测试策略

### 8.1 单元测试
- 测试各模块独立功能
- 使用 Mock 避免真实 API 调用
- 覆盖正常流程与异常情况

### 8.2 集成测试
- 测试完整流程（读取小说 → 生成剧本 → 保存文件）
- 验证输出格式正确性

---

## 9. 错误处理

| 错误类型 | 描述 | 处理方式 |
|---------|------|---------|
| FileNotFoundError | 输入文件不存在 | 提示用户检查路径 |
| IOError | 文件读写失败 | 记录日志并终止 |
| LLMCallError | API 调用失败 | 重试（最多 3 次）或终止 |
| ScriptGenerationError | 剧本生成失败 | 提示用户并记录详情 |
| FormatValidationError | 格式校验失败 | 报告问题列表（不强制终止） |

---

## 10. 后续优化方向

1. 支持多种小说格式（.epub, .pdf 等）
2. 支持自定义剧本风格与长度
3. 添加剧本预览功能
4. 支持批量处理多本小说
5. 集成更多 LLM 模型选项
6. 添加剧本编辑与微调功能
