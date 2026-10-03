# 包装主流静态类型检查器的可行性研究

研究问题：typescope 是否可以让用户选择 Pyright、mypy、Pyrefly 等已有检查器，按需安装并优先复用用户项目中已安装的版本，同时为 `is_assignable(source, target)` 提供与静态检查一致的结果。

## 结论

可以做“可选外部引擎适配器”，但不能把它等同于一个稳定的、进程内的 assignability 函数。三种工具公开且受支持的入口主要是 CLI、LSP 或专用 daemon；它们检查的是带有项目上下文的源代码，而不是两个任意 Python `typing` 对象。建议把引擎集成定义为可选能力：发现并调用用户指定/项目已安装的 checker；找不到或查询能力不足时返回明确的 capability error，并由 typescope 自己的规范实现作为可选 fallback（是否 fallback 需要单独决策）。

## 各引擎的官方入口

### mypy

* mypy 官方文档支持从 Python 导入 `mypy.api` 并调用 `run(list[str])`。返回值只是 `(stdout, stderr, exit_status)`，也就是 CLI 的报告，不是公开的类型对象或 assignability API。[Extending and integrating mypy](https://mypy.readthedocs.io/en/stable/extending_mypy.html#integrating-mypy-into-another-python-application)
* mypy 的插件 API 用于定制分析钩子；文档说明它不能定义新的“一等类型”，并要求插件兼容增量/daemon 模式。因此插件接口不能直接作为通用类型比较引擎。[mypy plugin 文档](https://mypy.readthedocs.io/en/stable/extending_mypy.html#extending-mypy-using-plugins)
* `dmypy` 是长驻进程，通过命令行客户端发送请求并缓存内存中的程序状态；官方警告 daemon CLI 未来可能变化。它能在 `--export-types` 后用 `dmypy inspect` 查询源文件表达式的推断类型，但查询需要文件位置和已成功检查的项目上下文。[mypy daemon](https://mypy.readthedocs.io/en/stable/mypy_daemon.html)
* mypy 仓库和发行包采用 MIT（并包含少量 PSF 许可文件），因此作为可选外部依赖或独立进程调用通常没有 copyleft 隔离问题。[mypy LICENSE](https://github.com/python/mypy/blob/master/LICENSE)

### Pyright

* 官方 CLI 支持 `--outputjson`，输出诊断和汇总；这适合 subprocess 适配器，但仍是对源文件的整体验证，不是两个 `typing` 值的 API。[Pyright command line](https://github.com/microsoft/pyright/blob/main/docs/command-line.md)
* Pyright 内部文档列出 CLI、LSP 和 analyzer 的 `Service`/`Program`/`SourceFile` 架构；`pyright-internal` 是内部实现包，发行包只提供 CLI/LSP bundle，没有文档化的稳定 Python/JS embedding API。[Pyright internals](https://github.com/microsoft/pyright/blob/main/docs/internals.md)、[`pyright-internal` package](https://raw.githubusercontent.com/microsoft/pyright/main/packages/pyright-internal/package.json)、[`pyright` package](https://raw.githubusercontent.com/microsoft/pyright/main/packages/pyright/package.json)
* Pyright 另有 `pyright-typeserver` npm 包。它通过 stdio 上的 JSON-RPC Type Server Protocol（TSP）提供 `getComputedType`、`getDeclaredType`、`getExpectedType`、`resolveImport` 等查询，并与 CLI/LSP 共用 analyzer，因此类型结果保持同一引擎语义。TSP 仍需启动 Node 外部进程、打开/修改文档并用位置查询；没有“比较任意两个 runtime type”的请求。[Pyright Type Server](https://github.com/microsoft/pyright/blob/main/docs/type-server.md)
* Pyright 主仓库和包为 MIT；可按需安装 npm 包并保留许可声明。[Pyright LICENSE](https://raw.githubusercontent.com/microsoft/pyright/main/LICENSE.txt)

### Pyrefly

* Pyrefly 官方定位同时包含 CLI type checker 和 language server；`pyrefly check` 接受文件/目录并从 `pyrefly.toml` 或 `pyproject.toml` 读取配置。[Introduction](https://pyrefly.org/en/docs/)、[Installation](https://pyrefly.org/en/docs/installation/)
* 配置查找会向上搜索 `pyrefly.toml`、`pyproject.toml`、`mypy.ini`、`pyrightconfig.json` 等；无原生配置时还会在内存中迁移 mypy/Pyright 配置。这有利于复用项目设置，但意味着相同源码在不同根目录、配置和解释器下可能得到不同结果。[Configuration finding](https://pyrefly.org/en/docs/configuration/)
* 官方文档公开的是 CLI/LSP 使用方式，没有承诺供 Python 程序导入的 checker API。仓库架构说明核心类型定义在 Rust crate 中，`pyrefly` 是命令行/服务实现；因此从 Python 进程内嵌 Rust checker 不是稳定集成面。[Pyrefly architecture](https://github.com/facebook/pyrefly/blob/main/ARCHITECTURE.md)
* Pyrefly 支持通过 LSP 提供 IDE 类型信息，并持续演进；版本策略明确“不遵循严格语义化版本”，任何版本都可能引入新的类型错误或行为变化。这要求适配器记录并约束引擎版本。[Pyrefly README](https://github.com/facebook/pyrefly)、[IDE](https://pyrefly.org/en/docs/IDE/)
* 官方仓库为 MIT，可作为独立可选安装。[Pyrefly repository/license](https://github.com/facebook/pyrefly)

## 对 typescope API 的影响

### 进程内、CLI、daemon/LSP 的取舍

* **进程内 import**：只有 mypy 明确记录了 `mypy.api.run`，且该 API 只是 CLI 包装；Pyright 的可用内部模块标记为 private，Pyrefly 的核心在 Rust。直接 import checker internals 会把 typescope 绑定到未承诺的内部结构和版本，不能作为稳定公共后端。
* **一次性 subprocess CLI**：三者都适合通过项目环境中的可执行文件运行。请求可生成临时模块/代码片段，运行 checker 的机器可读输出，再解析诊断；隔离依赖、解释器和插件最简单，但启动成本高，且诊断并不天然对应一对 type expression。
* **长驻协议**：mypy daemon、Pyright TSP/LSP、Pyrefly LSP 可复用解析和缓存，适合编辑器或批量查询。协议生命周期、文档状态、取消、版本协商和并发必须由适配器管理；其中 mypy daemon CLI 明确可能变化，TSP/LSP 也不等同于稳定 assignability API。

### 任意两个类型的核心难点

静态 checker 的 assignability 判断通常依赖：模块导入图、typeshed/stub、Python 目标版本、平台、配置开关、插件、已知符号和上下文（表达式位置、泛型约束、flow narrowing）。因此无法仅把 `list[int]` 和 `Sequence[object]` 序列化后发给上述公开接口就得到规范化 bool。

可行的实验性桥接是生成最小临时源文件，例如把 `source` 作为变量/返回值，把 `target` 放在赋值或函数参数位置，然后读取 checker 的“assignment/argument type”诊断。此方法有明显边界：

1. 需要可靠地把 runtime `typing` 表达式重建为源码（局部类、闭包、不可导入对象和 `TypeVar` 绑定无法普遍重建）。
2. 诊断结果受项目配置和引擎版本影响；不同 checker 的 Any、Protocol、Callable、推断和错误恢复策略可能不同。
3. “没有诊断”不一定等价于 `True`（可能是未分析、被忽略、配置禁用、导入失败后降级为 `Any`）。适配器必须区分 `assignable`、`not_assignable`、`unknown/capability_error`。

## 用户环境复用与按需安装建议

1. 后端配置应显式选择 `native`、`mypy`、`pyright`、`pyrefly` 或 `auto`；`auto` 只负责发现，不应悄悄下载工具。
2. 发现顺序建议是：用户显式 executable/command；项目环境（当前 Python 环境的 `sys.executable` 旁边或 PATH）；工作区工具配置（例如 `pyproject.toml`/checker 原生配置）；最后才是可选安装提示。使用 `shutil.which`、`importlib.metadata` 和子进程 `--version` 做能力探测，并记录真实可执行路径与版本。
3. 默认 extras 不应捆绑所有 checker。提供独立 extras（例如 `typescope[mypy]`）只安装 Python checker；Pyright 需要 Node/npm 包，Pyrefly 可由 uv/pip 等安装，故更适合“外部工具已安装”或显式安装向导。不要在库 import 时联网或自动修改用户环境。
4. 适配器缓存键至少包含引擎名称/版本、配置文件摘要、Python 目标版本/平台、解释器路径、依赖搜索路径和输入类型源码；缓存失效必须保守处理。
5. 公开 API 应保留引擎差异：`AssignabilityResult` 至少含 `status`（yes/no/unknown）、`engine`、`engine_version`、可选诊断和上下文指针；文档明确“与所选 checker 在给定配置下尽量一致”，而不是宣称跨 checker 或规范绝对一致。

## 建议的后续决策

将“外部 checker 后端和 capability/error 语义”作为独立规范票据。第一阶段可先实现 CLI JSON 适配器和环境发现，再评估 Pyright TSP/mypy daemon/Pyrefly LSP 的长驻会话；不要把任何 checker 的 private internals 作为 typescope 的基础实现。另需单独决定 native assignability 实现是否始终保留，作为无 checker 环境和任意 runtime type 对象的可预测 fallback。

