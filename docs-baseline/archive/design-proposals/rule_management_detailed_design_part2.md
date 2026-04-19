# 规则管理详细设计方案（续）

## 三、规则引擎核心实现

### 3.1 依赖解析与计算图构建

```python
# engine/dependency_resolver.py

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
import networkx as nx

@dataclass
class MetricNode:
    """指标节点"""
    id: str                          # 指标ID
    name: str                        # 指标名称
    source: str                      # input | rule | intermediate_metric
    source_rule_id: Optional[str]    # 如果来自规则，记录规则ID
    dependencies: List[str] = field(default_factory=list)
    
@dataclass  
class RuleNode:
    """规则节点"""
    id: str                          # 规则ID
    name: str
    priority: int
    inputs: List[MetricNode]
    outputs: List[str]
    compute_config: Dict
    
@dataclass
class ComputationGraph:
    """计算图（DAG）"""
    nodes: Dict[str, MetricNode]     # 所有指标节点
    edges: List[Tuple[str, str]]     # 依赖边
    execution_order: List[str]       # 拓扑排序后的执行顺序
    
class DependencyResolver:
    """
    依赖解析器
    
    职责：
    1. 解析规则之间的依赖关系
    2. 构建计算图（DAG）
    3. 检测循环依赖
    4. 生成执行顺序
    """
    
    def __init__(self):
        self.metrics: Dict[str, MetricNode] = {}
        self.rules: Dict[str, RuleNode] = {}
        self.graph = nx.DiGraph()
        
    def parse_rule_file(self, rule_file: Dict) -> ComputationGraph:
        """
        解析规则文件，构建计算图
        """
        # 1. 解析输入指标（原子指标）
        for input_name, input_config in rule_file.get("inputs", {}).items():
            self.metrics[input_name] = MetricNode(
                id=input_name,
                name=input_name,
                source="input",
                dependencies=[]
            )
            
        # 2. 解析中间指标
        for metric_name, metric_config in rule_file.get("intermediate_metrics", {}).items():
            deps = metric_config.get("dependencies", [])
            self.metrics[metric_name] = MetricNode(
                id=metric_name,
                name=metric_config.get("description", metric_name),
                source="intermediate_metric",
                dependencies=deps
            )
            
        # 3. 解析规则
        for rule_config in rule_file.get("rules", []):
            rule_id = rule_config["id"]
            
            # 解析规则输入
            rule_inputs = []
            for input_config in rule_config.get("inputs", []):
                input_name = input_config["name"]
                input_from = input_config["from"]
                
                if input_from == "rule":
                    # 来自其他规则的输出
                    source_rule_id = input_config["rule_id"]
                    rule_inputs.append(MetricNode(
                        id=input_name,
                        name=input_name,
                        source="rule",
                        source_rule_id=source_rule_id,
                        dependencies=[source_rule_id]
                    ))
                elif input_from == "input":
                    rule_inputs.append(self.metrics[input_name])
                elif input_from == "intermediate_metric":
                    rule_inputs.append(self.metrics[input_name])
                    
            # 解析规则输出
            rule_outputs = [o["name"] for o in rule_config.get("outputs", [])]
            
            # 注册规则
            self.rules[rule_id] = RuleNode(
                id=rule_id,
                name=rule_config.get("name", rule_id),
                priority=rule_config.get("priority", 50),
                inputs=rule_inputs,
                outputs=rule_outputs,
                compute_config=rule_config.get("compute", {})
            )
            
            # 注册规则输出的指标
            for output_name in rule_outputs:
                self.metrics[output_name] = MetricNode(
                    id=output_name,
                    name=output_name,
                    source="rule",
                    source_rule_id=rule_id,
                    dependencies=[rule_id]
                )
                
        # 4. 构建依赖图
        self._build_dependency_graph()
        
        # 5. 拓扑排序
        execution_order = self._topological_sort()
        
        return ComputationGraph(
            nodes=self.metrics,
            edges=list(self.graph.edges()),
            execution_order=execution_order
        )
        
    def _build_dependency_graph(self):
        """构建依赖图"""
        # 添加所有节点
        for metric_id in self.metrics:
            self.graph.add_node(metric_id)
            
        for rule_id in self.rules:
            self.graph.add_node(rule_id)
            
        # 添加边：规则 → 输出指标
        for rule_id, rule in self.rules.items():
            for output in rule.outputs:
                self.graph.add_edge(rule_id, output)
                
        # 添加边：输入指标 → 规则
        for rule_id, rule in self.rules.items():
            for input_metric in rule.inputs:
                if input_metric.source == "rule":
                    # 规则输出 → 规则输入
                    self.graph.add_edge(input_metric.source_rule_id, rule_id)
                else:
                    # 原子指标/中间指标 → 规则
                    self.graph.add_edge(input_metric.id, rule_id)
                    
        # 添加边：中间指标的依赖
        for metric_id, metric in self.metrics.items():
            if metric.source == "intermediate_metric":
                for dep in metric.dependencies:
                    self.graph.add_edge(dep, metric_id)
                    
    def _topological_sort(self) -> List[str]:
        """拓扑排序，返回执行顺序"""
        try:
            return list(nx.topological_sort(self.graph))
        except nx.NetworkXUnfeasible:
            # 检测到循环依赖
            cycles = list(nx.simple_cycles(self.graph))
            raise ValueError(f"检测到循环依赖: {cycles}")
            
    def get_required_inputs(self, target_metrics: List[str]) -> Set[str]:
        """
        获取计算目标指标所需的所有原子输入
        """
        required = set()
        
        for target in target_metrics:
            # 反向遍历依赖图，找到所有 source="input" 的节点
            predecessors = nx.ancestors(self.graph, target)
            for pred in predecessors:
                if pred in self.metrics and self.metrics[pred].source == "input":
                    required.add(pred)
                    
        return required
        
    def visualize(self, output_path: str):
        """可视化计算图"""
        import matplotlib.pyplot as plt
        
        pos = nx.spring_layout(self.graph)
        nx.draw(self.graph, pos, with_labels=True, node_size=2000, 
                node_color="lightblue", font_size=8, arrows=True)
        plt.savefig(output_path)
        plt.close()
```

