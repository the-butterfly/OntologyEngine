# 项目结构

> **状态**: 设计中  
> **级别**: L1 - 实现层  
> **目标读者**: 开发者、贡献者

## 目录结构

```
ontology-engine/                          # 项目根目录
├── Cargo.toml                           # Workspace 配置
├── README.md                            # 项目说明
├── LICENSE
├── .gitignore
│
├── crates/                              # Rust crates
│   ├── ont-engine/                      # 核心引擎 (lib)
│   ├── ont-storage/                     # 存储层 (lib)
│   ├── ont-schema/                      # Schema 管理 (lib)
│   ├── ont-query/                       # 查询引擎 (lib)
│   ├── ont-rules/                       # 规则引擎 (lib)
│   ├── ont-inference/                   # 推理引擎 (lib)
│   ├── ont-memory/                      # Memory 服务 (lib)
│   ├── ont-api/                         # API 服务 (bin + lib)
│   └── ont-cli/                         # 命令行工具 (bin)
│
├── proto/                               # Protocol Buffers 定义
│   ├── common.proto
│   ├── schema.proto
│   ├── query.proto
│   ├── rules.proto
│   └── memory.proto
│
├── schemas/                             # 默认 Schema 定义
│   ├── core/                            # 核心本体
│   │   ├── types.yaml
│   │   └── base.yaml
│   ├── finance/                         # 金融领域
│   │   └── counterparty.yaml
│   └── medical/                         # 医疗领域
│       └── patient.yaml
│
├── configs/                             # 配置文件
│   ├── development.yaml
│   ├── production.yaml
│   └── test.yaml
│
├── migrations/                          # 数据库迁移
│   ├── postgresql/
│   └── neo4j/
│
├── docker/                              # Docker 配置
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
│
├── docs/                                # 文档
│   ├── architecture/                    # 架构设计
│   ├── design/                          # 详细设计
│   ├── implementation/                  # 实现细节
│   ├── api/                             # API 文档
│   ├── development/                     # 开发计划
│   └── reference/                       # 参考资料
│
├── tests/                               # 集成测试
│   ├── integration/
│   ├── fixtures/
│   └── e2e/
│
├── benchmarks/                          # 性能测试
│   └── criterion/
│
├── scripts/                             # 工具脚本
│   ├── setup.sh
│   ├── test.sh
│   └── deploy.sh
│
└── .github/                             # CI/CD
    ├── workflows/
    │   ├── ci.yml
    │   ├── release.yml
    │   └── docs.yml
    └── CODEOWNERS
```

## Crate 划分

### 核心 Crate

```
┌─────────────────────────────────────────────────────────────────┐
│                        ont-api                                  │
│                    (Binary + Library)                           │
│                    HTTP/gRPC 服务入口                           │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  ont-schema   │     │  ont-query    │     │  ont-rules    │
│  Schema 管理  │     │  查询引擎     │     │  规则引擎     │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌───────────────┐
                    │  ont-storage  │
                    │  存储抽象层   │
                    └───────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌───────────┐  ┌───────────┐  ┌───────────┐
        │ GraphStore│  │VectorStore│  │  RDBMS    │
        └───────────┘  └───────────┘  └───────────┘
```

### Crate 依赖关系

```
ont-api
├── ont-schema
├── ont-query
├── ont-rules
├── ont-inference
├── ont-memory
└── ont-storage
    ├── ont-schema (dev)
    └── ont-common

ont-query
├── ont-schema
├── ont-storage
└── ont-common

ont-rules
├── ont-schema
├── ont-storage
└── ont-common

ont-inference
├── ont-rules
├── ont-schema
└── ont-common

ont-memory
├── ont-storage
└── ont-common

ont-schema
└── ont-common

ont-common
└── (无依赖，基础类型和工具)
```

## 各 Crate 职责

### `ont-common` - 公共基础

```rust
// crates/ont-common/src/lib.rs

pub mod error;        // 错误类型定义
pub mod types;        // 基础类型
pub mod utils;        // 工具函数
pub mod constants;    // 常量定义
```

### `ont-schema` - Schema 管理

```rust
// crates/ont-schema/src/lib.rs

pub mod schema;       // Schema 定义
pub mod concept;      // Concept 定义
pub mod relation;     // Relation 定义
pub mod attribute;    // Attribute 定义
pub mod types;        // 类型系统
pub mod validator;    // Schema 校验
pub mod registry;     // Schema 注册表
```

### `ont-storage` - 存储层

```rust
// crates/ont-storage/src/lib.rs

pub mod graph;        // 图存储接口
pub mod vector;       // 向量存储接口
pub mod relational;   // 关系型存储接口
pub mod cache;        // 缓存接口

// 具体实现
pub mod neo4j;        // Neo4j 实现
pub mod pgvector;     // pgvector 实现
pub mod postgres;     // PostgreSQL 实现
pub mod redis;        // Redis 实现
```

### `ont-query` - 查询引擎

```rust
// crates/ont-query/src/lib.rs

pub mod parser;       // 查询解析
pub mod optimizer;    // 查询优化
pub mod executor;     // 查询执行
pub mod planner;      // 执行计划
pub mod result;       // 结果处理
```

### `ont-rules` - 规则引擎

```rust
// crates/ont-rules/src/lib.rs

pub mod rule;         // 规则定义
pub mod operator;     // 算子定义
pub mod dependency;   // 依赖解析
pub mod executor;     // 规则执行
pub mod context;      // 执行上下文
```

### `ont-inference` - 推理引擎

```rust
// crates/ont-inference/src/lib.rs

pub mod symbolic;     // 符号推理
pub mod neural;       // 神经网络推理
pub mod hybrid;       // 混合推理
pub mod reasoner;     // 推理接口
```

