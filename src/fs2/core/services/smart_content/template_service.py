"""TemplateService for Smart Content prompt rendering (Phase 2).

Loads Jinja2 templates from package resources (wheel-safe) and renders prompts
using a stable context contract (AC8) and category mapping (AC11).
"""

from __future__ import annotations

import importlib.resources as importlib_resources
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from jinja2 import DictLoader, Environment, StrictUndefined
from jinja2.exceptions import TemplateError as JinjaTemplateError
from jinja2.exceptions import TemplateNotFound, TemplateSyntaxError, UndefinedError

from fs2.config.objects import SmartContentConfig
from fs2.core.services.smart_content.exceptions import TemplateError

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


DEFAULT_TEMPLATE_PACKAGE = "fs2.core.templates.smart_content"
DEFAULT_REQUIRED_TEMPLATE_NAMES: tuple[str, ...] = (
    "smart_content_file.j2",
    "smart_content_type.j2",
    "smart_content_callable.j2",
    "smart_content_section.j2",
    "smart_content_block.j2",
    "smart_content_base.j2",
)


@dataclass(frozen=True)
class TemplateSelection:
    template_name: str
    max_tokens: int


class TemplateService:
    """Service for loading and rendering Smart Content templates."""

    def __init__(
        self,
        config: ConfigurationService,
        *,
        template_package: str = DEFAULT_TEMPLATE_PACKAGE,
        required_template_names: Sequence[str] = DEFAULT_REQUIRED_TEMPLATE_NAMES,
        template_sources: Mapping[str, str] | None = None,
    ) -> None:
        self._config = config
        self._smart_config = config.require(SmartContentConfig)
        self._template_package = template_package
        self._required_template_names = tuple(required_template_names)

        if template_sources is None:
            template_sources = self._load_template_sources_from_package(
                template_package,
                self._required_template_names,
            )

        self._template_sources = dict(template_sources)
        self._env = Environment(
            loader=DictLoader(self._template_sources),
            undefined=StrictUndefined,
            autoescape=False,
        )

        self._validate_templates_at_init()

    def list_template_names(self) -> list[str]:
        return sorted(self._template_sources.keys())

    def resolve_template_name(self, category: str) -> str:
        mapping = {
            "file": "smart_content_file.j2",
            "type": "smart_content_type.j2",
            "callable": "smart_content_callable.j2",
            "section": "smart_content_section.j2",
            "block": "smart_content_block.j2",
            "definition": "smart_content_base.j2",
            "statement": "smart_content_base.j2",
            "expression": "smart_content_base.j2",
            "other": "smart_content_base.j2",
        }
        return mapping.get(category, "smart_content_base.j2")

    def resolve_max_tokens(self, category: str) -> int:
        limits = self._smart_config.token_limits
        if category in limits:
            return limits[category]
        if "other" in limits:
            return limits["other"]
        raise TemplateError(f"No token limit configured for category: {category}")

    def select_for_category(self, category: str) -> TemplateSelection:
        return TemplateSelection(
            template_name=self.resolve_template_name(category),
            max_tokens=self.resolve_max_tokens(category),
        )

    def render_template(self, template_name: str, context: Mapping[str, Any]) -> str:
        try:
            template = self._env.get_template(template_name)
            return template.render(dict(context))
        except (TemplateNotFound, TemplateSyntaxError, UndefinedError, JinjaTemplateError) as e:
            raise TemplateError(f"Template render failed for '{template_name}': {e}") from e

    def render_for_category(self, category: str, context: Mapping[str, Any]) -> str:
        selection = self.select_for_category(category)

        render_context = dict(context)
        render_context.setdefault("category", category)
        render_context.setdefault("max_tokens", selection.max_tokens)

        return self.render_template(selection.template_name, render_context)

    @staticmethod
    def _load_template_sources_from_package(
        template_package: str,
        required_template_names: Sequence[str],
    ) -> dict[str, str]:
        base = importlib_resources.files(template_package)
        sources: dict[str, str] = {}

        missing: list[str] = []
        for name in required_template_names:
            candidate = base.joinpath(name)
            try:
                if not candidate.is_file():
                    missing.append(name)
                    continue
                sources[name] = candidate.read_text(encoding="utf-8")
            except FileNotFoundError:
                missing.append(name)

        if missing:
            missing_str = ", ".join(missing)
            raise TemplateError(
                f"TemplateService initialization failed: missing templates: {missing_str}"
            )

        return sources

    def _validate_templates_at_init(self) -> None:
        for name in self._required_template_names:
            try:
                self._env.get_template(name)
            except TemplateNotFound as e:
                raise TemplateError(
                    f"TemplateService initialization failed: missing template: {name}"
                ) from e
            except TemplateSyntaxError as e:
                raise TemplateError(
                    f"TemplateService initialization failed: invalid template syntax in '{name}': {e}"
                ) from e
            except JinjaTemplateError as e:
                raise TemplateError(
                    f"TemplateService initialization failed: template error in '{name}': {e}"
                ) from e