### 3.2 规则执行引擎

```python
# engine/rule_executor.py

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import time
import json

@dataclass
class ExecutionContext:
    """执行上下文"""
    entity_id: str
    as_of_date: datetime
    inputs: Dict[str, Any]           # 原子输入
    computed: Dict[str, Any]         # 已计算结果
    trace: List[Dict]                # 执行追踪
    errors: List[Dict]               # 错误记录
    
@dataclass
class ExecutionResult:
    """执行结果"""
    entity_id: str
    outputs: Dict[str, Any]          # 所有输出指标
    execution_time_ms: float
    trace: List[Dict]
    errors: List[Dict]
    
class RuleExecutor:
    """
    规则执行器
    
    职责：
    1. 按依赖顺序执行规则
    2. 管理计算上下文
    3. 调用算子执行计算
    4. 记录完整执行轨迹
    """
    
    def __init__(self, computation_graph: ComputationGraph, 
                 rule_registry: Dict, operator_registry: Dict):
        self.graph = computation_graph
        self.rule_registry = rule_registry
        self.operator_registry = operator_registry
        
    def execute(self, entity_id: str, inputs: Dict[str, Any],
                as_of_date: datetime = None) -> ExecutionResult:
        """
        执行完整的规则链
        
        Args:
            entity_id: 实体ID
            inputs: 原子输入 {指标名: 值}
            as_of_date: 计算时点
            
        Returns:
            ExecutionResult: 包含所有计算结果
        """
        start_time = time.time()
        
        # 初始化上下文
        context = ExecutionContext(
            entity_id=entity_id,
            as_of_date=as_of_date or datetime.now(),
            inputs=inputs,
            computed=dict(inputs),  # 已计算结果初始化为输入
            trace=[],
            errors=[]
        )
        
        # 按拓扑顺序执行
        for node_id in self.graph.execution_order:
            # 跳过已计算的指标（输入）
            if node_id in context.computed:
                continue
                
            # 检查是否是规则节点
            if node_id in self.rule_registry:
                self._execute_rule(node_id, context)
                
            # 检查是否是中间指标
            elif node_id in self.graph.nodes:
                node = self.graph.nodes[node_id]
                if node.source == "intermediate_metric":
                    self._compute_intermediate_metric(node_id, context)
                    
        execution_time = (time.time() - start_time) * 1000
        
        return ExecutionResult(
            entity_id=entity_id,
            outputs=context.computed,
            execution_time_ms=execution_time,
            trace=context.trace,
            errors=context.errors
        )
        
    def _execute_rule(self, rule_id: str, context: ExecutionContext):
        """执行单条规则"""
        rule = self.rule_registry[rule_id]
        
        # 记录执行开始
        trace_entry = {
            "type": "rule",
            "rule_id": rule_id,
            "rule_name": rule["name"],
            "start_time": datetime.now().isoformat(),
            "inputs": {}
        }
        
        try:
            # 1. 收集输入
            rule_inputs = {}
            for input_config in rule.get("inputs", []):
                input_name = input_config["name"]
                
                if input_name in context.computed:
                    rule_inputs[input_name] = context.computed[input_name]
                elif input_config.get("required", True):
                    # 缺少必填输入
                    if "default" in input_config:
                        rule_inputs[input_name] = input_config["default"]
                    else:
                        raise ValueError(f"缺少必填输入: {input_name}")
                else:
                    rule_inputs[input_name] = input_config.get("default")
                    
            trace_entry["inputs"] = rule_inputs
            
            # 2. 执行计算
            compute_config = rule["compute"]
            result = self._execute_compute(compute_config, rule_inputs, context)
            
            # 3. 写入输出
            outputs = rule.get("outputs", [])
            if isinstance(result, dict):
                for output_config in outputs:
                    output_name = output_config["name"]
                    if output_name in result:
                        context.computed[output_name] = result[output_name]
            else:
                # 单一输出
                if outputs:
                    context.computed[outputs[0]["name"]] = result
                    
            trace_entry["outputs"] = {o["name"]: context.computed.get(o["name"]) for o in outputs}
            trace_entry["status"] = "success"
            
        except Exception as e:
            trace_entry["status"] = "error"
            trace_entry["error"] = str(e)
            context.errors.append({
                "rule_id": rule_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            
            # 异常处理
            self._handle_error(rule, e, context)
            
        finally:
            trace_entry["end_time"] = datetime.now().isoformat()
            context.trace.append(trace_entry)
            
    def _execute_compute(self, compute_config: Dict, 
                        inputs: Dict, context: ExecutionContext) -> Any:
        """
        执行计算配置
        
        支持：
        1. 单一算子调用
        2. 嵌套算子组合
        3. 变量引用 ${var}
        """
        operator_name = compute_config["operator"]
        parameters = compute_config.get("parameters", {})
        
        # 解析参数（处理变量引用和嵌套算子）
        resolved_params = self._resolve_parameters(parameters, inputs, context)
        
        # 获取算子
        operator = self.operator_registry.get(operator_name)
        if not operator:
            raise ValueError(f"未知算子: {operator_name}")
            
        # 执行算子
        return operator.execute(resolved_params, context)
        
    def _resolve_parameters(self, params: Any, inputs: Dict, 
                           context: ExecutionContext) -> Any:
        """
        解析参数值
        
        支持：
        1. 字面值: 100, "string", true
        2. 变量引用: "${variable_name}"
        3. 嵌套算子: {"operator": "ADD", "parameters": {...}}
        4. 列表和字典
        """
        if isinstance(params, str):
            # 变量引用
            if params.startswith("${") and params.endswith("}"):
                var_name = params[2:-1]
                if var_name in context.computed:
                    return context.computed[var_name]
                elif var_name in inputs:
                    return inputs[var_name]
                else:
                    raise ValueError(f"未定义的变量: {var_name}")
            return params
            
        elif isinstance(params, dict):
            # 嵌套算子
            if "operator" in params:
                return self._execute_compute(params, inputs, context)
            # 字典，递归处理
            return {k: self._resolve_parameters(v, inputs, context) 
                    for k, v in params.items()}
                    
        elif isinstance(params, list):
            # 列表，递归处理
            return [self._resolve_parameters(item, inputs, context) 
                    for item in params]
            
        else:
            # 字面值
            return params
            
    def _compute_intermediate_metric(self, metric_id: str, 
                                     context: ExecutionContext):
        """计算中间指标"""
        metric = self.graph.nodes[metric_id]
        formula = metric.get("formula")
        
        # 简单公式求值
        # TODO: 使用更安全的表达式引擎
        result = self._evaluate_formula(formula, context.computed)
        context.computed[metric_id] = result
        
    def _handle_error(self, rule: Dict, error: Exception, 
                     context: ExecutionContext):
        """错误处理"""
        error_config = rule.get("on_error", {})
        
        # 根据错误类型查找处理策略
        error_type = type(error).__name__
        handling = error_config.get(error_type, error_config.get("default", {}))
        
        action = handling.get("action", "skip")
        
        if action == "return_default":
            default_value = handling.get("value")
            for output in rule.get("outputs", []):
                context.computed[output["name"]] = default_value
                
        elif action == "fallback":
            fallback_value = handling.get("fallback_value")
            if isinstance(fallback_value, dict):
                context.computed.update(fallback_value)
```

