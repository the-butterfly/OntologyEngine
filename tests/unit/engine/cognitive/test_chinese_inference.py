"""Tests for Chinese memory_type inference patterns."""

from __future__ import annotations

import pytest

from ontology_engine.engine.cognitive.memory_utils import infer_memory_type


class TestChineseEntityInference:
    @pytest.mark.parametrize("content", [
        "这家公司是行业领先企业",
        "该机构负责监管金融市场",
        "这个组织致力于环保事业",
        "他是一位知名人物",
        "这款产品在市场上很受欢迎",
        "这个地点风景优美",
        "北京是一座历史悠久的城市",
        "中国是一个发展中国家",
    ])
    def test_entity_chinese(self, content: str) -> None:
        assert infer_memory_type(content) == "entity"


class TestChineseRelationInference:
    @pytest.mark.parametrize("content", [
        "他任职于该部门",
        "总部位于上海",
        "他管理着一个团队",
        "他向CEO汇报工作",
        "双方合作开发新项目",
        "他们是主要供应商",
        "他们是我们的大客户",
    ])
    def test_relation_chinese(self, content: str) -> None:
        assert infer_memory_type(content) == "relation"


class TestChineseRuleInference:
    @pytest.mark.parametrize("content", [
        "员工应该按时上班",
        "必须遵守安全规定",
        "禁止在办公区域吸烟",
        "如果违规则处以罚款",
        "根据政策要求执行",
        "按规定流程操作",
    ])
    def test_rule_chinese(self, content: str) -> None:
        assert infer_memory_type(content) == "rule"


class TestChineseEpisodeInference:
    @pytest.mark.parametrize("content", [
        "昨天发生了一起事故",
        "今天我们开了项目会议",
        "上周系统出现了故障",
        "上月销售额有所增长",
        "发生了一件意想不到的事",
        "出现了一个新问题",
        "这是一次重大事件",
        "事故原因正在调查中",
    ])
    def test_episode_chinese(self, content: str) -> None:
        assert infer_memory_type(content) == "episode"


class TestChineseProcedureInference:
    @pytest.mark.parametrize("content", [
        "首先准备材料",
        "然后进行测试",
        "接着分析结果",
        "最后生成报告",
        "按照步骤逐一执行",
        "这是标准流程",
        "操作前请确认",
        "使用方法如下",
    ])
    def test_procedure_chinese(self, content: str) -> None:
        assert infer_memory_type(content) == "procedure"


class TestChineseOpinionInference:
    @pytest.mark.parametrize("content", [
        "我认为这个方案可行",
        "我相信团队的能力",
        "我希望项目能成功",
        "这可能是一个误判",
        "大概需要三天时间",
        "似乎有什么不对",
    ])
    def test_opinion_chinese(self, content: str) -> None:
        assert infer_memory_type(content) == "opinion"


class TestChineseObservationInference:
    @pytest.mark.parametrize("content", [
        "观察到温度异常升高",
        "检测到网络延迟增加",
        "测量结果超出预期",
        "记录下所有异常情况",
        "数据显示增长趋势",
    ])
    def test_observation_chinese(self, content: str) -> None:
        assert infer_memory_type(content) == "observation"


class TestChineseFallbackToFragment:
    def test_unrecognized_chinese_falls_to_fragment(self) -> None:
        assert infer_memory_type("这是一段普通的文字") == "fragment"

    def test_english_still_works(self) -> None:
        assert infer_memory_type("The company is a leading organization") == "entity"
        assert infer_memory_type("I think this is correct") == "opinion"
