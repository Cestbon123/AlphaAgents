"""Tests for agent skills registry."""

from app.agent.skills import ALL_SKILLS, get_skill, get_skills_for_display
from app.agent.tools import find_tool


def test_all_skills_have_required_fields():
    for skill in ALL_SKILLS:
        assert skill.id, "Skill missing id"
        assert skill.name, f"Skill {skill.id} missing name"
        assert skill.description, f"Skill {skill.id} missing description"
        assert skill.tools, f"Skill {skill.id} has empty tools list"
        assert skill.data_sources, f"Skill {skill.id} has empty data_sources"


def test_all_skill_tools_exist():
    for skill in ALL_SKILLS:
        for tool_name in skill.tools:
            tool = find_tool(tool_name)
            assert tool is not None, f"Skill {skill.id} references unknown tool: {tool_name}"


def test_get_skill_returns_correct_skill():
    s = get_skill("stock_diagnosis")
    assert s is not None
    assert s.id == "stock_diagnosis"
    assert s.name == "个股诊断"
    assert get_skill("nonexistent") is None


def test_get_skills_for_display():
    result = get_skills_for_display()
    assert len(result) == len(ALL_SKILLS)
    for item in result:
        assert "id" in item
        assert "name" in item
        assert "description" in item


def test_review_deposition_requires_confirmation():
    s = get_skill("review_deposition")
    assert s.is_write
    assert s.requires_confirmation
    assert "update_tracking" in s.tools or "record_operation" in s.tools
