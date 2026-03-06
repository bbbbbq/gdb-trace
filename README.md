# gdbtrace 需求表

## 项目目标

`gdbtrace` 是一个面向 `SkyEye` 远程调试场景的命令行追踪工具。首版目标是在 `thumb`、`thumb2`、`arm32`、`aarch64`、`riscv32`、`riscv64` 六类指令集或执行态下，稳定记录指令流与函数调用序列，便于问题复现、执行路径分析和调用链定位。首版范围按“两者同优先”定义：指令级追踪与函数级追踪均为核心能力，不做二选一裁剪。

## 需求表

| ID | 类别 | 需求项 | 优先级 | 验收标准 |
|---|---|---|---|---|
| R1 | 产品目标 | 支持当前会话目标地址配置、全局默认目标地址配置，以及按优先级自动解析远程连接地址 | Must | 当前会话已设置时优先使用当前会话地址；未设置时回退到全局默认地址；两者都未设置时输出明确错误提示 |
| R2 | 产品目标 | 支持 `thumb`、`thumb2`、`arm32`、`aarch64`、`riscv32`、`riscv64` 六类指令集或执行态的追踪 | Must | 可在这六类目标程序或执行态下正确启动追踪并输出结果 |
| R3 | 核心功能 | 支持记录逐条指令流，并在开启函数调用序列时按函数调用层级组织指令输出 | Must | 未开启函数调用序列时，仅输出按执行顺序排列的指令流；开启后，输出中包含 `call <func>`、缩进后的函数内指令、`ret <func>`，且支持多层嵌套调用 |
| R4 | 核心功能 | 支持记录函数调用序列 | Must | 能输出函数进入、返回、调用深度、调用关系 |
| R5 | 核心功能 | 支持追踪开始、暂停、停止、保存 | Must | CLI 通过 `start`、`pause`、`save`、`stop` 显式控制追踪生命周期；`start` 启动前会校验必需配置；`stop` 后产出完整结果文件 |
| R6 | 核心功能 | 支持按执行区间追踪 | Must | 可指定从某地址或符号开始，到某地址或符号或条件结束 |
| R7 | 核心功能 | 支持符号解析 | Must | 给定 ELF 或符号文件后，调用序列优先显示函数名；真实 backend 在无 `main` 符号时退化为地址级指令流，不输出函数调用序列 |
| R8 | 核心功能 | 支持指令流与调用序列关联 | Must | 开启函数调用序列时，指令必须归属到所属函数层级，可据此还原嵌套调用树 |
| R9 | 架构适配 | AArch64 下识别 `BL`、`BLR`、`RET` 等调用返回行为 | Must | 调用链与真实执行路径一致，不出现系统性漏记或错记 |
| R10 | 架构适配 | ARM32 下识别 `BL`、`BLX`、`BX`、返回到 `LR/PC` 等行为 | Must | ARM/Thumb 场景下调用序列可用，模式切换不会导致大面积错乱 |
| R11 | 架构适配 | 正确处理 ARM/Thumb 状态切换 | Must | 输出中能保持正确 PC、反汇编及函数边界判断 |
| R12 | 过滤能力 | 支持按地址范围、函数名、模块过滤追踪内容 | Should | 用户可只记录目标模块或函数，减少输出噪声 |
| R13 | 过滤能力 | 支持仅记录调用序列、仅记录指令流或两者同时记录 | Must | CLI 中可配置三种模式，输出符合所选模式 |
| R14 | 输出能力 | 支持输出人类可读的彩色 log 文件 | Must | 生成 `.log` 文件，文件内容可直接用于问题排查，且关键事件带颜色区分 |
| R15 | 输出能力 | 支持彩色日志输出格式约定 | Must | 日志中包含 ANSI 颜色编码和统一的日志行格式，便于查看调用边界与指令内容 |
| R16 | 输出能力 | 输出中包含会话元数据 | Must | 结果文件包含架构、目标地址、时间、加载符号文件、追踪参数 |
| R17 | 可用性 | CLI 方式启动，参数清晰 | Must | 至少支持：目标地址、架构、符号文件、输出路径、追踪模式 |
| R18 | 可用性 | 异常场景可诊断 | Must | 连接失败、符号缺失、反汇编失败、目标停止异常均有明确日志 |
| R19 | 性能 | 长时间追踪时不应无限制占用内存 | Must | 支持流式写盘或分段落盘，避免 trace 全驻内存 |
| R20 | 性能 | 在可接受开销下运行 | Should | 对目标执行影响可控，首版以“调试可用”为准，不追求极限低开销 |
| R21 | 可靠性 | 目标中断、断连、异常退出时能安全收尾 | Must | 已采集数据不丢失，输出文件可正常关闭并标记异常结束 |
| R22 | 兼容性 | 与 SkyEye 远程调试流程兼容，不要求修改 SkyEye | Must | 通过标准远程调试接入即可工作，不依赖侵入式补丁 |
| R23 | 兼容性 | 无符号文件时仍可工作 | Must | 至少输出地址级指令流；真实 backend 在无 `main` 符号时仅支持 `inst` 模式 |
| R24 | 可扩展性 | 架构相关逻辑与通用追踪逻辑分层 | Should | 后续扩展到 `RISC-V` 或 `x86` 时无需重写主流程 |
| R25 | 可测试性 | 具备可复现实验用例 | Must | 对 `thumb`、`thumb2`、`arm32`、`aarch64`、`riscv32`、`riscv64` 各至少有一套可验证 trace 正确性的样例程序 |

