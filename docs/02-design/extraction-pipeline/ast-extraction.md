# Pass 1: AST 确定性提取

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` | **last_verified**: 2026-04-19

## 目的

定义提取管线第一通道——基于 AST 解析和结构化规则的确定性提取。此通道零 LLM 成本，通过 tree-sitter、正则表达式和结构化解析器，从代码文件、YAML/JSON 配置、Markdown 文档中提取结构化的实体和关系。所有提取结果的置信度标签为 EXTRACTED（confidence=1.0）。

## 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 代码文件的结构信息（类、函数、导入、调用图）无法被语义检索 | tree-sitter AST 解析提取 class/function/import/call 节点 |
| 2 | 结构化数据（YAML/JSON）无需 LLM 即可提取 | 专用解析器直接映射为 EntityInstance |
| 3 | Markdown 文档的标题/表格结构信息丢失 | 正则 + Markdown 解析器提取 heading/table 节点 |
| 4 | 确定性提取与语义推断混在一起，无法区分可信度 | Pass 1 独立执行，所有产出 confidence=1.0, 标签=EXTRACTED |
| 5 | 提取结果与 Schema v2 Instance 层不对齐 | 严格输出 EntityInstance / EdgeInstance / KnowledgeFragment |

---

## 提取源类型与策略

| 源类型 | 文件扩展名 | 提取策略 | 提取内容 |
|--------|-----------|----------|----------|
| **Python 代码** | .py | tree-sitter Python | class, function, import, call, inheritance |
| **TypeScript/JS 代码** | .ts, .tsx, .js, .jsx | tree-sitter TypeScript/JS | class, function, import, call, arrow function |
| **Java 代码** | .java | tree-sitter Java | class, interface, method, import, call |
| **Go 代码** | .go | tree-sitter Go | struct, func, import, call |
| **Rust 代码** | .rs | tree-sitter Rust | struct, fn, use, call |
| **C/C++ 代码** | .c, .cpp, .h, .hpp | tree-sitter C/C++ | function, struct, include, call |
| **YAML 配置** | .yaml, .yml | PyYAML 解析 | schema 定义、规则定义、维度定义 |
| **JSON 数据** | .json | json 解析 | 结构化数据记录 |
| **Markdown 文档** | .md | 正则 + Markdown 解析 | heading, table, code block, link |
| **CSV 数据** | .csv | csv 解析 | 每行作为一个数据记录 |

---

## 代码文件 AST 提取

### 目的

从源代码文件中提取结构化的类、函数、导入和调用关系，构建代码知识图谱。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 代码结构信息无法被知识图谱检索 | AST 提取产出 EntityInstance（类/函数节点）和 EdgeInstance（包含/导入/调用边） |
| 2 | 跨文件依赖关系不可见 | import 边连接文件节点与模块节点，call 边连接调用者与被调用者 |
| 3 | 继承/实现关系丢失 | inherits 边记录类继承和接口实现 |

### 提取节点类型

| 节点类型 | EntityInstance._fact_object | 提取来源 | 示例 |
|----------|---------------------------|----------|------|
| file | code:File | 每个源文件 | `src/engine/rule_engine.py` |
| class | code:Class | class_definition | `RuleEngine` |
| function | code:Function | function_definition / method_declaration | `execute_rule()` |
| module | code:Module | import 语句的目标 | `ontology_engine.storage` |

### 提取边类型

| 边类型 | EdgeInstance.relation_name | 语义 | confidence |
|--------|--------------------------|------|-----------|
| contains | code:contains | 文件包含类/函数 | 1.0 (EXTRACTED) |
| imports | code:imports | 文件导入模块 | 1.0 (EXTRACTED) |
| calls | code:calls | 函数调用函数 | 1.0 (EXTRACTED) |
| inherits | code:inherits | 类继承类 | 1.0 (EXTRACTED) |

### 提取流程

```
输入: source_file_path
  │
  ├─ 1. 识别语言类型（基于文件扩展名）
  │     → 选择 LanguageConfig
  │
  ├─ 2. tree-sitter 解析
  │     parser = Parser(Language(lang_fn()))
  │     tree = parser.parse(source_bytes)
  │
  ├─ 3. 遍历 AST 节点
  │     walk(root_node):
  │       - class_types → 创建 class EntityInstance + contains EdgeInstance
  │       - function_types → 创建 function EntityInstance + contains EdgeInstance
  │       - import_types → 创建 module EntityInstance + imports EdgeInstance
  │       - call_types → 创建 calls EdgeInstance
  │
  ├─ 4. 生成 EntityInstance
  │     id = UUID5(namespace, identity_fields)
  │     _fact_object = "code:Class" | "code:Function" | ...
  │     attributes = {name, source_location, ...}
  │     confidence = 1.0
  │     source_pipeline = "ast_extraction"
  │     source_content_hash = SHA256(file_content + relative_path)
  │
  ├─ 5. 生成 EdgeInstance
  │     from_id / to_id 引用 EntityInstance.id
  │     relation_name = "contains" | "imports" | "calls" | "inherits"
  │     confidence = 1.0
  │     source_pipeline = "ast_extraction"
  │
  └─ 6. 创建 EXTRACTED_FROM 边
        每个 EntityInstance → KnowledgeFragment
        source_file = 文件路径
        offset_start/end = AST 节点的字节范围
        confidence = 1.0
