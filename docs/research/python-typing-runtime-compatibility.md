# Python typing 规范与跨版本运行时表示

研究对象是 typescope 的运行时 `assignable(source, destination)` 语义。当前项目声明
`requires-python >=3.11`，并以 3.11、3.12、3.13 为发布分类；下表按这三个版本整理。
资料优先采用 Python typing specification、Python 标准库文档和已接受的 PEP。运行时类名
（例如 `typing._GenericAlias`）属于 CPython 实现细节，不应成为公开 API 的判别依据。

## 先固定术语和方向

typing specification 把 assignability 定义为 consistent subtyping：类型 `B` 可赋值给
类型 `A`，表示 `B` 是 `A` 的 consistent subtype。typescope 的 API 应固定为
`assignable(source=B, destination=A)`，不要把参数顺序留给调用方猜测。[Type system concepts](https://typing.python.org/en/latest/spec/concepts.html#the-assignable-to-or-consistent-subtyping-relation)

对于完全静态类型，普通类的子类型关系对应继承关系；Protocol 和 TypedDict 是结构类型，
可以在没有继承关系时成为子类型。[Nominal and structural types](https://typing.python.org/en/latest/spec/concepts.html#nominal-and-structural-types)

## 规范语义矩阵

| 能力 | typing specification / PEP 规则 | 对运行时实现的约束 | 语义归属 |
| --- | --- | --- | --- |
| 普通类 | 子类实例类型可赋给基类；继承关系是名义子类型。 | 对两个 class 使用 `issubclass(source, destination)`，并处理 `bool` 等真实继承。 | 标准语义 |
| `Any` | `Any` 代表未知静态类型；任何类型可赋给 `Any`，`Any` 也可赋给任何类型。渐进类型不是“所有运行时对象”的集合。 | `typing.Any` 是单例式特殊对象，`get_origin/get_args` 都为空；必须先于普通 class 逻辑处理。嵌套 `list[Any]` 等仍然是渐进类型。 | 标准语义 |
| `Never` / `NoReturn` | `Never` 是空集底类型；自 Python 3.11 起提供，和 `NoReturn` 语义等价。作为 source 时可赋给任意 destination；destination 为 `Never` 时只有空类型（以及按 `Any` 规则处理的 `Any`）可通过。 | 两者都是 special form，不能依赖 `isinstance` 或 `issubclass`；比较对象身份和规范化别名。 | 标准语义 |
| `None` | 注解中的 `None` 等价于 `type(None)`；`T | None` 是显式可空类型。仅因默认值为 `None` 就自动添加 Optional 已不再是推荐行为。 | 原始 `__annotations__` 可能保存 `None` 或字符串；规范化时把注解表达式 `None` 映射为 `type(None)`，不要把“参数有默认值”当成类型关系。 | 标准语义（旧 checker 行为需单独 profile） |
| Union / `|` | `X | Y` 与 `Union[X, Y]` 等价；Union 成员可分别赋给 Union。子类型关系可以消除冗余成员，但 `T | Any` 不能简单化为 `Any`，它保留 `T` 这个下界。 | 3.10+ 的 `|` 通常是 `types.UnionType`，旧语法是 `typing.Union` 相关对象；用 `get_origin`/`get_args` 展开成员，不能按 repr 或私有类名分支。 | 标准语义 |
| 泛型与方差 | 每个泛型参数按声明方差比较：协变同向、逆变反向、不变要求双向等价。只读集合如 `Sequence`/`Mapping` 协变；可变 `list`/`MutableSequence`/`MutableMapping` 不变。 | 既要判断 origin 的继承/实现关系，也要取得类型参数和每个参数的方差；`list[int]` 与 `typing.List[int]` 应归一到同一 origin。 | 标准语义 |
| `TypeVar` | 有 bound 时，替换类型必须可赋给 bound；有 constraints 时只能选择约束项，且 checker 的求解细节并未完全规范化。协变/逆变只对绑定到泛型类有意义，对泛型函数和别名不能直接套用。 | 3.11 可读 `__bound__`、`__constraints__`、`__covariant__`、`__contravariant__`；3.12 增加 `infer_variance` 与 PEP 695 参数；3.13 增加默认值和 `typing.NoDefault`。直接比较含自由 TypeVar 的两个表达式必须规定绑定/量化策略。 | 标准语义 + checker 求解约定 |
| Protocol | 具体类型 `X` 可赋给 Protocol `P`，当且仅当实现 P 的全部成员且成员类型可赋；Protocol 不能赋给具体类型；Protocol 之间按成员包含关系结构赋值。泛型 Protocol 沿用方差规则。 | 需要从类注解、方法签名和继承的 Protocol 成员构建结构视图；`@runtime_checkable` 的 `isinstance` 只检查运行时可检查属性，不能替代静态成员类型 assignability。 | 标准语义 |
| `Callable` | source callable 的返回类型须可赋给 destination 返回类型；source 参数必须接受 destination 可能传入的全部参数，即参数逆变、返回值协变；参数种类、名称、默认值、`*args`/`**kwargs` 和 overload 影响结果。 | `get_args(Callable[[A], R])` 常见形态为 `([A], R)`；也可能是 `...`、ParamSpec、Concatenate。仅依赖这个列表不足以表达 callback Protocol 的 keyword-only/positional-only 细节。 | 标准语义 |
| `type[T]` | `type[Derived]` 可赋给 `type[Base]`，参数协变；传入值必须是真实 class object，不能是 Union 或 Callable 等 special form。 | `type` 裸形式等价 `type[Any]`；按 origin `type` 单独处理 class-object 关系。 | 标准语义 |
| 数值快捷规则 | `int` 可作为 `float` 参数，`int` 或 `float` 可作为 `complex` 参数，尽管这些 class 并非彼此子类。 | 这是 assignability 规则，不能由 `issubclass` 推导；应放在 profile 的基础类型规则中。 | 标准语义 |

来源：[special types](https://typing.python.org/en/latest/spec/special-types.html)、[generics and variance](https://typing.python.org/en/latest/spec/generics.html#variance)、[protocol assignability](https://typing.python.org/en/latest/spec/protocol.html#assignability-relationships-with-other-types)、[callable assignability](https://typing.python.org/en/latest/spec/callables.html#assignability-rules-for-callables)、[PEP 585](https://peps.python.org/pep-0585/)、[PEP 604](https://peps.python.org/pep-0604/)。

## 运行时表示兼容矩阵

以下是应由一个版本无关的 introspection 层统一出来的观察结果。`typing.get_origin` 和
`typing.get_args` 自 Python 3.8 起可用；`get_origin` 会把 `typing.Dict` 等旧别名归一到
`dict`，但 Union 的 origin 仍可能是 `typing.Union` 或 `types.UnionType`。`get_args` 的
Union/Literal 参数顺序可能因缓存而不同，因此联合类型应按集合/规范化键比较。[Python 3.11 typing introspection](https://docs.python.org/3.11/library/typing.html#introspection-helpers)

| 表达式 | 3.11 | 3.12 | 3.13 | 统一策略 |
| --- | --- | --- | --- | --- |
| `list[int]`, `dict[str, int]` | `types.GenericAlias`，有 `__origin__`/`__args__`/`__parameters__` | 同 | 同 | 优先 `get_origin/get_args`；PEP 585 说明参数在运行时保留，但实例化会擦除参数。 |
| `typing.List[int]`, `typing.Dict[...]` | 旧 typing alias（私有实现类可能不同） | 同 | 同 | 用 `get_origin` 归一到内建 origin；将旧别名和 PEP 585 别名视为同一表达式。 |
| `int | str` 与 `Union[int, str]` | 前者 `types.UnionType`，后者 `typing.Union` alias | 同 | 同 | 展开 args、去重、忽略顺序；保留 `Any` 的渐进下界规则。PEP 604 明确两种语法等价。 |
| `class C(Generic[T])` / `C[int]` | 传统 Generic 和 alias；可读 origin/args/parameters | 仍支持传统形式 | 仍支持传统形式 | 不读取私有 alias 类名；从 origin、args 和 `__parameters__` 建立泛型实例。 |
| `class C[T]`、`type Alias[T] = ...` | 语法不可用 | PEP 695；generic object 有 `__type_params__`，类型别名是 `typing.TypeAliasType` | 同 | 兼容两种声明；若要展开 TypeAliasType，应显式记录别名边界和延迟求值。 [PEP 695](https://peps.python.org/pep-0695/) |
| `TypeVar` | 构造器形式；bound/constraints/variance 属性 | 增加 `infer_variance` 和新语法参数 | 增加 `default`/`__default__`，无默认值由 `typing.NoDefault` 表示 | 通过公开属性读取，不假定类型变量一定有可求值 bound；`TypeVar` 本身不是 class。 [3.13 docs](https://docs.python.org/3.13/library/typing.html#typing.TypeVar) |
| `Protocol` | Protocol class；没有 `is_protocol`/`get_protocol_members` 公共 helper | 同 | `typing.is_protocol`、`typing.get_protocol_members` 新增；generic alias 仍不会被 `is_protocol` 识别 | 3.13+ 使用 helper；3.11/3.12 需要可隔离的兼容探测，不要把私有 `_is_protocol` 变成公共契约。 [3.13 docs](https://docs.python.org/3.13/library/typing.html#typing.is_protocol) |
| `Callable` | `typing.Callable` 和 `collections.abc.Callable` 均可参数化；ParamSpec/Concatenate 已支持 | 同 | 同 | 以 `get_origin` 得到 `collections.abc.Callable` 为主；args 只够表达简单签名，复杂签名转用 `inspect.signature` 或 Protocol 成员。 |
| `ForwardRef` / 字符串注解 | `typing.List["X"]` 使用 ForwardRef；PEP 585 的 `list["X"]` 不自动转换为 ForwardRef | 同 | 同 | `get_type_hints(obj, globalns, localns, include_extras=...)` 需要解析上下文，失败应产生 capability/unknown，而不是静默 false。 [3.13 docs](https://docs.python.org/3.13/library/typing.html#typing.ForwardRef) |
| `Annotated`、`Literal`、`TypedDict` | 已有运行时对象；`is_typeddict` 自 3.10 可用 | 同 | Protocol helper 增加；TypedDict 的 `ReadOnly` 与 key 属性增加 | 这些类型不是本票据核心，但 introspector 必须保留 origin/args/metadata/key-required 信息，后续决定是否纳入 profile。 |

PEP 585 特别指出，参数化泛型不能直接用于 `isinstance`/`issubclass`，而且创建实例时类型参数会擦除；因此 typescope 的 assignability 是“比较类型表达式”，不是把运行时值交给这些内建检查。[PEP 585 runtime behavior](https://peps.python.org/pep-0585/#parameters-to-generics-are-available-at-runtime)

## 3.11–3.13 的版本边界

* **3.11 基线**：`Never`、PEP 585/604 的运行时 generic/union 表示、ParamSpec/Concatenate、`get_origin`/`get_args`、`is_typeddict` 和泛型 TypedDict 可用。PEP 695 语法不可用，Protocol 成员只能通过类元数据和注解自行收集。
* **3.12 变化**：PEP 695 引入 `class C[T]`、`def f[T]`、`type Alias[T]` 及 `__type_params__`；TypeVar 增加 `infer_variance`。旧构造器必须继续支持，因此规范化不能只看新语法。
* **3.13 变化**：提供 `typing.is_protocol`、`typing.get_protocol_members`；TypeVar 默认值和 `NoDefault` 可见；TypedDict 的 `ReadOnly` 元数据出现。若库仍支持 3.11，公共 API 不能无条件导入这些名字，应采用 feature detection。
* **前向兼容**：标准库文档说明 `typing_extensions` 为较旧 Python 回移新 typing 特性；因此输入可能来自 `typing` 或 `typing_extensions`。判别应基于公开的 origin/args/属性和语义标签，而不是模块名精确相等。[Python typing docs](https://docs.python.org/3.11/library/typing.html)

## checker 约定与本库定义的分界

typing specification 是默认标准语义；但 checker 仍有需要显式记录的约定：

* TypeVar 的 constraint solving 在 PEP 484 中并未完全规定，Pyright 文档也指出约束求解会综合方差和 bound；不同 checker 或版本可能给出不同推断。[Pyright 对 mypy 的比较](https://github.com/microsoft/pyright/blob/main/docs/mypy-comparison.md#constraint-solver-behaviors)
* Pyright 区分 `Unknown` 与 `Any`，把 Unknown 描述为 Any 的特殊形式；typescope 的 native 表达式只遇到 `typing.Any` 时不能擅自宣称等同 Unknown。若接入外部 checker，应保留 engine/version/context。[Pyright type inference](https://github.com/microsoft/pyright/blob/main/docs/type-inference.md#unknown-type)
* 默认值为 `None` 的隐式 Optional 是历史差异：typing spec 建议显式写 `T | None`；Pyright 的比较文档说明它不会按 mypy 的规则特殊处理 None。该行为只能属于选定 checker profile，不能写进无版本的 native 规则。[typing spec union with None](https://typing.python.org/en/latest/spec/concepts.html#union-with-none)、[Pyright/mypy comparison](https://github.com/microsoft/pyright/blob/main/docs/mypy-comparison.md#none-return-type)

建议把下面几项明确标为 **Wayfinder semantic extension**，直到另一个决策票据定案：

1. 含自由 `TypeVar` 的两个独立 type expression 是否按存在量词、全称量词、或先绑定再比较；
2. TypeAliasType 是否透明展开、保留别名身份，及递归别名的循环/深度上限；
3. Protocol 的运行时结构检查是否解析方法签名、属性可写性、继承和 overload，还是只提供能力受限的 nominal/attribute 模式；
4. 无法解析 ForwardRef、未知 typing_extensions 形式或 checker-specific Unknown 时，结果返回 `unknown/capability_error` 还是拒绝输入；
5. `Annotated` metadata、Literal、TypedDict、ParamSpec/TypeVarTuple 等超出第一阶段核心的表达式是否纳入语义 profile。

这些扩展不应伪装成 Python 标准的布尔答案；结果契约应至少区分 `yes`、`no` 和 `unknown/capability_error`，并携带使用的 semantic profile。

## 后续实现顺序

1. 先实现与版本无关的表达式归一化：class、Any/Never/None、Union、GenericAlias/typing alias、TypeVar、Callable、Protocol 标识和 ForwardRef 状态；统一使用 `get_origin/get_args`，并记录 Python 版本。
2. 以规范关系实现 nominal、特殊类型、Union、泛型方差、Callable 和 Protocol 的最小闭环；每条规则输出可解释的 rule path。
3. 用 3.11、3.12、3.13 的矩阵测试新旧拼写、PEP 695 参数和 3.13 helper 的 feature detection。
4. 另开决策票据处理 checker adapter、constraint solving、别名/递归、TypedDict/Literal/Annotated 等未定语义。
