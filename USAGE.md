# gdbtrace 使用指南

## 目标

本文档说明如何在当前仓库中实际使用 `gdbtrace`，包括：

- 如何配置追踪会话
- 如何启动、暂停、保存、停止 trace
- 如何查看 `inst`、`call`、`both` 三种输出
- 如何在 Docker 容器 `ubuntu` 中跑真实 `aarch64`、`arm32`、`thumb`、`thumb2`、`riscv32`、`riscv64` 场景

## 运行环境

当前仓库约定在 Docker 容器 `ubuntu` 中运行和测试 `gdbtrace`。

进入容器后，仓库路径为：

```bash
cd /code/gdb_trace
```

当前常用工具链包括：

- `python3`
- `gdb`
- `gdb-multiarch`
- `qemu-arm`
- `qemu-riscv32`
- `qemu-riscv64`
- `aarch64-linux-gnu-gcc`
- `arm-linux-gnueabihf-gcc`
- `riscv64-linux-gnu-gcc`

## 安装到 GDB

如果希望在 GDB 启动后直接拥有 `gdbtrace` 相关命令，可让 GDB 加载仓库内初始化脚本：

```gdb
python
import runpy
runpy.run_path("/path/to/gdb-trace/gdbtrace/gdb_init.py", run_name="__main__")
end
```

建议把这段加入用户级 `~/.gdbinit`。加载完成后，可在 GDB 中执行：

```gdb
help gdbtrace
```

安装完成后，GDB 内可直接使用与 CLI 一致的命令名，例如：

```gdb
gdbtrace set-target 127.0.0.1:1234
gdbtrace set-arch aarch64
gdbtrace set-elf demo.elf
gdbtrace set-output trace.log
gdbtrace set-mode both
gdbtrace show-config
gdbtrace start
gdbtrace save
gdbtrace stop
```

在 GDB 会话中，如果你已经先执行了 `file /path/to/program`，那么 `gdbtrace start` 在未显式执行 `gdbtrace set-elf` 时，会自动继承当前已加载的 ELF。

同样地，如果你在 `gdb-multiarch` 或支持对应架构字符串的 GDB 中已经先执行了 `set architecture aarch64`、`set architecture arm`、`set architecture riscv:rv32` 或 `set architecture riscv:rv64`，那么 `gdbtrace start` 在未显式执行 `gdbtrace set-arch` 时，也会自动继承当前架构设置。`thumb` / `thumb2` 目前仍建议显式执行 `gdbtrace set-arch`。

如果需要直接调用低层 agent，也可使用：

```gdb
gdbtrace run
```

它会直接调用 `gdbtrace.gdb_agent.run()`，继续使用现有的 `GDBTRACE_GDB_*` 环境变量约定。

## CLI 模型

`gdbtrace` 采用“先配置，后启动”的模型。

常用命令分为三组：

1. 目标地址配置

```bash
python3 -m gdbtrace set-target <ip:port>
python3 -m gdbtrace set-default-target <ip:port>
python3 -m gdbtrace show-target
python3 -m gdbtrace clear-target
python3 -m gdbtrace clear-default-target
```

2. 当前会话配置

```bash
python3 -m gdbtrace set-arch <thumb|thumb2|arm32|aarch64|riscv32|riscv64>
python3 -m gdbtrace set-elf <file>
python3 -m gdbtrace set-output <path.log>
python3 -m gdbtrace set-mode <inst|call|both>
python3 -m gdbtrace set-registers <on|off>
python3 -m gdbtrace show-config
python3 -m gdbtrace clear-arch
python3 -m gdbtrace clear-elf
python3 -m gdbtrace clear-output
python3 -m gdbtrace clear-mode
python3 -m gdbtrace clear-registers
```

3. 生命周期命令

```bash
python3 -m gdbtrace start [--target <ip:port>] [--start <addr|symbol>] [--stop <addr|symbol>] [--filter-func <pattern>] [--filter-range <start:end>]
python3 -m gdbtrace pause
python3 -m gdbtrace save
python3 -m gdbtrace stop
```

## 最小示例