```

### LanguageConfig 模式

参考 Graphify 的 LanguageConfig dataclass 模式，OntologyEngine 为每种支持的语言定义提取配置：

| 配置项 | Python 示例 | 说明 |
|--------|------------|------|
| ts_module | tree_sitter_python | tree-sitter 语言模块 |
| class_types | {class_definition} | 类定义节点类型 |
| function_types | {function_definition} | 函数定义节点类型 |
| import_types | {import_statement, import_from_statement} | 导入节点类型 |
| call_types | {call} | 调用节点类型 |
| import_handler | _import_python | 语言特定的导入处理函数 |

### 参考项目对齐

| 参考项目 | 模式 | OntologyEngine 对齐 |
|----------|------|-------------------|
| Graphify _extract_generic | LanguageConfig 驱动的通用 AST 提取器 | 复用 LanguageConfig 模式，增加 Schema v2 Instance 层对齐 |
| Graphify _make_id | 稳定节点 ID 生成 | 改用 UUID5 基于 identity_fields，支持跨管道幂等 |
| Graphify add_node / add_edge | 节点/边添加辅助函数 | 产出 EntityInstance / EdgeInstance，增加 _fact_object / relation_name |
| Graphify walk | AST 递归遍历 | 复用 walk 模式，增加 EXTRACTED_FROM 边创建 |
| Graphify _import_python | Python 导入处理 | 复用导入处理逻辑，产出 EdgeInstance(relation_name="imports") |

---

## YAML/JSON 结构化数据提取

### 目的

从 YAML/JSON 配置文件中提取 Schema 定义、规则定义和维度定义，直接映射为 EntityInstance 和 EdgeInstance。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | Schema YAML 定义无法自动进入知识图谱 | YAML 解析器将 EntityDeclaration 映射为 EntityInstance |
| 2 | 规则定义与业务实体脱节 | 规则定义提取后通过 EdgeInstance 关联到 Fact Object |

### 提取策略

| 文件类型 | 提取内容 | EntityInstance._fact_object |
|----------|----------|---------------------------|
| schema.yaml | EntityDeclaration | schema:EntityDeclaration |
| schema.yaml | RelationDeclaration | schema:RelationDeclaration |
| schema.yaml | DimensionDeclaration | schema:DimensionDeclaration |
| schema.yaml | MetricDeclaration | schema:MetricDeclaration |
| schema.yaml | RuleDefinitionDeclaration | schema:RuleDefinitionDeclaration |
| *.json | 结构化数据记录 | 按内容自动推断 |

### YAML 提取流程

```
输入: schema.yaml 文件
  │
  ├─ 1. PyYAML 解析
  │     schema = yaml.safe_load(content)
  │
  ├─ 2. 遍历顶层键
  │     for key in schema:
  │       match key:
  │         "fact_object" → 创建 schema:EntityDeclaration EntityInstance
  │         "relation" → 创建 schema:RelationDeclaration EntityInstance
  │         "categorization" → 创建 schema:DimensionDeclaration EntityInstance
  │         "metric" → 创建 schema:MetricDeclaration EntityInstance
  │         "rule_definition" → 创建 schema:RuleDefinitionDeclaration EntityInstance
  │
  ├─ 3. 生成 EntityInstance
  │     id = UUID5(namespace, declaration.name)
  │     _fact_object = "schema:{DeclarationType}"
  │     attributes = {name, description, ...从声明中提取的属性}
  │     confidence = 1.0
  │     source_pipeline = "ast_extraction"
  │
  ├─ 4. 生成 EdgeInstance
  │     relation_name = "defines" | "applies_to" | "depends_on"
  │     from_id = 声明 ID, to_id = 引用的声明 ID
  │
  └─ 5. 创建 DEFINED_IN 边
        RuleDefinition / MetricDeclaration → KnowledgeFragment
        source_file = YAML 文件路径
        offset_start/end = 声明在文件中的位置