### `ont-memory` - Memory 服务

```rust
// crates/ont-memory/src/lib.rs

pub mod memory;       // Memory 定义
pub mod store;        // 存储接口
pub mod retrieve;     // 检索接口
pub mod summarize;    // 摘要生成
```

### `ont-api` - API 服务

```rust
// crates/ont-api/src/lib.rs

pub mod rest;         // REST API
pub mod graphql;      // GraphQL API
pub mod grpc;         // gRPC 服务
pub mod middleware;   // 中间件
pub mod auth;         // 认证授权
```

### `ont-cli` - 命令行工具

```rust
// crates/ont-cli/src/main.rs

mod commands;
mod config;

use clap::Parser;

#[derive(Parser)]
#[command(name = "ont")]
#[command(about = "OntologyEngine CLI")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Schema 管理
    Schema {
        #[command(subcommand)]
        action: SchemaAction,
    },
    /// 数据导入
    Import {
        file: PathBuf,
    },
    /// 查询
    Query {
        query: String,
    },
    /// 服务管理
    Server {
        #[command(subcommand)]
        action: ServerAction,
    },
}
```

## Workspace 配置

```toml
# Cargo.toml
[workspace]
members = [
    "crates/ont-common",
    "crates/ont-schema",
    "crates/ont-storage",
    "crates/ont-query",
    "crates/ont-rules",
    "crates/ont-inference",
    "crates/ont-memory",
    "crates/ont-api",
    "crates/ont-cli",
]
resolver = "2"

[workspace.package]
version = "0.1.0"
edition = "2021"
license = "Apache-2.0"
repository = "https://github.com/example/ontology-engine"
rust-version = "1.75"

[workspace.dependencies]
# 公共依赖
ont-common = { path = "crates/ont-common" }
ont-schema = { path = "crates/ont-schema" }
ont-storage = { path = "crates/ont-storage" }
ont-query = { path = "crates/ont-query" }
ont-rules = { path = "crates/ont-rules" }
ont-inference = { path = "crates/ont-inference" }
ont-memory = { path = "crates/ont-memory" }

# 第三方依赖
tokio = { version = "1", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
thiserror = "1.0"
anyhow = "1.0"
tracing = "0.1"
```

## 各 Crate Cargo.toml 示例

### `crates/ont-common/Cargo.toml`

```toml
[package]
name = "ont-common"
version.workspace = true
edition.workspace = true
license.workspace = true

[dependencies]
serde = { workspace = true }
serde_json = { workspace = true }
thiserror = { workspace = true }
uuid = { version = "1.7", features = ["v4", "serde"] }
chrono = { version = "0.4", features = ["serde"] }
regex = "1.10"

[dev-dependencies]
pretty_assertions = "1.4"
```

### `crates/ont-api/Cargo.toml`

```toml
[package]
name = "ont-api"
version.workspace = true
edition.workspace = true
license.workspace = true

[[bin]]
name = "ont-api"
path = "src/main.rs"

[lib]
name = "ont_api"
path = "src/lib.rs"

[dependencies]
ont-common = { workspace = true }
ont-schema = { workspace = true }
ont-storage = { workspace = true }
ont-query = { workspace = true }
ont-rules = { workspace = true }
ont-inference = { workspace = true }
ont-memory = { workspace = true }

axum = "0.7"
tokio = { workspace = true }
tonic = "0.11"
serde = { workspace = true }
tracing = { workspace = true }
config = "0.14"

[dev-dependencies]
tokio-test = "0.4"
reqwest = { version = "0.12", features = ["json"] }
```

## 代码组织规范

### 目录结构规范

```
crates/ont-xxx/
├── Cargo.toml
├── README.md                    # Crate 说明
├── src/
│   ├── lib.rs                   # 库入口
│   ├── main.rs                  # 二进制入口 (可选)
│   ├── error.rs                 # 错误定义
│   ├── types.rs                 # 类型定义
│   ├── xxx/                     # 功能模块
│   │   ├── mod.rs
│   │   ├── xxx_impl.rs
│   │   └── xxx_test.rs
│   └── prelude.rs               # 常用导入
├── tests/                       # 集成测试
│   └── integration_test.rs
├── benches/                     # 性能测试
│   └── xxx_benchmark.rs
└── examples/                    # 示例代码
    └── basic_usage.rs
```

### 模块组织规范

```rust
// lib.rs 结构示例
#![deny(missing_docs)]
#![deny(unsafe_code)]

//! # ont-schema
//! 
//! Schema 管理模块，负责本体定义、校验和版本管理。

pub mod error;
pub mod types;

mod concept;
mod relation;
mod attribute;
mod validator;
mod registry;

pub use concept::{Concept, ConceptId};
pub use relation::{Relation, RelationId};
pub use attribute::{Attribute, AttributeId};
pub use validator::SchemaValidator;
pub use registry::SchemaRegistry;

/// 模块公共导入
pub mod prelude {
    pub use super::{Concept, Relation, Attribute};
    pub use super::types::*;
}
```

## 💬 待讨论问题

1. **Crate 粒度**: 当前的划分是否合适？是否需要合并或拆分？
2. **命名规范**: `ont-xxx` 的命名是否合适？是否有更好的命名方案？
3. **API 聚合**: `ont-api` 作为聚合 crate 是否合适？
4. **测试组织**: 集成测试放在 workspace 根还是各 crate？

## 下一步

- [Crate 设计](./crate-design.md) - 各 Crate 详细设计
- [核心数据结构](./data-structures.md) - 关键数据结构定义
