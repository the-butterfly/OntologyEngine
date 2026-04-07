#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
供应链金融授信评估 MVP 演示

演示完整链路：
分析对象(Supplier) -> 分析维度/场景(credit_assessment) -> 分析逻辑(指标计算+规则推理)

场景：
- 案例1：优质供应商（深圳智造科技）- 预期：正常授信
- 案例2：高风险供应商（某贸易公司）- 预期：拒绝授信  
- 案例3：担保圈供应商（供应商A/B/C）- 预期：担保圈预警
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, date
from enum import Enum
import json


# ============================================================
# 数据模型定义
# ============================================================

class RiskLevel(Enum):
    LOW = "低风险"
    MEDIUM = "中风险"
    HIGH = "高风险"


class CreditGrade(Enum):
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"
    CC = "CC"
    C = "C"
    D = "D"


@dataclass
class Money:
    value: float
    currency: str = "CNY"
    
    def __str__(self):
        return f"{self.currency} {self.value:,.2f}"


@dataclass
class Supplier:
    """分析对象：供应商"""
    supplier_id: str
    company_name: str
    unified_credit_code: str
    registered_capital: Money
    establishment_date: date
    industry_type: str
    company_size: str
    status: str
    
    # 原子指标（输入）
    total_invoice_amount_90d: Money = None
    invoice_count_90d: int = 0
    overdue_invoice_amount: Money = None
    total_contract_amount: Money = None
    avg_monthly_tax_revenue: Money = None
    tax_compliance_score: int = 0
    negative_news_count_90d: int = 0
    core_enterprise_count: int = 0
    
    # 关联数据
    invoices: List[Dict] = field(default_factory=list)
    contracts: List[Dict] = field(default_factory=list)
    guarantee_chain_depth: int = 0
    has_guarantee_circle: bool = False
    
    # 分析维度
    active_dimensions: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.total_invoice_amount_90d is None:
            self.total_invoice_amount_90d = Money(0)
        if self.overdue_invoice_amount is None:
            self.overdue_invoice_amount = Money(0)
        if self.total_contract_amount is None:
            self.total_contract_amount = Money(0)
        if self.avg_monthly_tax_revenue is None:
            self.avg_monthly_tax_revenue = Money(0)


@dataclass
class AnalysisContext:
    """分析上下文"""
    supplier: Supplier
    dimension: str  # 分析维度：如 "credit_assessment"
    as_of_date: date
    
    # 中间计算结果
    computed_metrics: Dict[str, Any] = field(default_factory=dict)
    
    # 规则执行结果
    rule_results: List[Dict] = field(default_factory=list)
    
    # 预警信息
    alerts: List[Dict] = field(default_factory=list)


@dataclass
class CreditAssessmentResult:
    """授信评估结果"""
    supplier_id: str
    company_name: str
    
    # 派生指标结果
    overdue_invoice_ratio: float = 0.0
    avg_invoice_amount: Money = None
    contract_utilization_rate: float = 0.0
    business_stability_score: int = 0
    reputation_score: int = 0
    
    # 复合指标结果
    credit_score: int = 0
    credit_grade: str = ""
    
    # 图算法指标
    guarantee_chain_depth: int = 0
    guarantee_risk_score: int = 0
    
    # 决策结果
    eligible: bool = False
    final_decision: str = ""
    approved_credit_limit: Money = None
    recommended_interest_rate: float = 0.0
    requires_additional_guarantee: bool = False
    
    # 解释
    decision_reasoning: str = ""
    alerts: List[Dict] = field(default_factory=list)


# ============================================================
# 指标计算引擎
# ============================================================

