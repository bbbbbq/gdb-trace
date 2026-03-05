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
- 已完成第八批代码：`arm32` / `thumb` / `thumb2` 的真实 QEMU gdb stub 调试链路。
- 已完成第九批代码：`riscv32` / `riscv64` 的真实 QEMU gdb stub 调试链路。
- 已完成第十批代码：更贴近真实场景的 qemu-user 用户态程序与调试测试。
- 已完成第十一批代码：无符号 ELF 的地址级指令流采集支持。
- 已完成第十二批代码：`both` 模式双日志输出。

## 已完成内容

- 明确了 `gdbtrace` 的目标场景：面向 `SkyEye` 远程调试。
- 明确了支持的指令集或执行态：`thumb`、`thumb2`、`arm32`、`aarch64`、`riscv32`、`riscv64`。
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
- 已实现最小 trace 事件模型，并为 `aarch64`、`arm32`、`thumb`、`thumb2`、`riscv32`、`riscv64` 提供样例事件。
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
- 已新增 `gdb-qemu-arm` 真实采集后端，当前支持 `arm32`、`thumb`、`thumb2` 通过 `qemu-arm` gdb stub + `gdb-multiarch` 采集。
- 已新增 `test_programs/arm32_sample.c`、`thumb_sample.c`、`thumb2_sample.c` 三个 ARM32 系基础样例源码。
- 已新增 `test_programs/arm32_complex.c`、`thumb_complex.c`、`thumb2_complex.c` 三个 ARM32 系复杂样例源码。
- 已新增 `gdb-qemu-riscv` 真实采集后端，当前支持 `riscv32`、`riscv64` 通过 `qemu-riscv32` / `qemu-riscv64` gdb stub + `gdb-multiarch` 采集。
- 已新增 `test_programs/riscv_start.S` 共享启动汇编，用于构建可调试的静态 `riscv32` / `riscv64` ELF。
- 已新增 `test_programs/riscv32_sample.c`、`riscv64_sample.c` 两个 RISC-V 基础样例源码。
- 已新增 `test_programs/riscv32_complex.c`、`riscv64_complex.c` 两个 RISC-V 复杂样例源码。
- 已新增 `test_programs/userspace_qemu_app.c`，作为更贴近真实场景的用户态程序样例，覆盖动态链接、`libc` 调用、字符串处理和格式化。
- 已新增 `tests/test_qemu_user_userspace_apps.py`，用于验证 ARM 与 `riscv64` 在 `qemu-user` 用户态程序场景下的真实 trace 行为。
- 已新增 `test_programs/aarch64_start.S` 与 `test_programs/arm32_start.S`，用于构建无 `main` 符号的最小入口 ELF，验证 stripped ELF 场景。
- 已实现真实 backend 的无 `main` 符号退化逻辑：允许 `inst` 模式做地址级指令流采集，拒绝 `call` / `both` 模式。
- 已新增 stripped ELF 真实场景自动化测试，覆盖 `gdb-native` `aarch64` 与 `gdb-qemu-arm` `arm32` 两条链路。
- 已实现 `both` 模式双日志输出：原 `set-output` 路径保存层级化 `both` 日志，并派生 `<stem>.call.log` 保存纯函数调用序列日志。
- 已新增 `test_programs/userspace_printf_app.c`，作为显式调用 `printf` / `snprintf` 的用户态程序样例。
- 已新增 `tests/test_qemu_user_userspace_apps.py` 中的 `printf` 用户态真实测试，覆盖 `arm32` 与 `riscv64` 的 `qemu-user` 调试链路。

## 当前验证状态

