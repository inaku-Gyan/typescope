# 需要结构视图的 Python 类型

本研究回答两个问题：`Protocol`、`TypedDict`、`dataclasses.dataclass` 是否需要不同于
普通继承/泛型的实现；以及是否有可以直接复用的库。资料优先使用 Python typing
specification、标准库文档和项目自己的官方文档。结论针对 TypeScope 的
`assignable(source, destination)`，不是对运行时值做校验。

## 结论

这三类对象不能共用“取类名和 MRO 后调用 `issubclass`”的算法，但可以共用一个
**结构视图（shape view）层**。该层把一个类型表达式解析成可比较的成员/键/签名图，
再由各结构类型规则比较图中的成员。结构视图也必须携带 `unknown` 状态：动态属性、
未解析的字符串注解、描述符返回类型或 `dataclass_transform` 的库特定行为无法从类对象
安全恢复时，不能把“未找到”误判为不赋值。

第一版建议不承诺完整的“任意具体类 → Protocol”或 dataclass-like 结构赋值。可以先
保留类型来源和结构能力状态，并把这类比较返回 capability unknown；后续在结构视图层
稳定后，按独立 profile 分阶段加入 `TypedDict`、Protocol 和 dataclass-transform 适配器。
`TypedDict` 的两个标准类型之间只依赖键元数据，适合作为最先恢复的结构规则；Protocol
和 dataclass-like 类需要成员访问、方法签名和动态属性分析，风险明显更高。

## 为什么它们是另一类关系

### Protocol