### 3.3 算子注册与执行

```python
# engine/operators.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import requests

class BaseOperator(ABC):
    """算子基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """算子名称"""
        pass
        
    @property
    @abstractmethod
    def category(self) -> str:
        """算子类别"""
        pass
        
    @abstractmethod
    def execute(self, params: Dict[str, Any], context) -> Any:
        """执行计算"""
        pass
        
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """参数验证"""
        return True


# ========== 数学算子 ==========

class AddOperator(BaseOperator):
    name = "ADD"
    category = "math"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        operands = params["operands"]
        return sum(operands)


class SubOperator(BaseOperator):
    name = "SUB"
    category = "math"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        return params["minuend"] - params["subtrahend"]


class MulOperator(BaseOperator):
    name = "MUL"
    category = "math"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        result = 1
        for factor in params["factors"]:
            result *= factor
        return result


class DivOperator(BaseOperator):
    name = "DIV"
    category = "math"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        dividend = params["dividend"]
        divisor = params["divisor"]
        
        if divisor == 0:
            raise ZeroDivisionError("除数不能为0")
            
        return dividend / divisor


class SumOperator(BaseOperator):
    name = "SUM"
    category = "math"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        return sum(params["values"])


class AvgOperator(BaseOperator):
    name = "AVG"
    category = "math"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        values = params["values"]
        return sum(values) / len(values) if values else 0


class MaxOperator(BaseOperator):
    name = "MAX"
    category = "math"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        return max(params["values"])


class MinOperator(BaseOperator):
    name = "MIN"
    category = "math"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        return min(params["values"])


# ========== 逻辑算子 ==========

class IfOperator(BaseOperator):
    name = "IF"
    category = "logic"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        condition = params["condition"]
        then_value = params["then_value"]
        else_value = params["else_value"]
        
        return then_value if condition else else_value


class SwitchOperator(BaseOperator):
    name = "SWITCH"
    category = "logic"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        value = params["value"]
        cases = params["cases"]
        default = params.get("default")
        
        for case in cases:
            if case.get("condition", False):
                return case["output"]
                
        return default


class AndOperator(BaseOperator):
    name = "AND"
    category = "logic"
    
    def execute(self, params: Dict[str, Any], context) -> bool:
        return all(params["conditions"])


class OrOperator(BaseOperator):
    name = "OR"
    category = "logic"
    
    def execute(self, params: Dict[str, Any], context) -> bool:
        return any(params["conditions"])


class NotOperator(BaseOperator):
    name = "NOT"
    category = "logic"
    
    def execute(self, params: Dict[str, Any], context) -> bool:
        return not params["condition"]


# ========== 比较算子 ==========

class GtOperator(BaseOperator):
    name = "GT"
    category = "comparison"
    
    def execute(self, params: Dict[str, Any], context) -> bool:
        return params["left"] > params["right"]


class GteOperator(BaseOperator):
    name = "GTE"
    category = "comparison"
    
    def execute(self, params: Dict[str, Any], context) -> bool:
        return params["left"] >= params["right"]


class LtOperator(BaseOperator):
    name = "LT"
    category = "comparison"
    
    def execute(self, params: Dict[str, Any], context) -> bool:
        return params["left"] < params["right"]


class LteOperator(BaseOperator):
    name = "LTE"
    category = "comparison"
    
    def execute(self, params: Dict[str, Any], context) -> bool:
        return params["left"] <= params["right"]


class EqOperator(BaseOperator):
    name = "EQ"
    category = "comparison"
    
    def execute(self, params: Dict[str, Any], context) -> bool:
        return params["left"] == params["right"]


class InOperator(BaseOperator):
    name = "IN"
    category = "comparison"
    
    def execute(self, params: Dict[str, Any], context) -> bool:
        return params["value"] in params["collection"]


# ========== 评分卡算子 ==========

class ScorecardOperator(BaseOperator):
    name = "SCORECARD"
    category = "scoring"
    
    def __init__(self, scorecard_config_loader):
        self.config_loader = scorecard_config_loader
        
    def execute(self, params: Dict[str, Any], context) -> Any:
        scorecard_id = params["scorecard_id"]
        features = params["features"]
        version = params.get("version", "latest")
        
        # 加载评分卡配置
        config = self.config_loader.load(scorecard_id, version)
        
        # 计算分数
        total_score = config["base_score"]
        
        for feature_name, feature_value in features.items():
            if feature_name in config["features"]:
                feature_config = config["features"][feature_name]
                score = self._compute_feature_score(feature_value, feature_config)
                total_score += score
                
        return total_score
        
    def _compute_feature_score(self, value: Any, config: Dict) -> float:
        """计算单个特征分数"""
        bins = config.get("bins", [])
        
        for bin_config in bins:
            if "min" in bin_config and "max" in bin_config:
                if bin_config["min"] <= value < bin_config["max"]:
                    return bin_config["score"]
            elif "value" in bin_config:
                if value == bin_config["value"]:
                    return bin_config["score"]
                    
        return config.get("default_score", 0)


class BinningOperator(BaseOperator):
    name = "BINNING"
    category = "scoring"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        value = params["value"]
        bins = params["bins"]
        scores = params["scores"]
        
        for i, (lower, upper) in enumerate(bins):
            if lower <= value < upper:
                return scores[i]
                
        return scores[-1] if scores else 0


# ========== 规则链算子 ==========

class RuleChainOperator(BaseOperator):
    name = "RULE_CHAIN"
    category = "decision"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        rules = params["rules"]
        mode = params.get("mode", "first_match")
        
        if mode == "first_match":
            for rule in rules:
                if rule.get("condition", True):
                    return rule.get("output")
                    
        elif mode == "all_match":
            outputs = []
            for rule in rules:
                if rule.get("condition", True):
                    outputs.append(rule.get("output"))
            return outputs
            
        return None


# ========== 外部模型算子 ==========

class MlModelOperator(BaseOperator):
    name = "ML_MODEL"
    category = "external"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        endpoint = params["endpoint"]
        model_id = params["model_id"]
        model_version = params.get("model_version", "latest")
        features = params["features"]
        timeout = params.get("timeout", 30000)
        
        # 调用外部模型API
        try:
            response = requests.post(
                endpoint,
                json={
                    "model_id": model_id,
                    "model_version": model_version,
                    "features": features
                },
                timeout=timeout / 1000
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            raise TimeoutError(f"模型调用超时: {model_id}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"模型调用失败: {str(e)}")


class ExternalApiOperator(BaseOperator):
    name = "EXTERNAL_API"
    category = "external"
    
    def execute(self, params: Dict[str, Any], context) -> Any:
        endpoint = params["endpoint"]
        method = params.get("method", "GET")
        headers = params.get("headers", {})
        body = params.get("body")
        timeout = params.get("timeout", 30000)
        
        try:
            if method == "GET":
                response = requests.get(endpoint, headers=headers, timeout=timeout/1000)
            else:
                response = requests.post(endpoint, json=body, headers=headers, timeout=timeout/1000)
                
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            raise RuntimeError(f"API调用失败: {str(e)}")


# ========== 图计算算子 ==========

class GraphTraverseOperator(BaseOperator):
    name = "GRAPH_TRAVERSE"
    category = "graph"
    
    def __init__(self, graph_db):
        self.graph_db = graph_db
        
    def execute(self, params: Dict[str, Any], context) -> Any:
        start_node = params["start_node"]
        edge_type = params["edge_type"]
        direction = params.get("direction", "out")
        max_depth = params.get("max_depth", 5)
        
        # 执行图遍历
        cypher = f"""
        MATCH path = (start {{entityId: $start_node}})-[{direction}*1..{max_depth}]-(end)
        WHERE ALL(r IN relationships(path) WHERE type(r) = $edge_type)
        RETURN nodes(path), relationships(path)
        """
        
        result = self.graph_db.run(cypher, {
            "start_node": start_node,
            "edge_type": edge_type
        })
        
        return result


class GraphCentralityOperator(BaseOperator):
    name = "GRAPH_CENTRALITY"
    category = "graph"
    
    def __init__(self, graph_db):
        self.graph_db = graph_db
        
    def execute(self, params: Dict[str, Any], context) -> Any:
        node_id = params["node_id"]
        algorithm = params["algorithm"]
        
        if algorithm == "pagerank":
            # 使用图算法库计算PageRank
            cypher = """
            CALL algo.pageRank(null, null, {write: false})
            YIELD nodes, scores
            MATCH (n {entityId: $node_id})
            RETURN scores[n] AS score
            """
        elif algorithm == "degree":
            cypher = """
            MATCH (n {entityId: $node_id})-[r]-()
            RETURN COUNT(r) AS score
            """
        else:
            raise ValueError(f"不支持的中心性算法: {algorithm}")
            
        result = self.graph_db.run(cypher, {"node_id": node_id})
        return result[0]["score"] if result else 0


# ========== 算子注册表 ==========

class OperatorRegistry:
    """算子注册表"""
    
    def __init__(self, graph_db=None, config_loader=None):
        self.operators: Dict[str, BaseOperator] = {}
        
        # 注册内置算子
        self._register_builtin_operators()
        
        # 注册需要依赖的算子
        if graph_db:
            self.register(GraphTraverseOperator(graph_db))
            self.register(GraphCentralityOperator(graph_db))
            
        if config_loader:
            self.register(ScorecardOperator(config_loader))
            
    def _register_builtin_operators(self):
        """注册内置算子"""
        # 数学算子
        self.register(AddOperator())
        self.register(SubOperator())
        self.register(MulOperator())
        self.register(DivOperator())
        self.register(SumOperator())
        self.register(AvgOperator())
        self.register(MaxOperator())
        self.register(MinOperator())
        
        # 逻辑算子
        self.register(IfOperator())
        self.register(SwitchOperator())
        self.register(AndOperator())
        self.register(OrOperator())
        self.register(NotOperator())
        
        # 比较算子
        self.register(GtOperator())
        self.register(GteOperator())
        self.register(LtOperator())
        self.register(LteOperator())
        self.register(EqOperator())
        self.register(InOperator())
        
        # 决策算子
        self.register(RuleChainOperator())
        
        # 外部算子
        self.register(MlModelOperator())
        self.register(ExternalApiOperator())
        
    def register(self, operator: BaseOperator):
        """注册算子"""
        self.operators[operator.name] = operator
        
    def get(self, name: str) -> BaseOperator:
        """获取算子"""
        return self.operators.get(name)
        
    def list_operators(self, category: str = None) -> List[str]:
        """列出算子"""
        if category:
            return [op.name for op in self.operators.values() 
                    if op.category == category]
        return list(self.operators.keys())
```