## 输出接口与使用方式

首版建议以 GDB 内命令作为真实 trace 的主入口；CLI 保留配置命令与静态样例能力，不要求稳定的库接口。

建议 CLI 能力：

- `gdbtrace set-arch <thumb|thumb2|arm32|aarch64|riscv32|riscv64>`
- `gdbtrace set-elf <file>`
- `gdbtrace set-output <path.log>`
- `gdbtrace set-mode <inst|call|both>`
- `gdbtrace set-registers <on|off>`
- `gdbtrace show-config`
- `gdbtrace clear-arch`
- `gdbtrace clear-elf`
- `gdbtrace clear-output`
- `gdbtrace clear-mode`
- `gdbtrace clear-registers`
- `gdbtrace start [--start <addr|symbol>] [--stop <addr|symbol>] [--filter-func <pattern>] [--filter-range <start:end>]`
- `gdbtrace pause`
- `gdbtrace save`
- `gdbtrace stop`

配置命令语义：

- `set-arch`：设置当前会话追踪架构，仅对当前 `gdbtrace` 会话生效。
- `set-elf`：设置当前会话使用的 ELF 或符号文件路径，仅对当前会话生效。
- `set-output`：设置当前会话的日志输出路径，输出文件约定为 `.log`。
- `set-mode`：设置当前会话的追踪模式，取值为 `inst`、`call`、`both`。
- `set-registers`：设置是否在指令行后追加通用寄存器输出，取值为 `on` 或 `off`，默认视为 `off`。
- `show-config`：显示当前会话内 `arch`、`elf`、`output`、`mode`、`registers` 的当前值。
- `clear-arch`、`clear-elf`、`clear-output`、`clear-mode`、`clear-registers`：清除当前会话中的对应配置项。

生命周期命令语义：

- `start`：当没有活动 trace 时，校验当前会话配置并启动新 trace；当存在已暂停的 trace 时，恢复该 trace。
- `pause`：暂停当前运行中的 trace。
- `save`：将当前 trace 的快照写回 `set-output` 设置的原始路径，不结束 trace。
- `stop`：停止当前 trace，并将最终完整结果写回 `set-output` 设置的原始路径。
- 在 GDB 当前会话采集路径中，若 `gdbtrace start` 执行中被 `Ctrl+C` 中断，已采集事件会被自动收敛为 `paused` trace，并立即写回一次 snapshot；随后仍可继续执行 `save` 或 `stop`。