```

---

## Markdown 文档提取

### 目的

从 Markdown 文档中提取标题结构、表格数据和代码块，构建文档知识图谱。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 文档结构信息丢失 | heading 提取产出层级结构 EntityInstance |
| 2 | 表格数据无法被检索 | table 提取产出结构化 EntityInstance |
| 3 | 代码块与文档的关联断裂 | code_block 提取产出关联边 |

### 提取节点类型

| 节点类型 | EntityInstance._fact_object | 提取规则 |
|----------|---------------------------|----------|
| document | doc:Document | 文件本身 |
| heading | doc:Heading | `#`, `##`, `###` 等 |
| table | doc:Table | `| ... |` 格式 |
| code_block | doc:CodeBlock | ` ``` ` 围栏代码块 |
| link | doc:Link | `[text](url)` 格式 |

### 提取边类型

| 边类型 | EdgeInstance.relation_name | 语义 |
|--------|--------------------------|------|
| contains | doc:contains | 文档包含标题/表格/代码块 |
| references | doc:references | 标题/文本引用链接 |

### Markdown 提取流程

```
输入: document.md
  │
  ├─ 1. 分片（参考 MemPalace chunk_text）
  │     CHUNK_SIZE = 800 字符
  │     CHUNK_OVERLAP = 100 字符
  │     优先段落边界切分
  │     → KnowledgeFragment[]
  │
  ├─ 2. 结构提取
  │     heading 正则: ^(#{1,6})\s+(.+)$
  │     table 检测: \|.*\| 模式
  │     code_block 检测: ``` 围栏
  │     → EntityInstance[] + EdgeInstance[]
  │
  └─ 3. 创建 EXTRACTED_FROM 边
        每个 EntityInstance → KnowledgeFragment
        offset_start/end = 元素在文档中的字符位置
```

### 参考项目对齐

| 参考项目 | 模式 | OntologyEngine 对齐 |
|----------|------|-------------------|
| MemPalace chunk_text | 800 字符块 + 100 字符 overlap + 段落边界优先 | 复用分片策略，产出 KnowledgeFragment |
| MemPalace detect_room | 文件路由到 room | 对应 domain_id 语义空间分配 |
| MemPalace file_already_mined | 检查文件是否已处理 | 对应增量缓存 check_ast_cache |

---

## EXTRACTED_FROM 边创建

### 目的

在 Pass 1 提取过程中，为每个提取的 EntityInstance 自动创建 EXTRACTED_FROM 互索引边，建立 Layer-S 实体到 Layer-R 碎片的溯源链接。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 实体来源不可追溯 | EXTRACTED_FROM 边指向原始 KnowledgeFragment，精确定位到段落级偏移 |
| 2 | 提取与互索引边创建脱节 | 在提取过程中同步创建，确保每个实体都有来源 |

### 边字段映射

| EXTRACTED_FROM 字段 | 填充来源 | 说明 |
|---------------------|----------|------|
| id | UUID5(namespace, entity_id + fragment_id) | 确定性 ID |
| from_id | EntityInstance.id | 提取出的实体 |
| to_id | KnowledgeFragment.id | 来源碎片 |
| source_file | 文件路径 | 来源文件 |
| offset_start | AST 节点 start_byte / 正则匹配位置 | 字符偏移起始 |
| offset_end | AST 节点 end_byte / 正则匹配位置 | 字符偏移终止 |
| confidence | 1.0 | AST 提取为确定性 |
| edge_text | "{entity_name} 从 {source_file} 第 {line} 行提取" | 自动生成 |
| created_at | 提取时间 | 边创建时间 |

### 参考项目对齐

| 参考项目 | 模式 | OntologyEngine 对齐 |
|----------|------|-------------------|
| Graphify source_location | "L{line}" 格式的源位置标注 | 扩展为 offset_start/end 字符级偏移，支持段落级溯源 |
| m_flow includes_chunk | Episode → ContentFragment 关联 | 泛化为 EntityInstance → KnowledgeFragment |
| Cognee DataPoint.source_content_hash | SHA256 溯源 | 在边级别复用，增加 offset 信息 |

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-AST-1 | tree-sitter 而非正则提取代码结构 | tree-sitter 产出精确的 AST，正则无法处理嵌套结构；Graphify 已验证此模式 |
| D-AST-2 | LanguageConfig 驱动而非硬编码 | 支持新语言只需添加配置，无需修改提取逻辑 |
| D-AST-3 | 代码节点 _fact_object 使用 "code:" 前缀 | 区分代码实体与业务实体，避免命名空间冲突 |
| D-AST-4 | YAML 解析使用 PyYAML 而非 tree-sitter | YAML 是结构化数据，PyYAML 直接产出 dict，无需 AST |
| D-AST-5 | Markdown 分片复用 MemPalace 策略 | 800 字符块 + 100 字符 overlap 已在垂直领域验证有效 |
| D-AST-6 | EXTRACTED_FROM 边在提取时同步创建 | 提取是创建溯源边的唯一可靠时机，延迟创建可能导致遗漏 |