- 已验证需求文档与协作文档在命名和接口约束上保持一致。
- 已验证输出格式示例已写入需求文档。
- 当前测试阶段暂不在 `SkyEye` 后端做集成验证。
- 已确认宿主机架构为 `Darwin arm64`。
- 已确认指定 Docker 容器 `ubuntu` 架构为 `Linux aarch64`。
- 已确认容器内现有工具包括：`gdb`、`qemu-arm`、`qemu-riscv32`、`qemu-riscv64`、`qemu-system-aarch64`、`aarch64-linux-gnu-gcc`。
- 已在 Docker 容器 `ubuntu` 内补齐 `gdb-multiarch`、`arm-linux-gnueabihf-gcc` 与 `libc6-dev-armhf-cross`。
- 已在 Docker 容器 `ubuntu` 内补齐 `riscv64-linux-gnu-gcc`、`binutils-riscv64-linux-gnu` 与 `libc6-dev-riscv64-cross`。
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
- 已在 Docker 容器 `ubuntu` 中完成 `arm32`、`thumb`、`thumb2` 的 `qemu-arm` gdb stub 真实场景自动化测试，覆盖基础样例、复杂样例、非 ARM32 系拒绝路径。
- 已在 Docker 容器 `ubuntu` 中以手工 CLI 流程完成 `thumb2_complex` 的 `set-* -> start -> save -> stop` 验证，并确认产出带颜色的层级化 `.log`。
- 已在 Docker 容器 `ubuntu` 中于 2026-03-06 执行 `python3 -m unittest discover -s tests -v`，当前 25 项自动化测试全部通过。
- 已在 Docker 容器 `ubuntu` 中完成 `riscv32`、`riscv64` 的 `qemu-riscv32` / `qemu-riscv64` gdb stub 真实场景自动化测试，覆盖基础样例、复杂样例、非 RISC-V 拒绝路径。
- 已在 Docker 容器 `ubuntu` 中以手工 CLI 流程完成 `riscv64_complex` 的 `set-* -> start -> save -> stop` 验证，并确认产出带颜色的层级化 `.log`。
- 已在 Docker 容器 `ubuntu` 中于 2026-03-06 执行 `python3 -m unittest discover -s tests -v`，当前 28 项自动化测试全部通过。
- 已在 Docker 容器 `ubuntu` 中完成带 `libc` 调用的 ARM 与 `riscv64` 用户态程序 `qemu-user` 自动化测试。
- 已在 Docker 容器 `ubuntu` 中以手工 CLI 流程完成动态链接 `arm32` 用户态程序的 `set-* -> start -> save -> stop` 验证，并确认 trace 中出现业务函数与 `strlen@plt` 等用户态调用边界。
- 已在 Docker 容器 `ubuntu` 中于 2026-03-06 执行 `python3 -m unittest discover -s tests -v`，当前 30 项自动化测试全部通过。
- 已在 Docker 容器 `ubuntu` 中完成 stripped ELF 自动化测试，确认 `gdb-native` `aarch64` 与 `gdb-qemu-arm` `arm32` 在无 `main` 符号时可输出地址级 `inst` trace，并在 `call` / `both` 模式下明确报错。
- 已在 Docker 容器 `ubuntu` 中于 2026-03-06 执行 `python3 -m unittest discover -s tests -v`，当前 34 项自动化测试全部通过。
- 已在 Docker 容器 `ubuntu` 中完成 `both` 双日志输出验证，确认主日志保留层级化 `both` 内容，派生 `<stem>.call.log` 仅保留调用序列。
- 已在 Docker 容器 `ubuntu` 中于 2026-03-06 再次执行 `python3 -m unittest discover -s tests -v`，当前 34 项自动化测试全部通过。
- 已在 Docker 容器 `ubuntu` 中完成 `printf` 用户态程序真实测试，确认 `arm32` 与 `riscv64` 可采集到 `emit_summary -> printf@plt` 路径。
- 已在 Docker 容器 `ubuntu` 中于 2026-03-06 再次执行 `python3 -m unittest discover -s tests -v`，当前 36 项自动化测试全部通过。
- 已在 Docker 容器 `ubuntu` 中完成 `both` 双日志输出自动化测试，覆盖生命周期、格式和元数据。

## 下一步

1. 继续收敛真实 GDB 采集链路中的通用部分，减少 `gdb-native`、`gdb-qemu-arm`、`gdb-qemu-riscv` 的重复实现。
2. 为 `riscv32` / `riscv64` 补齐无 `main` 符号 ELF 的真实自动化测试，统一各架构退化行为。
3. 继续扩展更大规模的用户态和复杂 ELF 样例，补强长指令流与复杂调用图回归。
4. 开始规划 `SkyEye` 远程目标适配所需的连接、停止条件和断连恢复处理。

## 已知阻塞或风险

- 当前日志已支持真实 `aarch64`、ARM32 系与 RISC-V 系采集，但默认后端仍是静态样例，尚未切换为面向真实目标的统一默认行为。
- `SkyEye` 远程目标尚未接入，当前真实场景仅覆盖容器内原生 `gdb`、`qemu-arm` gdb stub 与 `qemu-riscv` gdb stub。
- 基础样例和复杂样例已经落地，但更大规模的对拍样例和预期调用图资料仍需继续补充。
- 动态链接用户态程序在部分架构上会较早进入 PLT/动态装载相关路径，当前 trace 能稳定覆盖关键业务函数和部分 `libc` 调用边界，但对更深层库内部执行流的还原仍有限。