class MetricEngine:
    """指标计算引擎"""
    
    def calculate_overdue_invoice_ratio(self, ctx: AnalysisContext) -> float:
        """计算逾期发票占比"""
        total = ctx.supplier.total_invoice_amount_90d.value
        overdue = ctx.supplier.overdue_invoice_amount.value
        
        if total == 0:
            return 0.0
        
        ratio = (overdue / total) * 100
        ctx.computed_metrics["overdue_invoice_ratio"] = ratio
        
        print(f"  📊 逾期发票占比 = {overdue:,.2f} / {total:,.2f} * 100 = {ratio:.2f}%")
        
        # 触发阈值预警
        if ratio >= 15:
            ctx.alerts.append({
                "level": "critical",
                "type": "overdue_ratio_high",
                "message": f"逾期发票占比过高: {ratio:.2f}%"
            })
        elif ratio >= 5:
            ctx.alerts.append({
                "level": "warning",
                "type": "overdue_ratio_elevated",
                "message": f"逾期发票占比偏高: {ratio:.2f}%"
            })
        
        return ratio
    
    def calculate_avg_invoice_amount(self, ctx: AnalysisContext) -> Money:
        """计算平均发票金额"""
        count = ctx.supplier.invoice_count_90d
        total = ctx.supplier.total_invoice_amount_90d.value
        
        if count == 0:
            avg = 0
        else:
            avg = total / count
        
        result = Money(avg)
        ctx.computed_metrics["avg_invoice_amount"] = result
        
        print(f"  📊 平均发票金额 = {total:,.2f} / {count} = {result}")
        return result
    
    def calculate_contract_utilization_rate(self, ctx: AnalysisContext) -> float:
        """计算合同执行率"""
        invoice_total = ctx.supplier.total_invoice_amount_90d.value
        contract_total = ctx.supplier.total_contract_amount.value
        
        if contract_total == 0:
            rate = 0.0
        else:
            rate = (invoice_total / contract_total) * 100
        
        ctx.computed_metrics["contract_utilization_rate"] = rate
        
        print(f"  📊 合同执行率 = {invoice_total:,.2f} / {contract_total:,.2f} * 100 = {rate:.2f}%")
        return rate
    
    def calculate_business_stability_score(self, ctx: AnalysisContext) -> int:
        """计算业务稳定性评分"""
        score = 50  # 基础分
        
        # 合同执行率加分
        utilization = ctx.computed_metrics.get("contract_utilization_rate", 0)
        if utilization >= 80:
            score += 20
            print(f"    +20分 (合同执行率{utilization:.1f}% >= 80%)")
        elif utilization >= 50:
            score += 10
            print(f"    +10分 (合同执行率{utilization:.1f}% >= 50%)")
        
        # 核心企业数量加分
        core_count = ctx.supplier.core_enterprise_count
        if core_count >= 3:
            score += 15
            print(f"    +15分 (合作核心企业{core_count}家 >= 3家)")
        elif core_count >= 1:
            score += 5
            print(f"    +5分 (合作核心企业{core_count}家 >= 1家)")
        
        # 逾期率扣分
        overdue_ratio = ctx.computed_metrics.get("overdue_invoice_ratio", 0)
        if overdue_ratio < 5:
            score += 15
            print(f"    +15分 (逾期率{overdue_ratio:.2f}% < 5%)")
        elif overdue_ratio < 10:
            score += 5
            print(f"    +5分 (逾期率{overdue_ratio:.2f}% < 10%)")
        
        score = min(score, 100)
        ctx.computed_metrics["business_stability_score"] = score
        
        print(f"  📊 业务稳定性评分 = {score}/100")
        return score
    
    def calculate_reputation_score(self, ctx: AnalysisContext) -> int:
        """计算声誉风险评分"""
        base_score = 100
        
        # 负面新闻扣分
        news_count = ctx.supplier.negative_news_count_90d
        news_deduction = news_count * 10
        if news_deduction > 0:
            print(f"    -{news_deduction}分 (负面新闻{news_count}条)")
        
        # 逾期记录扣分
        overdue_ratio = ctx.computed_metrics.get("overdue_invoice_ratio", 0)
        overdue_deduction = overdue_ratio * 2
        if overdue_deduction > 0:
            print(f"    -{overdue_deduction:.1f}分 (逾期率{overdue_ratio:.2f}%)")
        
        score = max(0, base_score - news_deduction - overdue_deduction)
        ctx.computed_metrics["reputation_score"] = score
        
        print(f"  📊 声誉风险评分 = {score}/100")
        return score
    
    def calculate_guarantee_risk_score(self, ctx: AnalysisContext) -> int:
        """计算担保风险评分"""
        depth = ctx.supplier.guarantee_chain_depth
        has_circle = ctx.supplier.has_guarantee_circle
        
        if has_circle:
            score = 20
            print(f"    检测到担保圈! 评分降至{score}")
        elif depth >= 5:
            score = 20
        elif depth >= 3:
            score = 40
        elif depth >= 1:
            score = 70
        else:
            score = 100
        
        ctx.computed_metrics["guarantee_risk_score"] = score
        
        print(f"  📊 担保风险评分 = {score}/100 (担保链深度={depth}, 担保圈={has_circle})")
        
        if has_circle:
            ctx.alerts.append({
                "level": "critical",
                "type": "guarantee_circle_detected",
                "message": "检测到担保圈风险"
            })
        elif depth >= 3:
            ctx.alerts.append({
                "level": "high",
                "type": "guarantee_chain_long",
                "message": f"担保链过长: {depth}层"
            })
        
        return score
    
    def calculate_credit_score(self, ctx: AnalysisContext) -> int:
        """计算综合信用评分（复合指标）"""
        print("  📊 综合信用评分计算:")
        
        # 获取各维度分数
        stability = ctx.computed_metrics.get("business_stability_score", 50)
        tax = ctx.supplier.tax_compliance_score or 60
        reputation = ctx.computed_metrics.get("reputation_score", 80)
        guarantee = ctx.computed_metrics.get("guarantee_risk_score", 100)
        
        print(f"    业务稳定性: {stability} * 30% = {stability * 0.3:.1f}")
        print(f"    税务合规: {tax} * 25% = {tax * 0.25:.1f}")
        print(f"    声誉风险: {reputation} * 25% = {reputation * 0.25:.1f}")
        print(f"    担保风险: {guarantee} * 20% = {guarantee * 0.20:.1f}")
        
        # 加权计算
        score = (
            stability * 0.30 +
            tax * 0.25 +
            reputation * 0.25 +
            guarantee * 0.20
        )
        
        score = int(min(100, max(0, score)))
        ctx.computed_metrics["credit_score"] = score
        
        print(f"  📊 综合信用评分 = {score}/100")
        return score
    
    def calculate_credit_grade(self, ctx: AnalysisContext) -> str:
        """计算信用等级"""
        score = ctx.computed_metrics.get("credit_score", 0)
        
        if score >= 90:
            grade = "AAA"
        elif score >= 85:
            grade = "AA"
        elif score >= 80:
            grade = "A"
        elif score >= 70:
            grade = "BBB"
        elif score >= 60:
            grade = "BB"
        elif score >= 50:
            grade = "B"
        elif score >= 40:
            grade = "CCC"
        elif score >= 30:
            grade = "CC"
        elif score >= 20:
            grade = "C"
        else:
            grade = "D"
        
        ctx.computed_metrics["credit_grade"] = grade
        
        print(f"  📊 信用等级 = {grade}")
        return grade