### 3.4 完整执行流程示例

```python
# example_usage.py

from datetime import datetime

def main():
    # 1. 加载规则文件
    rule_file = load_yaml("rules/counterparty_risk_rules.yaml")
    
    # 2. 构建依赖解析器
    resolver = DependencyResolver()
    computation_graph = resolver.parse_rule_file(rule_file)
    
    # 3. 初始化算子注册表
    graph_db = Neo4jConnection("bolt://localhost:7687")
    config_loader = ScorecardConfigLoader("configs/scorecards/")
    operator_registry = OperatorRegistry(graph_db, config_loader)
    
    # 4. 创建规则执行器
    executor = RuleExecutor(
        computation_graph=computation_graph,
        rule_registry={r["id"]: r for r in rule_file["rules"]},
        operator_registry=operator_registry
    )
    
    # 5. 准备输入数据
    inputs = {
        "entity_id": "CP_2024_001",
        "legal_name": "某证券有限责任公司",
        "institution_type": "securities",
        "status": "active",
        "net_asset": 5000000000,
        "total_asset": 80000000000,
        "registered_capital": 3000000000,
        "capital_adequacy_ratio": 0.128,
        "total_guarantee_out": 2000000000,
        "total_guarantee_in": 500000000,
        "guarantee_chain_depth": 3,
        "transaction_count_90d": 1523,
        "transaction_amount_90d": 45000000000,
        "high_risk_counterparty_count": 2,
        "negative_news_count_30d": 1,
        "negative_news_sentiment_score": -0.3
    }
    
    # 6. 执行规则
    result = executor.execute(
        entity_id="CP_2024_001",
        inputs=inputs,
        as_of_date=datetime.now()
    )
    
    # 7. 输出结果
    print("=" * 60)
    print("执行结果:")
    print("=" * 60)
    print(f"实体ID: {result.entity_id}")
    print(f"执行时间: {result.execution_time_ms:.2f}ms")
    print()
    
    print("输出指标:")
    for key, value in result.outputs.items():
        print(f"  {key}: {value}")
        
    print()
    print("执行追踪:")
    for trace in result.trace:
        print(f"  [{trace['status']}] {trace['rule_name']}")
        
    if result.errors:
        print()
        print("错误信息:")
        for error in result.errors:
            print(f"  {error}")
            
if __name__ == "__main__":
    main()
```