`set-output` 语义：

- 输出路径约定为 `.log` 文件。
- 日志文件内容为人类可读文本，不再要求 `JSONL` 结构化输出。
- ANSI 颜色码直接写入 log 文件，用于区分 `call`、`ret` 和普通指令行。
- 当 `set-mode both` 时，`set-output` 指定的路径保存 `both` 主日志，并额外生成一份同目录的 `call` 日志，命名为 `<原文件名 stem>.call.log`。

`set-mode` 语义：

- `inst`：仅输出纯指令流，不带任何函数调用附加信息；单行格式固定为 `PC + 空格 + 指令`。
- `inst`：若 `set-registers on`，则每条指令后追加一行 `regs:`，输出当前架构的通用寄存器值。
- `call`：仅输出函数调用序列，使用 4 个空格缩进表示嵌套；单行格式固定为 `call <func>` 或 `ret <func>`。
- `both`：输出带函数层级的指令流，格式为 `call/ret + PC + 指令`，统一按每层 4 个空格缩进。
- `both`：除主 `both` 日志外，还会额外生成一份 `call` 日志，便于单独查看函数调用序列。
- `both`：若 `set-registers on`，则函数体内每条指令后追加一行 `regs:`，缩进层级比所属指令再深 4 个空格。

GDB 上下文语义：

- 远程连接、`target remote`、`file`、`run`、`continue` 等动作由 GDB 原生命令负责。
- `gdbtrace` 不管理远程目标地址，也不代替 GDB 建连。
- `gdbtrace start` 表示“开始追踪当前 GDB inferior”，而不是“去连接某个目标地址”。

`start` 校验规则：

- `start` 不接受 `--arch`、`--elf`、`--output`、`--mode`。
- `start` 执行前必须检查当前会话是否已配置 `output`、`mode`。
- `start` 执行前必须能够确定 `arch`、`elf`：优先使用 `set-arch` / `set-elf`，否则尝试从当前 GDB 会话自动继承。
- 当启用真实 GDB 会话采集时，`start` 还必须确认当前 inferior 已停在可读取指令的位置。
- 若存在缺失项，`start` 直接失败，并一次性列出全部缺失项。
- 当 `start` 已经进入真实 GDB 单步采集后，`Ctrl+C` 不再丢弃已采集事件，而是将当前 trace 自动执行一次 `pause + save` 语义收敛，再保留给后续 `save` / `stop`。
- `pause`、`save`、`stop` 不接受新的 trace 配置参数。
- `save` 不接受新的输出路径，始终写回 `set-output` 设置的原始路径。
- `set-mode both` 时，`save` / `stop` 会同时写回主 `both` 日志和派生的 `call` 日志。

错误示例：

```text
error: missing required trace config: arch, elf, output, mode
```

日志格式约束：

- `inst` 模式仅保留 `PC + 指令`，不包含序号字段、`opcode=...`、`disasm=`、`arch_mode`、`symbol`。
- `set-registers off` 时，不输出任何寄存器行；`set-registers on` 时，在每条指令行后追加一行 `regs: <reg>=<value> ...`。
- `call` 模式仅保留 `call <func>` 和 `ret <func>`，通过每层 4 个空格表示函数嵌套。
- `both` 模式为两者结合：`call/ret` 行沿用 `call` 模式，指令行沿用 `inst` 模式，并显示在所属函数层级下。
- `both` 模式落盘为两份 `.log` 文件：原始 `set-output` 路径保存 `both` 内容，派生的 `<stem>.call.log` 保存 `call` 内容。
- 动态库调用在可识别场景下优先显示真实函数名，不将 `foo@plt` 单独作为调用边界；若缺少稳定符号名，则允许退化为地址型函数名，如 `sub_<addr>`。
- ANSI 颜色码直接写入日志文件，用于区分 `call`、`ret` 和普通指令行。
- 日志头保留 `target`、`arch`、`elf`、`start_time`、`trace_mode` 等会话元数据。