# ============================================================
# 规则引擎
# ============================================================

class RuleEngine:
    """规则引擎"""
    
    def __init__(self):
        self.metric_engine = MetricEngine()
    
    def execute_rule_r001_basic_eligibility(self, ctx: AnalysisContext) -> bool:
        """规则1: 基础准入检查"""
        print("\n🔍 执行规则 R001: 基础准入检查")
        
        s = ctx.supplier
        checks = []
        
        # 检查1: 经营状态
        status_ok = s.status == "ACTIVE"
        checks.append(("经营状态正常", status_ok))
        print(f"  ✓ 经营状态: {s.status} {'通过' if status_ok else '不通过'}")
        
        # 检查2: 注册资本 >= 100万
        capital_ok = s.registered_capital.value >= 1000000
        checks.append(("注册资本>=100万", capital_ok))
        print(f"  ✓ 注册资本: {s.registered_capital} {'通过' if capital_ok else '不通过'}")
        
        # 检查3: 成立时间 >= 1年
        days_since_est = (ctx.as_of_date - s.establishment_date).days
        years_ok = days_since_est >= 365
        checks.append(("成立>=1年", years_ok))
        print(f"  ✓ 成立时间: {days_since_est}天 {'通过' if years_ok else '不通过'}")
        
        # 检查4: 近90天交易额 >= 50万
        amount_ok = s.total_invoice_amount_90d.value >= 500000
        checks.append(("近90天交易额>=50万", amount_ok))
        print(f"  ✓ 近90天交易额: {s.total_invoice_amount_90d} {'通过' if amount_ok else '不通过'}")
        
        all_passed = all(c[1] for c in checks)
        
        if all_passed:
            print("  ✅ 基础准入检查通过")
            ctx.computed_metrics["eligible"] = True
        else:
            failed = [c[0] for c in checks if not c[1]]
            print(f"  ❌ 基础准入检查不通过: {', '.join(failed)}")
            ctx.computed_metrics["eligible"] = False
            ctx.computed_metrics["rejection_reason"] = f"不符合准入条件: {', '.join(failed)}"
        
        ctx.rule_results.append({
            "rule_id": "R001",
            "rule_name": "基础准入检查",
            "passed": all_passed
        })
        
        return all_passed
    
    def execute_rule_r002_credit_scoring(self, ctx: AnalysisContext):
        """规则2: 信用评分计算"""
        print("\n🔍 执行规则 R002: 信用评分计算")
        
        # 计算派生指标
        print("  步骤1: 计算派生指标")
        self.metric_engine.calculate_overdue_invoice_ratio(ctx)
        self.metric_engine.calculate_avg_invoice_amount(ctx)
        self.metric_engine.calculate_contract_utilization_rate(ctx)
        
        print("\n  步骤2: 计算业务稳定性评分")
        self.metric_engine.calculate_business_stability_score(ctx)
        
        print("\n  步骤3: 计算声誉风险评分")
        self.metric_engine.calculate_reputation_score(ctx)
        
        print("\n  步骤4: 计算担保风险评分")
        self.metric_engine.calculate_guarantee_risk_score(ctx)
        
        print("\n  步骤5: 计算综合信用评分")
        self.metric_engine.calculate_credit_score(ctx)
        self.metric_engine.calculate_credit_grade(ctx)
        
        ctx.rule_results.append({
            "rule_id": "R002",
            "rule_name": "信用评分计算",
            "passed": True
        })
    
    def execute_rule_r003_guarantee_circle_check(self, ctx: AnalysisContext):
        """规则3: 担保圈检测"""
        print("\n🔍 执行规则 R003: 担保圈检测")
        
        if ctx.supplier.has_guarantee_circle:
            print("  ⚠️ 检测到担保圈风险!")
            ctx.alerts.append({
                "level": "critical",
                "type": "guarantee_circle",
                "message": "该供应商处于担保圈中，存在循环担保风险"
            })
        else:
            print("  ✅ 未检测到担保圈")
        
        ctx.rule_results.append({
            "rule_id": "R003",
            "rule_name": "担保圈检测",
            "passed": not ctx.supplier.has_guarantee_circle
        })
    
    def execute_rule_r004_credit_limit_calculation(self, ctx: AnalysisContext):
        """规则4: 授信额度计算"""
        print("\n🔍 执行规则 R004: 授信额度计算")
        
        credit_score = ctx.computed_metrics.get("credit_score", 0)
        credit_grade = ctx.computed_metrics.get("credit_grade", "D")
        registered_capital = ctx.supplier.registered_capital.value
        guarantee_depth = ctx.supplier.guarantee_chain_depth
        
        # 基础额度 = 注册资本 * 0.5
        base = registered_capital * 0.5
        print(f"  基础额度 = 注册资本 * 0.5 = {registered_capital:,.2f} * 0.5 = {base:,.2f}")
        
        # 信用等级乘数
        multiplier_map = {
            "AAA": 2.0, "AA": 1.8, "A": 1.5,
            "BBB": 1.2, "BB": 1.0, "B": 0.8,
            "CCC": 0.6, "CC": 0.5, "C": 0.4, "D": 0.3
        }
        multiplier = multiplier_map.get(credit_grade, 0.3)
        print(f"  信用等级乘数 ({credit_grade}): {multiplier}")
        
        # 担保链风险调整
        if guarantee_depth > 0:
            adjustment = 1 - guarantee_depth * 0.1
            multiplier = multiplier * max(0.5, adjustment)
            print(f"  担保链风险调整 (深度={guarantee_depth}): 乘数调整为 {multiplier:.2f}")
        
        # 计算推荐额度
        credit_limit = base * multiplier
        
        ctx.computed_metrics["recommended_credit_limit"] = credit_limit
        
        print(f"  📊 推荐授信额度 = {base:,.2f} * {multiplier:.2f} = {credit_limit:,.2f}")
        
        ctx.rule_results.append({
            "rule_id": "R004",
            "rule_name": "授信额度计算",
            "passed": True
        })
    
    def execute_rule_r005_risk_early_warning(self, ctx: AnalysisContext):
        """规则5: 风险预警"""
        print("\n🔍 执行规则 R005: 风险预警检查")
        
        overdue_ratio = ctx.computed_metrics.get("overdue_invoice_ratio", 0)
        negative_news = ctx.supplier.negative_news_count_90d
        credit_score = ctx.computed_metrics.get("credit_score", 0)
        guarantee_depth = ctx.supplier.guarantee_chain_depth
        has_circle = ctx.supplier.has_guarantee_circle
        
        warnings = []
        
        if overdue_ratio >= 15:
            warnings.append(("critical", f"逾期发票占比过高: {overdue_ratio:.2f}%"))
        
        if credit_score < 50:
            warnings.append(("critical", f"信用评分严重不足: {credit_score}"))
        
        if has_circle:
            warnings.append(("critical", "检测到担保圈风险"))
        elif guarantee_depth >= 5:
            warnings.append(("high", f"担保链过长: {guarantee_depth}层"))
        
        if negative_news >= 3:
            warnings.append(("warning", f"近期负面舆情较多: {negative_news}条"))
        
        if warnings:
            print("  ⚠️ 发现风险预警:")
            for level, msg in warnings:
                print(f"    [{level.upper()}] {msg}")
        else:
            print("  ✅ 无风险预警")
        
        ctx.rule_results.append({
            "rule_id": "R005",
            "rule_name": "风险预警",
            "passed": len([w for w in warnings if w[0] == "critical"]) == 0
        })
    
    def execute_rule_r006_interest_rate_pricing(self, ctx: AnalysisContext):
        """规则6: 利率定价"""
        print("\n🔍 执行规则 R006: 利率定价")
        
        credit_score = ctx.computed_metrics.get("credit_score", 50)
        
        base_rate = 0.05  # 5%基准利率
        risk_premium = (100 - credit_score) / 100 * 0.05
        interest_rate = (base_rate + risk_premium) * 100
        
        ctx.computed_metrics["recommended_interest_rate"] = interest_rate
        
        print(f"  基准利率: 5.00%")
        print(f"  风险溢价: {(100 - credit_score) / 100 * 0.05 * 100:.2f}% (基于信用分{credit_score})")
        print(f"  📊 建议利率: {interest_rate:.2f}%")
        
        ctx.rule_results.append({
            "rule_id": "R006",
            "rule_name": "利率定价",
            "passed": True
        })
    
    def execute_rule_r007_comprehensive_decision(self, ctx: AnalysisContext):
        """规则7: 综合授信决策"""
        print("\n🔍 执行规则 R007: 综合授信决策")
        
        credit_score = ctx.computed_metrics.get("credit_score", 0)
        guarantee_depth = ctx.supplier.guarantee_chain_depth
        has_circle = ctx.supplier.has_guarantee_circle
        eligible = ctx.computed_metrics.get("eligible", False)
        
        if not eligible:
            decision = "REJECT"
            reasoning = "不符合基础准入条件"
            requires_guarantee = False
        elif has_circle:
            decision = "APPROVE_WITH_CONDITIONS"
            reasoning = "存在担保圈风险，需加强监控并降低额度"
            requires_guarantee = True
        elif credit_score >= 80 and guarantee_depth < 2:
            decision = "APPROVE"
            reasoning = "信用良好，担保风险可控"
            requires_guarantee = False
        elif credit_score >= 60 and guarantee_depth < 3:
            decision = "APPROVE_WITH_CONDITIONS"
            reasoning = "信用一般，需追加担保"
            requires_guarantee = True
        elif credit_score >= 40:
            decision = "APPROVE_RESTRICTED"
            reasoning = "信用较差，严格限制额度并要求担保"
            requires_guarantee = True
        else:
            decision = "REJECT"
            reasoning = "信用评分过低，风险不可控"
            requires_guarantee = False
        
        ctx.computed_metrics["final_decision"] = decision
        ctx.computed_metrics["decision_reasoning"] = reasoning
        ctx.computed_metrics["requires_additional_guarantee"] = requires_guarantee
        
        print(f"  决策结果: {decision}")
        print(f"  决策理由: {reasoning}")
        print(f"  需要追加担保: {'是' if requires_guarantee else '否'}")
        
        ctx.rule_results.append({
            "rule_id": "R007",
            "rule_name": "综合授信决策",
            "passed": decision != "REJECT"
        })
    
    def execute_dimension_analysis(self, ctx: AnalysisContext) -> CreditAssessmentResult:
        """执行完整维度分析"""
        print(f"\n{'='*60}")
        print(f"🎯 开始分析: {ctx.supplier.company_name}")
        print(f"   分析维度: {ctx.dimension}")
        print(f"   分析日期: {ctx.as_of_date}")
        print(f"{'='*60}")
        
        # 步骤1: 基础准入检查
        eligible = self.execute_rule_r001_basic_eligibility(ctx)
        
        if eligible:
            # 步骤2: 信用评分计算
            self.execute_rule_r002_credit_scoring(ctx)
            
            # 步骤3: 担保圈检测
            self.execute_rule_r003_guarantee_circle_check(ctx)
            
            # 步骤4: 授信额度计算
            self.execute_rule_r004_credit_limit_calculation(ctx)
            
            # 步骤5: 风险预警
            self.execute_rule_r005_risk_early_warning(ctx)
            
            # 步骤6: 利率定价
            self.execute_rule_r006_interest_rate_pricing(ctx)
            
            # 步骤7: 综合决策
            self.execute_rule_r007_comprehensive_decision(ctx)
        
        # 组装结果
        result = CreditAssessmentResult(
            supplier_id=ctx.supplier.supplier_id,
            company_name=ctx.supplier.company_name,
            
            # 派生指标
            overdue_invoice_ratio=ctx.computed_metrics.get("overdue_invoice_ratio", 0),
            avg_invoice_amount=ctx.computed_metrics.get("avg_invoice_amount", Money(0)),
            contract_utilization_rate=ctx.computed_metrics.get("contract_utilization_rate", 0),
            business_stability_score=ctx.computed_metrics.get("business_stability_score", 0),
            reputation_score=ctx.computed_metrics.get("reputation_score", 0),
            
            # 复合指标
            credit_score=ctx.computed_metrics.get("credit_score", 0),
            credit_grade=ctx.computed_metrics.get("credit_grade", "D"),
            
            # 图算法指标
            guarantee_chain_depth=ctx.supplier.guarantee_chain_depth,
            guarantee_risk_score=ctx.computed_metrics.get("guarantee_risk_score", 0),
            
            # 决策结果
            eligible=eligible,
            final_decision=ctx.computed_metrics.get("final_decision", "REJECT"),
            approved_credit_limit=Money(ctx.computed_metrics.get("recommended_credit_limit", 0)),
            recommended_interest_rate=ctx.computed_metrics.get("recommended_interest_rate", 0),
            requires_additional_guarantee=ctx.computed_metrics.get("requires_additional_guarantee", False),
            decision_reasoning=ctx.computed_metrics.get("decision_reasoning", ""),
            alerts=ctx.alerts
        )
        
        return result


