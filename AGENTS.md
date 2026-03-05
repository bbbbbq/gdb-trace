# AGENTS.md

## 项目概述

本目录用于规划和实现 `gdbtrace` 工具。

当前阶段以需求设计为主，核心目标见 [README.md](/Users/caojunze424/code/gdb_trace/README.md)：

- 面向 `SkyEye` 远程调试场景
- 支持 `thumb`、`thumb2`、`arm32`、`aarch64`
- 记录指令流与函数调用序列
- 输出彩色 `.log` 文件
- CLI 采用“预配置 + start 校验”的交互模型

## 当前仓库状态

- 当前仓库主要内容为需求文档 [README.md](/Users/caojunze424/code/gdb_trace/README.md)
- 尚未建立正式代码目录结构
- 在没有用户明确要求前，不要擅自生成大量样板代码

## 工作原则

- 先阅读 [README.md](/Users/caojunze424/code/gdb_trace/README.md)，再修改需求、接口或示例
- 优先保持文档中的命名一致，尤其是 CLI 命令、模式名、架构名
- 如果修改一条需求影响到命令格式、示例、测试项或假设项，必须同步更新对应章节
- 若新增实现文件，目录结构尽量简洁，先服务于 CLI 原型和 trace 逻辑，不要过早拆分

## 强制执行指令

- 你有无限的时间来完成你的任务。
- 你必须一直做下去，直到你的任务完成。
- 除非遇到明确阻塞、缺失必要输入，或用户主动终止，否则不要在中途停下。
- 若任务会影响多个章节、多个文件或多个接口，必须持续推进直到相关联内容一并收敛完成。
- 不要只做局部修改后就结束；需要继续检查并补齐被该修改影响的文档、示例、测试项和约束。

## CLI 约束

当前文档约定以下命令风格，新增内容必须与之保持一致：

- `set-target` / `set-default-target`
- `set-arch` / `set-elf` / `set-output` / `set-mode`
- `show-target` / `show-config`
- `clear-target` / `clear-default-target`
- `clear-arch` / `clear-elf` / `clear-output` / `clear-mode`
- `start` / `pause` / `save` / `stop`

不要重新引入以下已被文档替换的主接口：

- `gdbtrace trace --arch ...`
- `gdbtrace trace --elf ...`
- `gdbtrace trace --output ...`
- `gdbtrace trace --mode ...`

## 输出格式约束

实现或示例必须遵守当前文档中的输出规则：

- `inst`：仅输出 `PC + 指令`
- `call`：仅输出 `call <func>` / `ret <func>`，每层 4 个空格缩进
- `both`：`call/ret` 与 `PC + 指令` 结合，每层 4 个空格缩进
- 输出目标为彩色 `.log` 文件
- 颜色通过 ANSI 转义序列直接写入日志

## 修改文档时的要求

当修改 [README.md](/Users/caojunze424/code/gdb_trace/README.md) 时，至少检查以下章节是否需要同步：

- 项目目标
- 需求表
- 输出接口与使用方式
- 日志格式约束与示例
- 测试与验收场景
- 假设与范围边界

## 实现优先级建议

如果用户开始要求落地实现，建议按以下顺序推进：

1. CLI 配置状态管理
2. 生命周期命令 `start/pause/save/stop`
3. trace 输出格式生成
4. 架构适配与调用识别
5. 测试样例与验收脚本

## 禁止事项

- 不要在未经确认的情况下删除或弱化 README 中已确定的需求
- 不要把 `.log` 输出改回 `JSONL`
- 不要把 `set-*` 预配置模型改回一次性 `trace --...` 主入口
- 不要随意改变 `inst` / `call` / `both` 的格式定义