`inst` 示例：

```log
0x400580 stp x29, x30, [sp, #-16]!
0x400584 mov x29, sp
0x400588 bl func_a
```

`inst + registers` 示例：

```log
0x400724 push {r11, lr}
    regs: r0=0x00000005 r1=0x00000007 r11=0x7fffffe0 lr=0x00010490 sp=0x7fffffd0
0x400728 add r11, sp, #0
    regs: r0=0x00000005 r1=0x00000007 r11=0x7fffffd0 lr=0x00010490 sp=0x7fffffd0
```

`call` 示例：

```log
call main
    call func_a
        call func_b
        ret func_b
    ret func_a
ret main
```

`both` 示例：

```log
call main
    0x400580 stp x29, x30, [sp, #-16]!
    0x400584 mov x29, sp
    0x400588 bl func_a
    call func_a
        0x4005a8 sub sp, sp, #0x10
        0x4005ac bl func_b
        call func_b
            0x4005bc mov x1, x0
            0x4005c0 ret
        ret func_b
        0x4005b4 ret
    ret func_a
ret main
```

`both + registers` 示例：

```log
call main
    0x400724 push {r11, lr}
        regs: r0=0x00000005 r1=0x00000007 r11=0x7fffffe0 lr=0x00010490 sp=0x7fffffd0
    0x400728 add r11, sp, #0
        regs: r0=0x00000005 r1=0x00000007 r11=0x7fffffd0 lr=0x00010490 sp=0x7fffffd0
    call func_a
        0x400740 bl func_b
            regs: r0=0x00000005 r1=0x00000007 r11=0x7fffffd0 lr=0x00010490 sp=0x7fffffd0
    ret func_a
ret main
```

## 测试与验收场景

- 当前测试阶段：暂不在 `SkyEye` 后端做集成验证，优先验证真实 GDB 调试链路。
- 当前环境判断：优先在原生 Ubuntu 或指定 Docker 容器 `ubuntu` 中执行真实测试，当前真实后端测试统一走 QEMU gdb stub。
- `aarch64` 测试策略：使用 `qemu-aarch64` 提供 gdb stub，再由 `gdb-multiarch` 连接执行真实 GDB 调试验证。
- `arm32` / `thumb` / `thumb2` 测试策略：使用 `qemu-arm` 提供 gdb stub，再由 `gdb-multiarch` 连接执行真实 GDB 调试验证。
- `riscv32` / `riscv64` 测试策略：使用 `qemu-riscv32` / `qemu-riscv64` 提供 gdb stub，再由 `gdb-multiarch` 连接执行真实 GDB 调试验证。
- 测试资产来源：所有测试 ELF 均由仓库内自写源码编译生成，不依赖外部未知二进制。
- 测试源码目录：在后续实现中新增 `test_programs/` 或等价目录，至少包含 `aarch64_sample.c`、`arm32_sample.c`、`thumb_sample.c`、`thumb2_sample.c`、`riscv32_sample.c`、`riscv64_sample.c`。
- 基础样例结构：统一包含 `main -> func_a -> func_b`，至少覆盖一个返回路径、一个嵌套调用、以及一个递归或间接调用场景。
- 复杂 ELF 样例要求：除基础样例外，必须新增更大、更复杂的测试程序，使单次运行包含更多指令数量和更复杂的函数调用图。
- 复杂样例文件规划：在基础样例之外，至少新增 `aarch64_complex.c`、`arm32_complex.c`、`thumb_complex.c`、`thumb2_complex.c`、`riscv32_complex.c`、`riscv64_complex.c` 或等价文件。
- 复杂 ELF 场景至少包括：
  - 更深的调用链，例如 `main -> parse -> dispatch -> worker -> helper`
  - 多分支路径与条件跳转
  - 循环与多次重复调用，形成更长的指令流
  - 递归调用
  - 函数指针或间接调用
  - 叶子函数与非叶子函数混合
  - 错误路径与正常路径并存