**输出示例：**

```
============================================================
执行结果:
============================================================
实体ID: CP_2024_001
执行时间: 156.32ms

输出指标:
  entity_id: CP_2024_001
  legal_name: 某证券有限责任公司
  net_asset: 5000000000
  guarantee_ratio: 0.4
  capital_score: 85.0
  guarantee_score: 60.0
  trading_score: 65.0
  reputation_score: 73.0
  risk_score: 70.75
  risk_grade: B
  cooperation_strategy: maintain
  alert_level: none
  alert_messages: []

执行追踪:
  [success] 担保比例计算
  [success] 资本充足度评分
  [success] 担保风险评分
  [success] 交易稳定性评分
  [success] 声誉风险评分
  [success] 综合风险评分
  [success] 风险等级判定
  [success] 预警生成
```

---

## 四、与知识图谱的集成点

### 4.1 数据输入集成

```python
# integration/kg_data_input.py

class KnowledgeGraphDataInput:
    """
    从知识图谱获取原子指标
    """
    
    def __init__(self, graph_db):
        self.graph_db = graph_db
        
    def fetch_entity_data(self, entity_id: str, 
                         required_inputs: List[str]) -> Dict[str, Any]:
        """
        从图谱获取实体数据作为规则输入
        """
        # 构建查询，一次性获取所有需要的属性
        cypher = """
        MATCH (cp:Counterparty {entityId: $entity_id})
        RETURN cp
        """
        
        result = self.graph_db.run(cypher, {"entity_id": entity_id})
        
        if not result:
            raise ValueError(f"实体不存在: {entity_id}")
            
        entity_data = result[0]["cp"]
        
        # 映射到输入格式
        inputs = {}
        for input_name in required_inputs:
            if input_name in entity_data:
                inputs[input_name] = entity_data[input_name]
                
        return inputs
        
    def fetch_relation_data(self, entity_id: str, 
                           relation_type: str) -> List[Dict]:
        """
        从图谱获取关系数据
        """
        cypher = f"""
        MATCH (cp:Counterparty {{entityId: $entity_id}})-[r:{relation_type}]-(related)
        RETURN r, related
        """
        
        result = self.graph_db.run(cypher, {"entity_id": entity_id})
        return result
```

