# 当前实现进度

## 当前状态

- 当前仓库已进入最小代码实现阶段。
- 已完成核心需求文档整理，主文档为 [README.md](/Users/caojunze424/code/gdb_trace/README.md)。
- 已建立协作约束文档 [AGENTS.md](/Users/caojunze424/code/gdb_trace/AGENTS.md)。
- 已完成第一批代码：CLI 配置状态管理。
- 已完成第二批代码：生命周期命令。
- 已完成第三批代码：trace 日志生成器与最小事件模型。
- 已完成第四批代码：过滤参数生效逻辑。
- 已完成第五批代码：采集后端抽象。
- 已完成第六批代码：多架构日志测试覆盖。
- 已完成第七批代码：采集结果元数据完善。

## 已完成内容

- 明确了 `gdbtrace` 的目标场景：面向 `SkyEye` 远程调试。
- 明确了支持的指令集或执行态：`thumb`、`thumb2`、`arm32`、`aarch64`。
- 明确了输出模式：`inst`、`call`、`both`。
- 明确了日志输出格式：彩色 `.log` 文件，ANSI 颜色直接写入。
- 明确了 CLI 模型：预配置命令 + `start/pause/save/stop` 生命周期命令。
- 明确了目标地址配置模型：当前会话优先，回退到全局默认配置。
- 已建立 Python CLI 最小工程骨架。
- 已实现目标地址配置命令：`set-target`、`set-default-target`、`show-target`、`clear-target`、`clear-default-target`。
- 已实现会话级配置命令：`set-arch`、`set-elf`、`set-output`、`set-mode`、`show-config`、`clear-arch`、`clear-elf`、`clear-output`、`clear-mode`。
- 已实现生命周期命令：`start`、`pause`、`save`、`stop`。
- 已实现 `start` 的配置校验、缺失项聚合报错、暂停后恢复逻辑。
- 已实现最小运行时状态文件与最小 `.log` 落盘逻辑。
- 已实现最小 trace 事件模型，并为 `aarch64`、`arm32`、`thumb`、`thumb2` 提供样例事件。
- 已实现 `inst`、`call`、`both` 三种模式的日志格式化逻辑。
- 已将 `save` / `stop` 输出切换为基于事件模型的真实日志格式，而不是纯占位文本。
- 已实现 `--start`、`--stop`、`--filter-func`、`--filter-range` 对事件流的实际过滤。
- 已实现过滤后的深度重映射，保证 `call` / `both` 模式输出保持正确缩进层级。
- 已实现采集后端抽象，当前默认后端为 `static`。
- 已将 `start` 的事件来源改为通过后端接口采集，而不是直接在 CLI 中硬编码样例事件。
- 已为 `arm32`、`thumb`、`thumb2` 补充模式级日志测试覆盖。
- 已将后端名称和过滤后事件数量纳入运行时状态与日志头元数据。
- 已新增 `gdb-native` 真实采集后端，当前支持 `aarch64` 原生 GDB 单步采集。
- 已新增 `test_programs/aarch64_sample.c` 与 `test_programs/aarch64_complex.c` 两个真实测试程序源码，用于基础与复杂场景验证。

## 当前验证状态