- 复杂样例规模要求：单个复杂 ELF 应至少包含多个互相调用的业务函数、多个基本块以及明显长于基础样例的指令流，用于检验长 trace 的稳定性。
- 复杂样例输出验证：复杂 ELF 不只验证调用边界，还要对关键路径上的代表性指令段做抽样核对，确认 `inst` 与 `both` 模式下指令顺序一致。
- 复杂 ELF 验证重点：不仅验证“能采到 trace”，还要验证在更长指令流和更复杂调用关系下，`inst`、`call`、`both` 三种模式仍然输出正确。
- 用户态程序验证：除基础样例和复杂样例外，还应加入更贴近真实场景的 `qemu-user` 用户态程序，覆盖动态链接、`libc` 调用、字符串处理、格式化、分支和循环。
- `printf` 用户态程序验证：应加入显式调用 `printf` / `snprintf` 的用户态 ELF，验证格式化输出路径和 `plt` 调用边界在真实调试链路下可被采集。
- 动态库调用验证：应确认 trace 不把 `printf@plt`、`snprintf@plt` 之类的 PLT 跳板单独视为最终调用边界，而是尽量继续展开真实函数或地址级子调用。
- 环境准备：当前开发环境应具备 `gdb-multiarch`、`qemu-aarch64`、`qemu-arm`、`qemu-riscv32`、`qemu-riscv64`、`aarch64-linux-gnu-gcc`、`arm-linux-gnueabihf-gcc`、`riscv64-linux-gnu-gcc`。
- 环境准备：在新的测试环境中，若缺失 `gdb-multiarch`、ARM32 交叉编译工具链或 RISC-V 交叉编译工具链，测试计划必须包含安装步骤。
- `aarch64` 编译策略：使用容器内现有 `aarch64-linux-gnu-gcc` 编译测试 ELF。
- `arm32` 编译策略：使用 ARM32 交叉编译器并指定 `-marm`。
- `thumb` 编译策略：使用 ARM32 交叉编译器并指定 `-mthumb`。
- `thumb2` 编译策略：使用 ARM32 交叉编译器并指定 `-mthumb -march=armv7-a` 或等价支持 Thumb-2 的目标参数。
- `riscv32` 编译策略：使用 `riscv64-linux-gnu-gcc` 并指定 `-march=rv32imac -mabi=ilp32`，必要时配合自定义启动汇编和静态链接。
- `riscv64` 编译策略：使用 `riscv64-linux-gnu-gcc` 并指定 `-march=rv64gc -mabi=lp64d`，必要时配合自定义启动汇编和静态链接。
- `aarch64` QEMU stub 测试：使用 `qemu-aarch64 -g <port> ./prog` 启动目标，再由 `gdb-multiarch` 连接，验证指令流、调用序列和缩进层级。
- `arm32` / `thumb` / `thumb2` QEMU stub 测试：使用 `qemu-arm -g <port> ./prog` 启动目标，再由 `gdb-multiarch` 连接，验证三类模式的指令流、调用序列和缩进层级。
- `riscv32` / `riscv64` QEMU stub 测试：使用 `qemu-riscv32 -g <port> ./prog` 或 `qemu-riscv64 -g <port> ./prog` 启动目标，再由 `gdb-multiarch` 连接，验证两类模式的指令流、调用序列和缩进层级。
- `qemu-user` 用户态测试：使用交叉编译器构建真实用户态 ELF，并通过 `qemu-arm`、`qemu-riscv64` 等用户态模拟器执行，验证 trace 在动态链接和常见 `libc` 调用场景下仍可用。
- `aarch64` 样例程序：普通函数调用、间接调用、递归调用、正常返回。
- `arm32` 样例程序：ARM 模式下直接调用、返回到 `LR/PC`。
- `thumb` 样例程序：Thumb 模式调用、返回、状态正确识别。
- `thumb2` 样例程序：Thumb-2 指令流记录、调用返回识别、与普通 Thumb 区分正确。
- `riscv32` 样例程序：RV32 指令流记录、函数调用与返回识别、静态链接 ELF 正常执行。
- `riscv64` 样例程序：RV64 指令流记录、函数调用与返回识别、静态链接 ELF 正常执行。
- 混合场景：`arm32` 与 `thumb/thumb2` 切换，确认模式切换后 PC、反汇编、函数边界判断正确。
- 输出文件场景：确认追踪结果生成为 `.log` 文件，而不是 `.jsonl`。
- 彩色输出场景：确认 log 文件中包含 ANSI 颜色码，且 `call`、`ret`、指令行可区分。
- `inst` 模式：确认每行只包含 `PC + 指令`，不包含序号、`opcode`、`disasm=`、`arch_mode`、`symbol`。
- 寄存器可选输出场景：`set-registers off` 时确认日志不包含 `regs:` 行；`set-registers on` 时确认每条指令后追加通用寄存器行。
- 无 `main` 符号 ELF 场景：确认真实 backend 在 `inst` 模式下仍可输出地址级指令流。
- 无 `main` 符号 ELF 场景：确认真实 backend 在 `call` / `both` 模式下明确报错，而不是伪造函数调用层级。
- `call` 模式：确认仅输出 `call/ret` 行，且每层嵌套固定缩进 4 个空格。
- `both` 模式：确认 `call/ret` 与指令行组合输出，且两者都遵循统一的 4 个空格层级缩进。
- `both` 模式：确认会生成两份 `.log` 文件，其中主日志包含 `call/ret + 指令`，派生 `call` 日志仅包含函数调用序列。
- `set-arch`、`set-elf`、`set-output`、`set-mode` 后：`show-config` 能正确显示当前值。
- 执行 `clear-arch`、`clear-elf`、`clear-output`、`clear-mode` 后：`show-config` 不再显示对应值。
- 未配置任何项时执行 `start`：一次性报出缺失的 `arch`、`elf`、`output`、`mode`。
- 仅配置部分项时执行 `start`：只报出剩余缺失项。
- 全部配置完成后执行 `start`：可正常启动 trace。
- `pause` 后再次执行 `start`：恢复原 trace，而不是新建 trace。
- `save` 在运行中与暂停态：均能写回 `set-output` 指定路径。
- `stop` 在运行中与暂停态：均能写回最终完整结果。
- `start` 若传入被移除的 `--arch`、`--elf`、`--output`、`--mode`：返回明确错误提示。
- 嵌套调用场景：函数 A 调用 B，B 调用 C，确认文本缩进和 `ret` 配对正确。
- 递归调用场景：同名函数多层进入和返回，确认深度与配对关系正确。
- 长指令流场景：使用包含循环、多分支和重复调用的复杂 ELF，确认长序列输出不乱序、不丢行。
- 复杂调用图场景：使用包含递归、间接调用、深层嵌套的复杂 ELF，确认调用树、缩进层级与返回配对正确。
- 多路径场景：同一 ELF 中覆盖正常路径、错误路径和早返回路径，确认 trace 能真实反映执行分支。
- 大样例回归场景：对基础样例和复杂样例分别执行 `inst`、`call`、`both` 三种模式，确认模式切换不会在复杂程序上产生格式回退或层级错乱。
- 场景对拍要求：复杂样例需记录预期调用图和关键路径，trace 输出必须与样例源码中的预期执行关系一致。
- 用户态程序场景：对带 `libc` 调用的用户态程序执行真实 `qemu-user` 调试，确认 trace 至少能稳定覆盖业务函数与关键 `libc` 调用边界。
- 查看一致性场景：需求文档中的格式示例与模式说明、测试项一致，不残留旧字段写法。
- 查看兼容性场景：确认在支持 ANSI 的查看方式下颜色可见，在不支持 ANSI 的环境中至少不影响文本内容可读性。
- `aarch64` 验收标准：通过 `qemu-aarch64` stub + `gdb-multiarch` 完成真实 GDB 调试采集。
- `arm32` / `thumb` / `thumb2` 验收标准：通过 QEMU stub + `gdb-multiarch` 完成真实 GDB 调试采集。
- `riscv32` / `riscv64` 验收标准：通过 QEMU stub + `gdb-multiarch` 完成真实 GDB 调试采集。
- 测试资产验收标准：所有测试 ELF 都来自仓库内源码编译。
- 输出验收标准：生成的 trace 与需求文档定义的 `inst` / `call` / `both` 格式一致。
- 在 GDB 中先完成 `file` / `target remote` / 停住 inferior，再执行 `gdbtrace start`：确认可正常启动 trace。
- 未建立有效 GDB 调试上下文时执行 `gdbtrace start`：确认返回“当前 inferior 不可追踪”的明确错误。
- 无 `main` 符号文件场景：验证地址级 `inst` trace 可用，且 `call` / `both` 会被拒绝。
- 大量指令场景：验证流式输出、文件完整性、内存不失控。
- 断连或异常停止场景：验证 trace 文件可收尾且有错误标记。
- 过滤场景：仅函数级、仅指令级、地址范围过滤、函数名过滤结果正确。
- 对拍场景：trace 中的调用关系与样例程序预期调用图一致。