# ============================================================
# 演示执行
# ============================================================

def create_supplier_case_1() -> Supplier:
    """案例1: 优质供应商 - 深圳智造科技"""
    return Supplier(
        supplier_id="SUP_2024_001",
        company_name="深圳智造科技有限公司",
        unified_credit_code="91440300MA5G8KXXXX",
        registered_capital=Money(50000000),  # 5000万
        establishment_date=date(2018, 3, 15),
        industry_type="TECHNOLOGY",
        company_size="MEDIUM",
        status="ACTIVE",
        
        # 原子指标
        total_invoice_amount_90d=Money(12450000),  # 1245万
        invoice_count_90d=5,
        overdue_invoice_amount=Money(150000),  # 15万（仅1张小额逾期）
        total_contract_amount=Money(23000000),  # 2300万
        avg_monthly_tax_revenue=Money(800000),  # 80万
        tax_compliance_score=85,
        negative_news_count_90d=0,
        core_enterprise_count=2,
        
        # 担保
        guarantee_chain_depth=1,
        has_guarantee_circle=False,
        
        active_dimensions=["credit_assessment"]
    )


def create_supplier_case_2() -> Supplier:
    """案例2: 高风险供应商 - 某贸易公司"""
    return Supplier(
        supplier_id="SUP_2024_003",
        company_name="某贸易有限公司",
        unified_credit_code="91440300MA5G8KYYYY",
        registered_capital=Money(1000000),  # 100万（刚好过线）
        establishment_date=date(2023, 6, 1),  # 成立不到1年
        industry_type="TRADING",
        company_size="SMALL",
        status="ACTIVE",
        
        # 原子指标 - 风险信号
        total_invoice_amount_90d=Money(1000000),  # 100万（刚过线）
        invoice_count_90d=3,
        overdue_invoice_amount=Money(800000),  # 80万（大部分逾期）
        total_contract_amount=Money(1500000),
        avg_monthly_tax_revenue=Money(50000),
        tax_compliance_score=40,
        negative_news_count_90d=5,  # 多条负面新闻
        core_enterprise_count=0,  # 无核心企业合作
        
        guarantee_chain_depth=0,
        has_guarantee_circle=False,
        
        active_dimensions=["credit_assessment"]
    )