- 已验证需求文档与协作文档在命名和接口约束上保持一致。
- 已验证输出格式示例已写入需求文档。
- 当前测试阶段暂不在 `SkyEye` 后端做集成验证。
- 已确认宿主机架构为 `Darwin arm64`。
- 已确认指定 Docker 容器 `ubuntu` 架构为 `Linux aarch64`。
- 已确认容器内现有工具包括：`gdb`、`qemu-arm`、`qemu-system-aarch64`、`aarch64-linux-gnu-gcc`。
- 已确认容器当前缺失：`gdb-multiarch`、ARM32 交叉编译工具链。
- 已在 Docker 容器 `ubuntu` 中通过 `python3 -m unittest discover -s tests -v` 完成配置管理相关自动化测试。
- 已在 Docker 容器 `ubuntu` 中完成配置命令的最小手工命令验证。
- 已在 Docker 容器 `ubuntu` 中通过 `python3 -m unittest discover -s tests -v` 完成生命周期命令相关自动化测试。
- 已在 Docker 容器 `ubuntu` 中完成 `start -> pause -> start -> save -> stop` 的最小手工命令验证。
- 已在 Docker 容器 `ubuntu` 中通过 `python3 -m unittest discover -s tests -v` 完成日志格式化相关自动化测试。
- 已在 Docker 容器 `ubuntu` 中完成 `inst` 和 `both` 模式的最小手工日志验证。
- 已在 Docker 容器 `ubuntu` 中通过 `python3 -m unittest discover -s tests -v` 完成过滤逻辑相关自动化测试。
- 已在 Docker 容器 `ubuntu` 中完成 `--filter-func` 的最小手工日志验证。
- 已在 Docker 容器 `ubuntu` 中通过 `python3 -m unittest discover -s tests -v` 完成采集后端相关自动化测试。
- 已在 Docker 容器 `ubuntu` 中完成默认后端写入运行时状态的手工验证。
- 已在 Docker 容器 `ubuntu` 中通过 `python3 -m unittest discover -s tests -v` 完成多架构样例日志测试。
- 已在 Docker 容器 `ubuntu` 中完成 `thumb2` `inst` 模式的最小手工日志验证。
- 已在 Docker 容器 `ubuntu` 中通过 `python3 -m unittest discover -s tests -v` 完成日志元数据相关自动化测试。
- 已在 Docker 容器 `ubuntu` 中完成日志头 `backend` / `events` 字段的手工验证。
- 已将测试计划扩展为“基础样例 + 复杂 ELF 样例”两层结构，要求后续补齐更长指令流和更复杂调用图的真实程序验证。
- 已在 Docker 容器 `ubuntu` 中于 2026-03-06 再次执行 `python3 -m unittest discover -s tests -v`，当前 19 项自动化测试全部通过。
- 已在 Docker 容器 `ubuntu` 中完成 `aarch64` 原生 GDB 真实场景自动化测试，覆盖基础样例、复杂样例、非 `aarch64` 拒绝路径。
- 已在 Docker 容器 `ubuntu` 中以手工 CLI 流程完成 `aarch64_complex` 的 `set-* -> start -> save -> stop` 验证，并确认产出带颜色的层级化 `.log`。
- 已在 Docker 容器 `ubuntu` 中于 2026-03-06 执行 `python3 -m unittest discover -s tests -v`，当前 22 项自动化测试全部通过。

## 下一步

1. 先不接 `SkyEye` 后端，优先规划并实现真实 GDB 调试链路测试。
2. 为仓库补齐 `arm32_sample.c`、`thumb_sample.c`、`thumb2_sample.c` 三类基础测试程序源码并在容器内编译生成 ELF。
3. 为仓库补齐 `arm32_complex.c`、`thumb_complex.c`、`thumb2_complex.c` 或等价复杂样例，用于覆盖更长指令流和更复杂调用图。
4. 复杂样例需要覆盖深层调用链、多分支、循环、递归、间接调用、正常路径与错误路径并存等场景。
5. `arm32`、`thumb`、`thumb2` 走 `qemu-arm` gdb stub + `gdb-multiarch` 调试测试。
6. 在执行 ARM32/Thumb 系列真实测试前，先补齐 `gdb-multiarch` 和 ARM32 交叉编译工具链。
7. 在 `aarch64` 已有真实后端基础上，继续扩展远程 GDB stub 采集能力，逐步替换静态样例后端在 ARM32/Thumb 系列中的占位作用。

## 已知阻塞或风险

- 当前尚无代码目录结构，后续实现时需要先确定最小工程骨架。
- 当前日志虽已按目标格式输出，但事件来源仍是静态样例数据，尚未接入真实指令流采集。
- ARM32 / Thumb / Thumb2 的真实 GDB 调试测试依赖容器内补装 `gdb-multiarch` 和 ARM32 交叉编译工具链。
- `aarch64` 真实 GDB 测试样例已落地，但 ARM32 / Thumb / Thumb2 的真实样例 ELF 仍未落地。
- `aarch64` 复杂 ELF 样例已落地，但 ARM32 / Thumb / Thumb2 的复杂样例仍需补齐，并补充对应的预期调用图对拍资料。