以下示例使用默认静态后端，不依赖真实 GDB 目标。

```bash
python3 -m gdbtrace set-target 127.0.0.1:1234
python3 -m gdbtrace set-arch aarch64
python3 -m gdbtrace set-elf demo.elf
python3 -m gdbtrace set-output ./demo.log
python3 -m gdbtrace set-mode both
python3 -m gdbtrace set-registers off

python3 -m gdbtrace start
python3 -m gdbtrace save
python3 -m gdbtrace stop
```

生成结果：

- `./demo.log`
- `./demo.call.log`

说明：

- `mode=inst` 时只生成 `demo.log`
- `mode=call` 时只生成 `demo.log`
- `mode=both` 时会生成两份日志：
  - 主日志：`demo.log`
  - 调用序列日志：`demo.call.log`

## 输出模式

### inst

只输出指令流：

```log
0x400580 stp x29, x30, [sp, #-16]!
0x400584 mov x29, sp
0x400588 bl func_a
```

如果启用寄存器输出：

```bash
python3 -m gdbtrace set-registers on
```

日志会在每条指令后追加一行寄存器：

```log
0x400724 push {r11, lr}
    regs: r0=0x00000005 r1=0x00000007 r11=0x7fffffe0 lr=0x00010490 sp=0x7fffffd0
0x400728 add r11, sp, #0
    regs: r0=0x00000005 r1=0x00000007 r11=0x7fffffd0 lr=0x00010490 sp=0x7fffffd0
```

### call

只输出函数调用序列：

```log
call main
    call func_a
        call func_b
        ret func_b
    ret func_a
ret main
```

### both

输出函数层级 + 指令流：

```log
call main
    0x400580 stp x29, x30, [sp, #-16]!
    0x400588 bl func_a
    call func_a
        0x4005ac bl func_b
        call func_b
        ret func_b
    ret func_a
ret main
```

补充规则：

- `both` 主日志保留 `call/ret + 指令`
- `both` 的派生 `*.call.log` 只保留 `call/ret`
- `set-registers on` 时，`inst` 和 `both` 模式会在每条指令后追加一行 `regs:`
- 动态库调用优先显示真实函数名，不把 `foo@plt` 当作最终调用边界
- 若缺少稳定符号名，允许显示为 `sub_<addr>`

## 真实后端选择

`gdbtrace` 当前支持以下后端：

- `static`
- `gdb-native`
- `gdb-qemu-aarch64`
- `gdb-qemu-arm`
- `gdb-qemu-riscv`

通过环境变量选择后端：

```bash
export GDBTRACE_CAPTURE_BACKEND=static
```

## aarch64 QEMU gdb stub 示例

在容器中编译一个 `aarch64` 样例：

```bash
aarch64-linux-gnu-gcc -g -O0 -fno-omit-frame-pointer -no-pie \
    test_programs/aarch64_sample.c -o /tmp/aarch64_sample
```

执行 trace：

```bash
export GDBTRACE_CAPTURE_BACKEND=gdb-qemu-aarch64
export GDBTRACE_GDB_MAX_STEPS=20000

python3 -m gdbtrace set-target 127.0.0.1:23064
python3 -m gdbtrace set-arch aarch64
python3 -m gdbtrace set-elf /tmp/aarch64_sample
python3 -m gdbtrace set-output ./aarch64_sample.log
python3 -m gdbtrace set-mode both
python3 -m gdbtrace set-registers on

python3 -m gdbtrace start
python3 -m gdbtrace save
python3 -m gdbtrace stop
```

## arm32 / thumb / thumb2 QEMU gdb stub 示例

以 `arm32` 为例：

```bash
arm-linux-gnueabihf-gcc -g -O0 -fno-omit-frame-pointer -marm \
    test_programs/arm32_sample.c -o /tmp/arm32_sample
```

执行 trace：

