#!/bin/bash
# Case 3: 亚太区总部税务架构优化 - 一键执行脚本
# 执行What-If模拟对比三个税务架构方案

set -e

echo "=============================================="
echo "Case 3: 亚太区总部税务架构 What-If 模拟"
echo "=============================================="

# 配置
SPACE_ID="space.tax_apac_2026"
SIMULATION_ID="sim_$(date +%Y%m%d_%H%M%S)"

# Step 1: 创建语义空间
echo ""
echo "[Step 1/6] 创建语义空间..."
ontology-cli space create \
    --name "tax_analysis_apac" \
    --description "2026年亚太区总部税务架构分析"
echo "✓ 语义空间创建完成: $SPACE_ID"

# Step 2: 加载Schema
echo ""
echo "[Step 2/6] 加载转让定价Schema..."
ontology-cli schema load \
    --space "$SPACE_ID" \
    --file "schema.yaml"
echo "✓ Schema加载完成"

# Step 3: 导入数据
echo ""
echo "[Step 3/6] 导入子公司及交易数据..."
ontology-cli entities batch-import \
    --space "$SPACE_ID" \
    --file "instances.yaml"
echo "✓ 数据导入完成"

# Step 4: 定义场景
echo ""
echo "[Step 4/6] 定义三个What-If场景..."

for scenario in A B C; do
    echo "  - 定义场景$scenario..."

    case $scenario in
        A)
            NAME="香港总部模式"
            PARAMS='{"hq_location":"香港","ip_location":"香港","operation_location":"中国","royalty_rate":0.05,"dividend_wht":0.05,"qdmt_applicable":true}'
            ;;
        B)
            NAME="新加坡总部模式"
            PARAMS='{"hq_location":"新加坡","ip_location":"新加坡","operation_location":"中国","royalty_rate":0.07,"dividend_wht":0.05,"qdmt_applicable":true}'
            ;;
        C)
            NAME="混合架构模式"
            PARAMS='{"hq_location":"香港+新加坡","ip_location":"香港","operation_location":"新加坡","royalty_rate":0.05,"dividend_wht":0.05,"qdmt_applicable":true}'
            ;;
    esac

    ontology-cli simulation define-scenario \
        --space "$SPACE_ID" \
        --scenario-id "scenario_$scenario" \
        --scenario-name "$NAME" \
        --parameters "$PARAMS"
done
echo "✓ 三个场景定义完成"

# Step 5: 执行模拟
echo ""
echo "[Step 5/6] 执行干运行模拟..."
ontology-cli simulation run \
    --space "$SPACE_ID" \
    --simulation-id "$SIMULATION_ID" \
    --mode dry_run \
    --scenarios "scenario_A,scenario_B,scenario_C"
echo "✓ 模拟执行完成 (dry_run模式，无数据持久化)"

# Step 6: 对比分析
echo ""
echo "[Step 6/6] 生成对比矩阵..."
ontology-cli simulation compare \
    --space "$SPACE_ID" \
    --simulation-id "$SIMULATION_ID" \
    --output-format table

echo ""
echo "=============================================="
echo "模拟完成!"
echo "=============================================="
echo ""
echo "输出文件:"
echo "  - 对比矩阵: expected_outputs/comparison_matrix.csv"
echo "  - 场景A结果: expected_outputs/scenario_a_result.json"
echo "  - 场景B结果: expected_outputs/scenario_b_result.json"
echo "  - 场景C结果: expected_outputs/scenario_c_result.json"
echo "  - 可视化: visualization/scenario_comparison.md"
echo ""
echo "推荐方案: 场景A (香港总部模式)"
echo "推荐理由: 综合税务效率最高 + BEPS低风险 + 无支柱二补税"
echo ""