## 假设与范围边界

- 默认 `gdbtrace` 通过标准远程调试方式接入 `SkyEye`，不直接修改模拟器内部实现。
- 当前阶段默认不接 `SkyEye` 后端做测试，只验证真实 GDB 调试链路。
- 当前阶段默认 `aarch64`、`arm32`、`thumb`、`thumb2`、`riscv32`、`riscv64` 的真实测试统一采用 QEMU gdb stub + `gdb-multiarch`。
- 当前阶段默认 `arm32`、`thumb`、`thumb2` 采用 QEMU gdb stub + `gdb-multiarch`。
- 当前阶段默认 `riscv32`、`riscv64` 采用 QEMU gdb stub + `gdb-multiarch`。
- 当前阶段默认测试用 ELF 由仓库内自写源码编译生成。
- 当前阶段默认需要在容器内补装 `gdb-multiarch`、ARM32 交叉编译工具链和 RISC-V 交叉编译工具链后，再执行对应真实调试测试。
- 默认“当前会话”指当前交互式 `gdbtrace` 会话上下文，不等同于整个操作系统 shell 生命周期。
- 默认符号解析来源为用户提供的 ELF 或符号文件；真实 backend 在缺失 `main` 符号时降级为地址级 `inst` 输出，不生成函数调用序列。
- 默认文本输出关键词固定使用 `call` 和 `ret`，不采用其他同义词。
- 默认“开启函数调用序列”对应 `set-mode both` 或等价开启调用序列的模式。
- 默认 `inst` 模式保留 `PC`，但不保留 `pc=` 标签，直接使用 `地址 + 空格 + 指令`。
- 默认 `call` 与 `both` 的缩进规则统一固定为每层 4 个空格。
- 默认 `both` 中函数体内的指令行相对所属 `call <func>` 行下沉一层显示。
- 默认 `set-arch`、`set-elf`、`set-output`、`set-mode` 均仅对当前 `gdbtrace` 会话生效，不做全局持久化。
- 默认远程连接完全由 GDB 原生命令管理，`gdbtrace` 不再维护目标地址配置。
- 默认不新增 `resume`，恢复语义并入 `start`。
- 默认同一时刻只允许一个活动 trace，因此不引入 `trace-id`。
- 默认首版完全删除 `JSONL` 输出要求，仅保留彩色 `.log` 文件输出。
- 默认颜色采用 ANSI 转义序列直接写入 log 文件，而不是额外的颜色标签字段。
- 首版以离线分析为主，优先产出 trace 文件，不要求实时 UI 展示。
- 首版不包含 GUI、多核并发追踪、变量级追踪。
- 首版允许为保证正确性牺牲部分性能，但不能牺牲 trace 完整性与可诊断性。