typing specification 定义 Protocol 的 assignability 是结构关系：具体类必须实现目标
Protocol 的所有成员，且每个成员类型可赋；一个 Protocol 赋给另一个 Protocol 时也比较
成员集合和成员类型，而不是比较 MRO。Protocol 成员包括普通/抽象方法、静态方法、类方法、
property，以及类体中的变量注解；未注解的方法参数按 `Any` 处理。协议变量默认可读写，
只读变量通常用 property 表达。[Protocol members](https://typing.python.org/en/latest/spec/protocol.html#protocol-members)
和 [Protocol assignability](https://typing.python.org/en/latest/spec/protocol.html#assignability-relationships-with-other-types)
说明了这些规则。

因此至少需要区分：

* 方法的完整 `Callable` 签名（位置/关键字参数、默认值、重载和 `self` 处理）；
* 可读属性、可写属性和只读 property；可写属性通常要求不变，而只读结果可按协变比较；
* `ClassVar` 与实例属性；继承后按正常 MRO 解析的成员；递归 Protocol 和字符串前向引用；
* 类对象与实例对象的视图。typing specification 明确 `type[Proto]` 只接受具体的
  Protocol 实现类，不能把 Protocol 类自身当成可实例化的具体类。

`@runtime_checkable` 也不能替代这个层。它只为 `isinstance`/`issubclass` 提供受限的
运行时存在性检查；规范把只含方法的 non-data Protocol 与含数据属性的 data Protocol
区分开，`issubclass` 甚至不能用于 data Protocol。[runtime-checkable restrictions](https://typing.python.org/en/latest/spec/protocol.html#runtime-checkable-decorator-and-narrowing-types-by-isinstance)
。这些检查不比较注解类型，所以不能直接作为 TypeScope 的 assignability 结果。

Python 3.13 新增 `typing.is_protocol()` 和 `typing.get_protocol_members()`，可以可靠地
识别 Protocol 并取得成员名；3.11/3.12 应做 feature detection，不能把私有
`_is_protocol` 当成公共接口。[Python 3.13 typing helpers](https://docs.python.org/3.13/library/typing.html#typing.get_protocol_members)

### TypedDict

TypedDict 的实例在运行时就是普通 `dict`，类型关系由键和值的 schema 决定。规范要求
比较 required/non-required、read-only/mutable、open/closed/extra-items 和每个键的值类型；
普通 `dict[K, V]` 不能仅因键值类型相容就赋给 TypedDict，因为它不能证明 required key
存在。完整规则见 [TypedDict structural assignability](https://typing.python.org/en/latest/spec/typeddict.html#subtyping-and-assignability)。

TypedDict 比 Protocol 更适合先实现，因为 schema 可以从类元数据中提取，不需要执行对象
属性：

* 3.9 起有 `__required_keys__` 和 `__optional_keys__`；`__total__` 只反映当前类体的
  `total` 参数，不代表继承后每个键的实际 required 状态；
* 3.13 起有 `__readonly_keys__` 和 `__mutable_keys__`，并加入 `ReadOnly`；
* 使用 `from __future__ import annotations` 或字符串注解时，标准文档警告上述集合可能
  不正确，因为定义时没有求值注解；这应产生 capability unknown 或要求显式 evaluation
  context，而不是静默采用空 schema。[TypedDict introspection](https://docs.python.org/3.13/library/typing.html#typing.TypedDict)

因此 TypedDict 需要 `KeyShape`，而不是普通 `MemberShape`：键名、值类型、required、
readonly、额外键策略是第一等字段。TypedDict 之间的比较仍然可复用递归
`assignable(value_type)` 和未知传播规则。

### dataclasses.dataclass 与 dataclass-like 类

标准 dataclass 装饰器返回同一个 class，并根据带注解的类变量生成 `__init__`、比较方法
等；它不是一个新的静态类型种类。`dataclasses.fields()` 返回真实字段，排除 `ClassVar`
和 `InitVar`；`InitVar` 只进入生成的 `__init__`/`__post_init__`，并不是实例字段。
`slots=True` 还可能返回新 class，且官方明确不能通过 `__slots__` 推断字段名，应使用
`fields()`。[dataclasses module](https://docs.python.org/3.13/library/dataclasses.html#dataclasses.dataclass)
、[fields and InitVar](https://docs.python.org/3.13/library/dataclasses.html#dataclasses.fields)
。

所以两个 dataclass 之间没有“按字段同构即可赋值”的标准语义：它们仍是普通名义 class，
直接赋值关系由继承决定。字段结构只有在以下场景才影响类型检查：

* dataclass 实例作为 Protocol 的实现，需要把字段/属性暴露为 Protocol 成员；
* 调用生成的 `__init__` 时，需要比较构造签名；
* `dataclass_transform` 让第三方装饰器、基类或 metaclass 具有 dataclass-like 的静态
  行为。

`dataclass_transform` 是关键的扩展边界：运行时装饰器只保证设置
`__dataclass_transform__` 属性，实际字段收集、默认值、别名、converter 和生成方法由
库实现；typing specification 规定了 type checker 应理解的共同参数，但也允许额外参数。
规范还明确 `attrs` 的 `factory` 是 `default_factory` 的别名，并把 attrs、pydantic 作为
真实使用者。[dataclass transform specification](https://typing.python.org/en/latest/spec/dataclasses.html)
、[PEP 681](https://peps.python.org/pep-0681/)。

这意味着 TypeScope 不能仅凭 `__dataclass_transform__` 推导完整运行时 shape；应提供
可插拔的 `ShapeProvider`（stdlib dataclass、attrs、pydantic 等），未注册的 provider
返回 capability unknown。dataclass 的字段视图可以作为 Protocol 的一种来源，但不应把
dataclass 本身提升为结构类型。

## 还有哪些类型属于结构视图类别

### Callback Protocol 和 Callable

Callback Protocol 用带 `__call__` 成员的 Protocol 表达关键字参数、可变参数、默认值和
重载等 `Callable[...]` 难以表达的签名。比较时仍是 Protocol member lookup 加 callable
参数逆变/返回值协变，不能只读取 `__bases__`。[callback protocols](https://typing.python.org/en/latest/spec/callables.html#callback-protocols)
。

### NamedTuple

`typing.NamedTuple`/`collections.namedtuple` 同时具有 tuple 的名义继承和字段属性。它
通常不产生“任意同字段类可互赋”的结构关系，但当目标是 Protocol 或调用构造器时，需要
字段/签名视图。Pydantic 的 `typing-inspection` 也把 `NAMED_TUPLE` 作为独立 annotation
source，说明它不应被普通 class 处理。[typing-inspection annotation sources](https://typing-inspection.pydantic.dev/latest/api/introspection/#annotationsource)

### 运行时 ABC 与动态对象

`collections.abc` 的部分 ABC 可以通过 `__subclasshook__` 或注册虚拟子类提供运行时
结构判断，但这不是 typing Protocol 的完整成员类型关系。对象可能通过 `__getattr__`、
metaclass、descriptor 或动态赋值提供成员；只读静态扫描无法证明其类型，必须允许
unknown。读取 class 字典时宜使用 `inspect.getattr_static` 等不执行 descriptor 的方式，
但这仍然只是保守快照，不是完整语义。

## 可以复用的轮子

没有一个标准库 API 能直接回答“两个任意 typing 对象是否 assignable”，也没有发现一个
同时提供 Python typing 规范、Protocol/TypedDict/dataclass 结构语义、`Any`/`Unknown`/能力
错误和 3.11–3.13 兼容矩阵的现成库。以下库可作为局部复用或 oracle，不能直接成为
TypeScope 的规范内核：

### beartype DOOR

`beartype.door.is_subhint(subhint, superhint)` 明确比较两个 type hints 的 subhint 关系，
并提供 `TypeHint` 包装、统一的 `.args` 和缓存；官方示例涵盖泛型和 Callable，并把 API
用于多重 dispatch 与 API 兼容性检查。[DOOR `is_subhint`](https://beartype.readthedocs.io/en/latest/api_door/#beartype.door.is_subhint)
、[TypeHint API](https://beartype.readthedocs.io/en/latest/api_door/#beartype.door.TypeHint)。

它返回单一 bool，没有 TypeScope 所需的 `unknown`、规则路径、semantic profile 和
capability error；文档也没有承诺与 typing specification/某个 checker 的逐项等价。因此
更适合作为兼容性对照、fuzz oracle 或未来可选 backend，不能让它决定 native profile 的
语义。Protocol、TypedDict 和 dataclass-like shape 仍应先验证其具体版本行为，再决定是否
委托。

### Typeguard

`typeguard.check_type(value, annotation)` 是运行时“值是否匹配注解”的检查器，不是 hint
之间的关系判断。其官方功能表包含 TypedDict 内容检查、Protocol 实例/类检查、NamedTuple
字段检查和 TypeVar 约束，但这些都需要一个实际 value/class，并不提供 source/destination
两棵类型表达式的结构比较。[Typeguard checking features](https://typeguard.readthedocs.io/en/latest/features.html)
、[check_type API](https://typeguard.readthedocs.io/en/stable/api.html#typeguard.check_type)。

### typing-inspection（Pydantic 维护）

`typing-inspection` 专注运行时 annotation 解析：可识别 `typing` 与 `typing_extensions`
对象、拆出 `Annotated` metadata/qualifier，并把 `DATACLASS`、`TYPED_DICT`、`NAMED_TUPLE`
作为 annotation source；其低级 API 明确同时检查标准库和 backport 变体。这很适合作为
TypeScope normalization/feature-detection 的候选依赖或设计参考，但没有 assignability
算法。[introspection API](https://typing-inspection.pydantic.dev/latest/api/introspection/)
、[typing object predicates](https://typing-inspection.pydantic.dev/latest/api/typing_objects/)。

### attrs、pydantic 等 dataclass-like 库

它们是 shape 的生产者，不是通用 assignability 引擎。`dataclass_transform` 统一了静态
字段规范，但每个库仍可定义自己的 converter、alias、validator、descriptor 和动态字段。
因此可为这些库实现 `ShapeProvider`，不能把某个库的 field metadata 当作所有类的标准。

## 共通实现建议

### 1. 分离表达式归一化、结构提取与关系规则

建议三层接口：

```text
normalize(type_expression, evaluation_context) -> NormalizedType
shape(normalized_type, view_kind) -> ShapeView | CapabilityUnknown
compare(source_shape, destination_shape, relation_context) -> EvaluationResult
```

`NormalizedType` 负责 `typing`/`types`/`typing_extensions` 的语义身份；`ShapeView` 负责
成员/键/签名，不把类名或 `repr` 当身份；关系规则负责 Protocol、TypedDict、callback
和未来 provider。每层都保留 provenance（实际模块、版本和语法来源）。

### 2. 统一的 ShapeView 数据模型

一个可行的最小模型是：

```text
ShapeView
  kind: protocol | typed_dict | dataclass | named_tuple | class | callable
  identity: semantic identity
  members: Mapping[str, MemberSpec]       # Protocol/class/dataclass/NamedTuple
  keys: Mapping[str, KeySpec]             # TypedDict
  call: CallableSignature | None
  openness: open | closed | extra_items | n/a
  resolution: complete | partial | unknown

MemberSpec
  read_type, write_type, callable_signature
  member_kind: attribute | property | method | classvar | field
  readable, writable, required

KeySpec
  value_type, required, readonly
```

`ShapeView` 应该是不可变、可缓存的图；递归 Protocol/字段用 identity 节点和 cycle guard，
解析超限返回 capability unknown。成员缺失（明确 `no`）必须和成员无法发现（`unknown`）
区分。

### 3. 使用公开元数据，避免执行用户代码

* Protocol：3.13 使用 `is_protocol`/`get_protocol_members`；成员注解和 callable 签名用
  受控的 `inspect`/annotation resolver，并要求 evaluation context；不要调用实例属性。
* TypedDict：优先 `inspect.get_annotations`、`__required_keys__`、`__optional_keys__`，
  3.13 再读取 `__readonly_keys__`；字符串注解未求值时标记 partial/unknown。
* dataclass：使用 `dataclasses.is_dataclass`、`dataclasses.fields` 和 `Field` 的公开属性；
  不依赖私有字段，也不从 `__slots__` 猜字段。
* 普通类/Protocol 实现：扫描 class MRO 和静态 descriptor；无法观察实例构造后才出现的
  属性、`__getattr__` 或 metaclass 注入时返回 unknown。

### 4. 先实现窄的结构 profile

建议首个可交付 profile：

1. 完整实现 `TypedDict → TypedDict` 的键规则（按当前 Python 能安全观察的 required/readonly
   元数据）；3.11/3.12 没有 `ReadOnly` 时不伪造 3.13 语义。
2. 实现 Protocol → Protocol 和显式已知成员的 callback Protocol；把具体类 → Protocol、
   动态属性、递归/未解析前向引用归为 capability unknown。
3. dataclass 只作为名义 class 处理；允许其 `ShapeView` 作为 Protocol source 的实验能力，
   但未注册 `dataclass_transform` provider 时不推断第三方模型。
4. 每条 structural 规则输出 rule path 和 provenance；兼容不同 checker 的结果只能走显式
   checker profile 或外部 oracle，不污染 native profile。

## 3.11–3.13 能力边界

| 能力 | 3.11 | 3.12 | 3.13 |
| --- | --- | --- | --- |
| TypedDict required/optional 元数据 | `__required_keys__`/`__optional_keys__` | 同 | 同 |
| TypedDict `ReadOnly` | 无标准库形式（可有 backport） | 通常依赖 backport | 标准库 `ReadOnly` 与 readonly/mutable key 集合 |
| Protocol 识别 | 需兼容探测 | 需兼容探测 | `is_protocol`/`get_protocol_members` |
| dataclass fields | `dataclasses.fields` | 同 | 同；`slots`/生成方法行为仍由 decorator 参数决定 |
| dataclass-like 静态转换 | `dataclass_transform` 可用 | 同 | 同；额外参数仍由库定义 |

Python 官方文档还警告，字符串或 postponed annotations 会使 TypedDict required/optional
集合不可靠；这正是 evaluation context 与 capability unknown 必须成为公共契约的原因。

## 建议的决策

* 将“结构类型视图和 provider 接口”单独作为架构决策，不把它埋进普通 class assignability。
* 首版 native profile 对无法完整建立 shape 的 Protocol、TypedDict、dataclass-like 比较返回
  capability unknown，并保留 provenance；不要用 `isinstance`/`issubclass` 或 `@runtime_checkable`
  的布尔结果冒充静态 assignability。
* 评估 beartype `is_subhint` 作为外部 oracle，评估 typing-inspection 作为 normalization
  依赖；两者都不直接决定 TypeScope 的 native 语义。
* 后续按独立票据实现 `TypedDict`、Protocol、dataclass-transform providers，并为每个 provider
  写跨 3.11–3.13 的能力矩阵和 unknown 测试。