### 4.2 结果写回集成

```python
# integration/kg_result_output.py

class KnowledgeGraphResultOutput:
    """
    将规则计算结果写回知识图谱
    """
    
    def __init__(self, graph_db):
        self.graph_db = graph_db
        
    def write_results(self, entity_id: str, results: Dict[str, Any],
                     computation_trace: Dict):
        """
        将结果写回图谱
        
        策略：
        1. 作为节点属性
        2. 创建独立的计算结果节点
        3. 维护历史版本
        """
        cypher = """
        MATCH (cp:Counterparty {entityId: $entity_id})
        
        // 更新节点属性
        SET cp.risk_grade = $risk_grade,
            cp.risk_score = $risk_score,
            cp.capital_score = $capital_score,
            cp.guarantee_score = $guarantee_score,
            cp.trading_score = $trading_score,
            cp.reputation_score = $reputation_score,
            cp.cooperation_strategy = $cooperation_strategy,
            cp.alert_level = $alert_level,
            cp.last_evaluated_at = datetime(),
            cp.evaluation_version = '2.1.0'
            
        // 创建计算结果节点（用于历史追溯）
        CREATE (eval:Evaluation {
            evaluated_at: datetime(),
            risk_grade: $risk_grade,
            risk_score: $risk_score,
            computation_trace: $trace
        })
        CREATE (cp)-[:HAS_EVALUATION]->(eval)
        """
        
        self.graph_db.run(cypher, {
            "entity_id": entity_id,
            "risk_grade": results.get("risk_grade"),
            "risk_score": results.get("risk_score"),
            "capital_score": results.get("capital_score"),
            "guarantee_score": results.get("guarantee_score"),
            "trading_score": results.get("trading_score"),
            "reputation_score": results.get("reputation_score"),
            "cooperation_strategy": results.get("cooperation_strategy"),
            "alert_level": results.get("alert_level"),
            "trace": json.dumps(computation_trace)
        })
```

