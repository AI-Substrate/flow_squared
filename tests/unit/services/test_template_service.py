"""Tests for TemplateService (Smart Content Phase 2).

TDD Phase: GREEN - TemplateService is implemented and these tests should pass.

Focus:
- Critical Discovery 04: package-safe loading via importlib.resources
- Critical Discovery 09: validate templates at initialization (fail early)
- Critical Discovery 12: surface failures as service-layer TemplateError
"""

import pytest


@pytest.mark.unit
def test_given_template_service_when_constructed_then_loads_all_required_templates():
    """TemplateService loads required templates at init.

    Purpose: Proves TemplateService initializes with required templates loaded
    Quality Contribution: Prevents runtime template-not-found failures
    Acceptance Criteria: Plan Phase 2 task 2.1 — constructor validates required templates are present and loadable.
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.services.smart_content.exceptions import TemplateError
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    sources = {
        "smart_content_file.j2": "name={{ name }}",
        "smart_content_type.j2": "name={{ name }}",
        "smart_content_callable.j2": "name={{ name }}",
        "smart_content_section.j2": "name={{ name }}",
        "smart_content_block.j2": "name={{ name }}",
        "smart_content_base.j2": "name={{ name }}",
    }

    try:
        service = TemplateService(config, template_sources=sources)
    except TemplateError as e:  # pragma: no cover - expected in RED until implemented
        raise AssertionError(f"Unexpected TemplateError during init: {e}") from e

    assert set(service.list_template_names()) == set(sources.keys())


@pytest.mark.unit
def test_given_missing_template_when_constructed_then_raises_template_error():
    """TemplateService fails early if required templates are missing.

    Purpose: Proves init-time validation catches missing templates
    Quality Contribution: Fails fast with actionable errors
    Acceptance Criteria: Plan Phase 2 task 2.1 — missing required template raises service-layer TemplateError (fail early).
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.services.smart_content.exceptions import TemplateError
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    sources = {
        "smart_content_base.j2": "ok",
    }

    with pytest.raises(TemplateError, match=r"missing"):
        TemplateService(
            config,
            required_template_names=[
                "smart_content_base.j2",
                "smart_content_callable.j2",
            ],
            template_sources=sources,
        )


@pytest.mark.unit
def test_given_invalid_template_syntax_when_constructed_then_raises_template_error():
    """TemplateService fails early on template syntax errors.

    Purpose: Proves templates are validated at init (not at render-time)
    Quality Contribution: Avoids delayed failures during prompt rendering
    Acceptance Criteria: Plan Phase 2 deliverable “Template validation at initialization” — invalid syntax raises TemplateError at construction time.
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.services.smart_content.exceptions import TemplateError
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    sources = {
        "smart_content_base.j2": "{% if %}",  # invalid Jinja2 syntax
    }

    with pytest.raises(TemplateError, match=r"syntax|parse|template"):
        TemplateService(
            config,
            required_template_names=["smart_content_base.j2"],
            template_sources=sources,
        )


@pytest.mark.unit
def test_given_category_when_resolving_template_then_matches_ac11_mapping():
    """TemplateService maps categories to templates per AC11 (with fallback).

    Purpose: Proves category→template mapping contract (AC11)
    Quality Contribution: Prevents wrong prompt shapes for node categories
    Acceptance Criteria: AC11 — category→template mapping matches spec table for all 9 categories (specialized + fallback).
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.services.smart_content.template_service import TemplateService

    config_obj = SmartContentConfig()
    config = FakeConfigurationService(config_obj)
    sources = {
        "smart_content_file.j2": "ok",
        "smart_content_type.j2": "ok",
        "smart_content_callable.j2": "ok",
        "smart_content_section.j2": "ok",
        "smart_content_block.j2": "ok",
        "smart_content_base.j2": "ok",
    }

    service = TemplateService(config, template_sources=sources)

    assert service.resolve_template_name("file") == "smart_content_file.j2"
    assert service.resolve_template_name("type") == "smart_content_type.j2"
    assert service.resolve_template_name("callable") == "smart_content_callable.j2"
    assert service.resolve_template_name("section") == "smart_content_section.j2"
    assert service.resolve_template_name("block") == "smart_content_block.j2"

    assert service.resolve_template_name("definition") == "smart_content_base.j2"
    assert service.resolve_template_name("statement") == "smart_content_base.j2"
    assert service.resolve_template_name("expression") == "smart_content_base.j2"
    assert service.resolve_template_name("other") == "smart_content_base.j2"