def create_supplier_case_3() -> Supplier:
    """案例3: 担保圈供应商 - 供应商A"""
    return Supplier(
        supplier_id="SUP_2024_A",
        company_name="供应商A（担保圈成员）",
        unified_credit_code="91440300MA5G8KAAAA",
        registered_capital=Money(10000000),  # 1000万
        establishment_date=date(2020, 1, 1),
        industry_type="MANUFACTURING",
        company_size="MEDIUM",
        status="ACTIVE",
        
        # 原子指标 - 本身资质不错
        total_invoice_amount_90d=Money(8000000),
        invoice_count_90d=8,
        overdue_invoice_amount=Money(100000),
        total_contract_amount=Money(12000000),
        avg_monthly_tax_revenue=Money(500000),
        tax_compliance_score=75,
        negative_news_count_90d=0,
        core_enterprise_count=2,
        
        # 担保圈风险
        guarantee_chain_depth=3,
        has_guarantee_circle=True,  # 处于担保圈中
        
        active_dimensions=["credit_assessment"]
    )


def print_result(result: CreditAssessmentResult):
    """打印分析结果"""
    print(f"\n{'='*60}")
    print("📋 分析结果汇总")
    print(f"{'='*60}")
    
    print(f"\n🏢 企业信息:")
    print(f"  供应商ID: {result.supplier_id}")
    print(f"  企业名称: {result.company_name}")
    
    print(f"\n📊 派生指标:")
    print(f"  逾期发票占比: {result.overdue_invoice_ratio:.2f}%")
    print(f"  平均发票金额: {result.avg_invoice_amount}")
    print(f"  合同执行率: {result.contract_utilization_rate:.2f}%")
    print(f"  业务稳定性评分: {result.business_stability_score}/100")
    print(f"  声誉风险评分: {result.reputation_score}/100")
    
    print(f"\n📈 复合指标:")
    print(f"  综合信用评分: {result.credit_score}/100")
    print(f"  信用等级: {result.credit_grade}")
    print(f"  担保链深度: {result.guarantee_chain_depth}")
    print(f"  担保风险评分: {result.guarantee_risk_score}/100")
    
    print(f"\n✅ 授信决策:")
    print(f"  准入资格: {'通过' if result.eligible else '未通过'}")
    print(f"  最终决策: {result.final_decision}")
    print(f"  推荐授信额度: {result.approved_credit_limit}")
    print(f"  建议利率: {result.recommended_interest_rate:.2f}%")
    print(f"  需要追加担保: {'是' if result.requires_additional_guarantee else '否'}")
    print(f"  决策理由: {result.decision_reasoning}")
    
    if result.alerts:
        print(f"\n⚠️ 风险预警:")
        for alert in result.alerts:
            print(f"  [{alert['level'].upper()}] {alert['message']}")
    
    print(f"\n{'='*60}")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("供应链金融授信评估 MVP 演示")
    print("分析链路: 分析对象 -> 分析维度(BY) -> 分析逻辑(计算指标)")
    print("="*60)
    
    # 初始化规则引擎
    engine = RuleEngine()
    analysis_date = date(2026, 4, 7)
    
    # ============================================================
    # 案例1: 优质供应商
    # ============================================================
    print("\n" + "="*60)
    print("📌 案例 1: 优质供应商（预期：正常授信）")
    print("="*60)
    
    supplier1 = create_supplier_case_1()
    ctx1 = AnalysisContext(
        supplier=supplier1,
        dimension="credit_assessment",
        as_of_date=analysis_date
    )
    result1 = engine.execute_dimension_analysis(ctx1)
    print_result(result1)
    
    # ============================================================
    # 案例2: 高风险供应商
    # ============================================================
    print("\n" + "="*60)
    print("📌 案例 2: 高风险供应商（预期：拒绝授信）")
    print("="*60)
    
    supplier2 = create_supplier_case_2()
    ctx2 = AnalysisContext(
        supplier=supplier2,
        dimension="credit_assessment",
        as_of_date=analysis_date
    )
    result2 = engine.execute_dimension_analysis(ctx2)
    print_result(result2)
    
    # ============================================================
    # 案例3: 担保圈供应商
    # ============================================================
    print("\n" + "="*60)
    print("📌 案例 3: 担保圈供应商（预期：担保圈预警，有条件授信）")
    print("="*60)
    
    supplier3 = create_supplier_case_3()
    ctx3 = AnalysisContext(
        supplier=supplier3,
        dimension="credit_assessment",
        as_of_date=analysis_date
    )
    result3 = engine.execute_dimension_analysis(ctx3)
    print_result(result3)
    
    # ============================================================
    # 总结
    # ============================================================
    print("\n" + "="*60)
    print("📊 案例对比总结")
    print("="*60)
    
    print(f"\n{'案例':<15} {'企业名称':<25} {'信用分':<10} {'等级':<8} {'决策':<20} {'授信额度':<15}")
    print("-"*100)
    
    cases = [
        ("案例1", result1),
        ("案例2", result2),
        ("案例3", result3),
    ]
    
    for case_name, result in cases:
        print(f"{case_name:<15} {result.company_name:<25} {result.credit_score:<10} "
              f"{result.credit_grade:<8} {result.final_decision:<20} {result.approved_credit_limit}")
    
    print("\n" + "="*60)
    print("✅ MVP演示完成")
    print("="*60)


if __name__ == "__main__":
    main()
