// ontology-engine-ui/src/pages/spaces/rulesEmbed.ts
//
// A2UI 规则管理模块统一导出
// ────────────────────────────────────────────────────────────────────────────
//
// 【用途】
//   1. 当前用于 SpaceDetailPage 嵌套路由（内嵌到管理面右侧内容区）
//   2. 未来 A2UI 可直接 import 这里的组件，作为独立卡片渲染到任意位置
//
// 【数据源】
//   所有规则管理组件使用 Schema L4 API：
//   - /v1/management/{spaceId}/schema/L4/rules/definitions
//   - /v1/management/{spaceId}/schema/L4/rules/logics
//   与 Schema 声明保持一致
//
// 【A2UI 接入方式】
//   import { RulesEmbedPage, RuleGroupDetailEmbedPage, RuleGroupCreateEmbedPage } from './rulesEmbed';
//
//   // 示例：A2UI 宿主直接传入 spaceId prop，不依赖路由上下文
//   <RulesEmbedPage spaceId="supply_chain_finance_v1" />
//   <RuleGroupDetailEmbedPage spaceId="supply_chain_finance_v1" groupId="RD001_basic_eligibility" />
//   <RuleGroupCreateEmbedPage spaceId="supply_chain_finance_v1" />
//
// 【扩展点说明】
//   - 每个组件根元素含 data-a2ui-component 属性，用于宿主识别和样式隔离
//   - 组件内部所有导航均通过 useNavigate()，A2UI 宿主需提供 Router 上下文
//     或替换为自定义 navigate prop（未来扩展）
// ────────────────────────────────────────────────────────────────────────────

export { RulesEmbedPage } from './RulesEmbedPage';
export type { RulesEmbedPageProps } from './RulesEmbedPage';

export { RuleGroupDetailEmbedPage } from './RuleGroupDetailEmbedPage';
export type { RuleGroupDetailEmbedPageProps } from './RuleGroupDetailEmbedPage';

export { RuleGroupCreateEmbedPage } from './RuleGroupCreateEmbedPage';
export type { RuleGroupCreateEmbedPageProps } from './RuleGroupCreateEmbedPage';

// 导出 L4 规则类型供外部使用
export type {
  L4RuleDefinition,
  L4RuleLogic,
  L4IOElement,
  L4Precondition,
  L4RuleGroupWithLogics,
} from '../../hooks/useL4Rules';