@pytest.mark.unit
def test_given_category_when_resolving_max_tokens_then_uses_smart_content_config_defaults():
    """TemplateService resolves per-category max_tokens from SmartContentConfig.

    Purpose: Proves token limits are config-driven (Phase 1 dependency)
    Quality Contribution: Prevents hard-coded token budgets across services
    Acceptance Criteria: AC4 — max_tokens is derived from SmartContentConfig.token_limits for all categories.
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.services.smart_content.template_service import TemplateService

    config_obj = SmartContentConfig()
    config = FakeConfigurationService(config_obj)
    sources = {
        "smart_content_file.j2": "ok",
        "smart_content_type.j2": "ok",
        "smart_content_callable.j2": "ok",
        "smart_content_section.j2": "ok",
        "smart_content_block.j2": "ok",
        "smart_content_base.j2": "ok",
    }

    service = TemplateService(config, template_sources=sources)

    for category, expected in config_obj.token_limits.items():
        assert service.resolve_max_tokens(category) == expected


@pytest.mark.unit
def test_given_required_context_vars_when_rendering_then_all_ac8_vars_are_supported():
    """TemplateService render supports the AC8 context contract.

    Purpose: Proves all AC8 variables are available to templates
    Quality Contribution: Prevents silent prompt degradation from missing fields
    Acceptance Criteria: AC8 — rendering accepts required context vars and injects max_tokens from config for the category.
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.services.smart_content.template_service import TemplateService

    config_obj = SmartContentConfig(
        token_limits={
            "file": 200,
            "type": 200,
            "callable": 999,
            "section": 150,
            "block": 150,
            "definition": 150,
            "statement": 100,
            "expression": 100,
            "other": 100,
        }
    )
    config = FakeConfigurationService(config_obj)
    sources = {
        "smart_content_callable.j2": (
            "name={{ name }}|qualified_name={{ qualified_name }}|category={{ category }}|"
            "ts_kind={{ ts_kind }}|language={{ language }}|content={{ content }}|"
            "signature={{ signature }}|max_tokens={{ max_tokens }}"
        ),
    }

    service = TemplateService(
        config,
        required_template_names=["smart_content_callable.j2"],
        template_sources=sources,
    )

    rendered = service.render_for_category(
        "callable",
        {
            "name": "my_func",
            "qualified_name": "MyClass.my_func",
            "category": "callable",
            "ts_kind": "function_definition",
            "language": "python",
            "content": "def my_func(): ...",
            "signature": "def my_func():",
        },
    )

    assert "name=my_func" in rendered
    assert "qualified_name=MyClass.my_func" in rendered
    assert "category=callable" in rendered
    assert "ts_kind=function_definition" in rendered
    assert "language=python" in rendered
    assert "signature=def my_func():" in rendered
    assert "max_tokens=999" in rendered


@pytest.mark.unit
def test_given_missing_required_context_var_when_rendering_then_raises_template_error():
    """TemplateService fails closed on missing AC8 context vars.

    Purpose: Proves strict undefined behavior for contract enforcement
    Quality Contribution: Ensures missing vars do not silently omit content
    Acceptance Criteria: AC8 — missing required context var fails closed (TemplateError), not silent omission.
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.services.smart_content.exceptions import TemplateError
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    sources = {"smart_content_callable.j2": "signature={{ signature }}"}

    service = TemplateService(
        config,
        required_template_names=["smart_content_callable.j2"],
        template_sources=sources,
    )

    with pytest.raises(TemplateError):
        service.render_for_category(
            "callable",
            {
                "name": "my_func",
                "qualified_name": "MyClass.my_func",
                "category": "callable",
                "ts_kind": "function_definition",
                "language": "python",
                "content": "def my_func(): ...",
            },
        )


@pytest.mark.unit
def test_given_all_templates_when_rendering_then_no_template_raises():
    """All packaged templates load and render end-to-end.

    Purpose: Proves package-data + importlib.resources loading works when installed
    Quality Contribution: Prevents runtime failures due to missing template files
    Acceptance Criteria: Plan Phase 2 task 2.12 — all templates load and render without raising; AC11/AC4 markers present in output.
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.services.smart_content.template_service import TemplateService

    service = TemplateService(FakeConfigurationService(SmartContentConfig()))

    categories = [
        "file",
        "type",
        "callable",
        "section",
        "block",
        "definition",
        "statement",
        "expression",
        "other",
    ]

    for category in categories:
        rendered = service.render_for_category(
            category,
            {
                "name": f"example_{category}",
                "qualified_name": f"Example.{category}",
                "ts_kind": "example_kind",
                "language": "python",
                "content": "example content",
                "signature": "example signature",
            },
        )

        assert f"Category: {category}" in rendered
        assert "Max tokens:" in rendered