```bash
export GDBTRACE_CAPTURE_BACKEND=gdb-qemu-arm
export GDBTRACE_GDB_MAX_STEPS=20000

python3 -m gdbtrace set-target 127.0.0.1:24001
python3 -m gdbtrace set-arch arm32
python3 -m gdbtrace set-elf /tmp/arm32_sample
python3 -m gdbtrace set-output ./arm32_sample.log
python3 -m gdbtrace set-mode both
python3 -m gdbtrace set-registers on

python3 -m gdbtrace start
python3 -m gdbtrace save
python3 -m gdbtrace stop
```

`thumb` / `thumb2` 仅需替换：

- `set-arch thumb` 或 `set-arch thumb2`
- 对应 ELF 文件
- 对应端口

## riscv32 / riscv64 QEMU gdb stub 示例

以 `riscv64` 为例：

```bash
riscv64-linux-gnu-gcc -g -O0 -fno-omit-frame-pointer -march=rv64gc -mabi=lp64d \
    test_programs/riscv64_sample.c -o /tmp/riscv64_sample
```

执行 trace：

```bash
export GDBTRACE_CAPTURE_BACKEND=gdb-qemu-riscv
export GDBTRACE_GDB_MAX_STEPS=20000

python3 -m gdbtrace set-target 127.0.0.1:26064
python3 -m gdbtrace set-arch riscv64
python3 -m gdbtrace set-elf /tmp/riscv64_sample
python3 -m gdbtrace set-output ./riscv64_sample.log
python3 -m gdbtrace set-mode both

python3 -m gdbtrace start
python3 -m gdbtrace save
python3 -m gdbtrace stop
```

## qemu-user 用户态示例

以 `arm32 printf` 用户程序为例：

```bash
arm-linux-gnueabihf-gcc -g -O0 -fno-omit-frame-pointer -Wl,-z,now -marm \
    test_programs/userspace_printf_app.c -o /tmp/userspace_printf_arm32
```

执行 trace：

```bash
export GDBTRACE_CAPTURE_BACKEND=gdb-qemu-arm
export GDBTRACE_GDB_MAX_STEPS=20000
export LD_BIND_NOW=1

python3 -m gdbtrace set-target 127.0.0.1:24101
python3 -m gdbtrace set-arch arm32
python3 -m gdbtrace set-elf /tmp/userspace_printf_arm32
python3 -m gdbtrace set-output ./arm32_printf.log
python3 -m gdbtrace set-mode both

python3 -m gdbtrace start
python3 -m gdbtrace save
python3 -m gdbtrace stop
```

你会看到类似：

```log
call main
    call emit_summary
        call printf
            call sub_4086d36c
```

## 无符号 ELF 说明

真实 backend 对无 `main` 符号 ELF 的行为如下：

- `inst`：允许，输出地址级指令流
- `call`：拒绝
- `both`：拒绝

典型报错：

```text
error: ELF without main symbol supports only inst mode in real backends
```

## 常用查看方式

查看主日志：

```bash
sed -n '1,120p' ./arm32_printf.log
```

查看派生调用日志：

```bash
sed -n '1,80p' ./arm32_printf.call.log
```

若终端支持 ANSI 颜色，日志中的 `call`、`ret` 会有颜色区分。

## 常见问题

### 1. `start` 报缺少配置

说明 `arch`、`elf`、`output`、`mode` 至少有一项未设置。

先执行：

```bash
python3 -m gdbtrace show-config
```

### 2. `remote target is not configured`

说明没有可用的目标地址。

检查：

```bash
python3 -m gdbtrace show-target
```

### 3. 为什么日志里出现 `sub_<addr>`

说明已经进入真实调用路径，但当前 GDB 无法稳定提供函数名。此时 `gdbtrace` 用地址型函数名补齐调用层级，而不是直接丢失这一层。

### 4. 为什么 `both` 会生成两份日志

这是当前设计要求：

- 主日志用于完整分析
- `*.call.log` 用于快速查看调用树

## 相关文档

- 需求文档：[README.md](/Users/caojunze424/code/gdb_trace/README.md)
- 当前进度：[CURRENT_IMPLEMENTATION.md](/Users/caojunze424/code/gdb_trace/CURRENT_IMPLEMENTATION.md)
- 协作约束：[AGENTS.md](/Users/caojunze424/code/gdb_trace/AGENTS.md)