---

## 五、管理界面API设计

### 5.1 规则管理API

```python
# api/rule_management_api.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any, Optional

app = FastAPI(title="规则管理API")

# ========== 数据模型 ==========

class RuleFileUpload(BaseModel):
    namespace: str
    content: Dict[str, Any]  # YAML解析后的JSON
    
class ExecutionRequest(BaseModel):
    entity_id: str
    inputs: Dict[str, Any]
    as_of_date: Optional[str] = None
    target_outputs: Optional[List[str]] = None  # 只计算特定输出
    
class ExecutionResponse(BaseModel):
    entity_id: str
    outputs: Dict[str, Any]
    execution_time_ms: float
    trace: List[Dict]
    errors: List[Dict]

# ========== 规则管理 ==========

@app.post("/rules/upload")
async def upload_rule_file(request: RuleFileUpload):
    """
    上传规则文件
    """
    # 1. 验证Schema
    validator = RuleSchemaValidator()
    validation_result = validator.validate(request.content)
    
    if not validation_result.valid:
        raise HTTPException(400, validation_result.errors)
        
    # 2. 构建计算图
    resolver = DependencyResolver()
    computation_graph = resolver.parse_rule_file(request.content)
    
    # 3. 检测循环依赖
    if computation_graph.has_cycle:
        raise HTTPException(400, "检测到循环依赖")
        
    # 4. 存储规则文件
    rule_store.save(request.namespace, request.content)
    
    return {
        "status": "success",
        "namespace": request.namespace,
        "rules_count": len(request.content.get("rules", [])),
        "computation_graph_nodes": len(computation_graph.nodes)
    }

@app.get("/rules/{namespace}")
async def get_rule_file(namespace: str):
    """获取规则文件"""
    rule_file = rule_store.get(namespace)
    if not rule_file:
        raise HTTPException(404, "规则文件不存在")
    return rule_file

@app.get("/rules/{namespace}/graph")
async def get_computation_graph(namespace: str):
    """获取计算图可视化数据"""
    rule_file = rule_store.get(namespace)
    resolver = DependencyResolver()
    graph = resolver.parse_rule_file(rule_file)
    
    return {
        "nodes": [{"id": n, "type": graph.nodes[n].source} for n in graph.nodes],
        "edges": [{"from": e[0], "to": e[1]} for e in graph.edges],
        "execution_order": graph.execution_order
    }

@app.get("/rules/{namespace}/required_inputs")
async def get_required_inputs(namespace: str, target_outputs: List[str] = None):
    """获取计算目标输出所需的所有输入"""
    rule_file = rule_store.get(namespace)
    resolver = DependencyResolver()
    graph = resolver.parse_rule_file(rule_file)
    
    targets = target_outputs or list(rule_file.get("outputs", {}).keys())
    required = resolver.get_required_inputs(targets)
    
    return {
        "target_outputs": targets,
        "required_inputs": list(required)
    }

# ========== 规则执行 ==========

@app.post("/rules/{namespace}/execute", response_model=ExecutionResponse)
async def execute_rules(namespace: str, request: ExecutionRequest):
    """
    执行规则
    
    输入原子指标 → 输出全量结果
    """
    # 1. 加载规则
    rule_file = rule_store.get(namespace)
    if not rule_file:
        raise HTTPException(404, "规则文件不存在")
        
    # 2. 验证输入
    resolver = DependencyResolver()
    graph = resolver.parse_rule_file(rule_file)
    
    if request.target_outputs:
        required = resolver.get_required_inputs(request.target_outputs)
    else:
        required = set(rule_file.get("inputs", {}).keys())
        
    missing = required - set(request.inputs.keys())
    if missing:
        raise HTTPException(400, f"缺少必填输入: {missing}")
        
    # 3. 执行
    executor = RuleExecutor(
        computation_graph=graph,
        rule_registry={r["id"]: r for r in rule_file.get("rules", [])},
        operator_registry=operator_registry
    )
    
    result = executor.execute(
        entity_id=request.entity_id,
        inputs=request.inputs,
        as_of_date=request.as_of_date
    )
    
    return ExecutionResponse(
        entity_id=result.entity_id,
        outputs=result.outputs,
        execution_time_ms=result.execution_time_ms,
        trace=result.trace,
        errors=result.errors
    )

# ========== 算子管理 ==========

@app.get("/operators")
async def list_operators(category: str = None):
    """列出所有注册的算子"""
    return {
        "operators": [
            {
                "name": op.name,
                "category": op.category,
                "description": op.__doc__
            }
            for op in operator_registry.operators.values()
            if category is None or op.category == category
        ]
    }

@app.post("/operators/register")
async def register_custom_operator(operator_config: Dict[str, Any]):
    """注册自定义算子（外部API类型）"""
    # 验证配置
    # 存储配置
    # 动态注册
    return {"status": "success"}

# ========== 执行历史 ==========

@app.get("/execution-history/{entity_id}")
async def get_execution_history(entity_id: str, limit: int = 10):
    """获取实体的执行历史"""
    history = execution_history_store.get(entity_id, limit)
    return {"entity_id": entity_id, "history": history}

@app.get("/execution-trace/{execution_id}")
async def get_execution_trace(execution_id: str):
    """获取单次执行的详细追踪"""
    trace = execution_trace_store.get(execution_id)
    return trace
```

---

## 六、总结

### 核心设计要点

| 设计点 | 解决方案 |
|--------|----------|
| **声明式定义** | YAML Schema，无代码配置 |
| **依赖解析** | 自动构建DAG，拓扑排序 |
| **算子复用** | 内置算子库 + 外部注册 |
| **规则组合** | 输入输出变量连接 |
| **执行追踪** | 完整轨迹，可审计 |
| **异常处理** | 多级fallback策略 |

### 执行流程

```
输入原子指标 → 依赖解析 → 拓扑排序 → 逐层执行 → 输出全量结果
     ↓              ↓           ↓           ↓            ↓
  key:value      构建DAG    确定顺序    调用算子     所有指标
```

### 与知识图谱集成

1. **输入层** - 从图谱实体属性获取原子指标
2. **计算层** - 图算子调用图数据库能力
3. **输出层** - 结果写回图谱节点/关系
4. **追溯层** - 计算历史与知识图谱关联
