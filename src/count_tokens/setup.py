"""Setup wizard: separated into prompter interface and config creation logic."""

from __future__ import annotations

from typing import Protocol

from count_tokens.config import load_config, save_config, CONFIG_FILE
from count_tokens.providers.base import Config, ProviderConfig
from count_tokens.providers import PROVIDER_ENV_KEYS


PLAN_OPTIONS: dict[str, list[tuple[str, str]]] = {
    "claude": [
        ("Free", "free"), ("Pro ($20/mo)", "pro"), ("Max 5x ($100/mo)", "max_5x"),
        ("Max 20x ($200/mo)", "max_20x"), ("Team Standard", "team_standard"),
        ("Team Premium", "team_premium"), ("Enterprise", "enterprise"),
    ],
    "openai": [
        ("Free", "free"), ("Go ($8/mo)", "go"), ("Plus ($20/mo)", "plus"),
        ("Pro ($200/mo)", "pro"), ("Business", "business"), ("Enterprise", "enterprise"),
    ],
    "gemini": [
        ("Free", "free"), ("AI Plus ($7.99/mo)", "ai_plus"),
        ("AI Pro ($19.99/mo)", "ai_pro"), ("AI Ultra ($249.99/mo)", "ai_ultra"),
    ],
    "grok": [
        ("Free", "free"), ("X Premium ($8/mo)", "x_premium"),
        ("X Premium+ ($40/mo)", "x_premium_plus"), ("SuperGrok ($30/mo)", "supergrok"),
        ("SuperGrok Heavy ($300/mo)", "supergrok_heavy"),
    ],
}

DEFAULT_MODELS: dict[str, str] = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "grok": "grok-3",
}

DEFAULT_AGENT_MODELS: dict[str, str] = {
    "claude": "claude-opus-4-6",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
}

ALL_PROVIDERS = ["claude", "openai", "gemini", "grok"]


class Prompter(Protocol):
    def checkbox(self, *, message: str, choices: list[str], defaults: list[str]) -> list[str]: ...
    def password(self, *, message: str, default: str) -> str: ...
    def select(self, *, message: str, choices: list[str], default: str | None) -> str: ...
    def confirm(self, *, message: str, default: bool) -> bool: ...
    def text(self, *, message: str, default: str) -> str: ...


class QuestionaryPrompter:
    """Real interactive prompter using questionary."""

    def checkbox(self, *, message: str, choices: list[str], defaults: list[str]) -> list[str]:
        import questionary
        choice_objects = [
            questionary.Choice(title=c, checked=c in defaults) for c in choices
        ]
        return questionary.checkbox(message=message, choices=choice_objects).ask() or []

    def password(self, *, message: str, default: str) -> str:
        import questionary
        return questionary.password(message=message, default=default).ask() or ""

    def select(self, *, message: str, choices: list[str], default: str | None) -> str:
        import questionary
        return questionary.select(message=message, choices=choices, default=default).ask() or choices[0]

    def confirm(self, *, message: str, default: bool) -> bool:
        import questionary
        return questionary.confirm(message=message, default=default).ask()

    def text(self, *, message: str, default: str) -> str:
        import questionary
        return questionary.text(message=message, default=default).ask() or ""


class FixedPrompter:
    """Deterministic prompter for testing — returns predetermined answers."""

    def __init__(self, *, answers: dict[str, str | list[str] | bool]):
        self._answers = answers
        self._call_log: list[tuple[str, str]] = []

    @property
    def call_log(self) -> list[tuple[str, str]]:
        return self._call_log

    def _get(self, *, message: str, default=None):
        self._call_log.append(("prompt", message))
        for key, value in self._answers.items():
            if key in message:
                return value
        return default

    def checkbox(self, *, message: str, choices: list[str], defaults: list[str]) -> list[str]:
        result = self._get(message=message, default=defaults)
        return result if isinstance(result, list) else defaults

    def password(self, *, message: str, default: str) -> str:
        result = self._get(message=message, default=default)
        return result if isinstance(result, str) else default

    def select(self, *, message: str, choices: list[str], default: str | None) -> str:
        result = self._get(message=message, default=default or choices[0])
        return result if isinstance(result, str) else (default or choices[0])

    def confirm(self, *, message: str, default: bool) -> bool:
        result = self._get(message=message, default=default)
        return result if isinstance(result, bool) else default

    def text(self, *, message: str, default: str) -> str:
        result = self._get(message=message, default=default)
        return result if isinstance(result, str) else default


CURATED_MODELS: dict[str, list[str]] = {
    "claude": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
    "openai": ["gpt-4o-mini", "gpt-4o", "chatgpt-4o-latest", "codex-mini-latest"],
    "gemini": ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    "grok": ["grok-4", "grok-3", "grok-3-fast-latest"],
}

OTHER_OPTION = "Other (enter manually)"


def _get_model_choices(*, provider_name: str) -> list[str]:
    """Get a curated list of model choices for a provider."""
    models = list(CURATED_MODELS.get(provider_name, []))
    default = DEFAULT_MODELS.get(provider_name, "")
    if default and default not in models:
        models.insert(0, default)
    models.append(OTHER_OPTION)
    return models


def _select_model(*, prompter: Prompter, provider_name: str, message: str, existing: str | None, default: str) -> str:
    """Select a model from curated list, with option to enter manually."""
    choices = _get_model_choices(provider_name=provider_name)
    preselect = existing if existing and existing in choices else (default if default in choices else None)

    selected = prompter.select(message=message, choices=choices, default=preselect)

    if selected == OTHER_OPTION:
        selected = prompter.text(
            message=f"Enter the {provider_name} model name:",
            default=existing or default,
        )

    return selected


def _validate_model(*, provider_name: str, api_key: str, model: str) -> str | None:
    """Validate a model works by making a test API call. Returns None on success, error message on failure."""
    import asyncio
    from count_tokens.providers import get_provider
    try:
        provider = get_provider(name=provider_name, api_key=api_key)
        asyncio.run(provider.count_tokens(content=b"hello", mime_type="text/plain", model=model))
        return None
    except Exception as exc:
        return str(exc)


def gather_config(*, prompter: Prompter, existing: Config | None = None, skip_validation: bool = False) -> Config | None:
    """Gather configuration from user via the prompter interface. Returns None if no providers selected."""
    existing_providers = list(existing.providers.keys()) if existing else []

    selected = prompter.checkbox(
        message="Which providers do you use?",
        choices=ALL_PROVIDERS,
        defaults=existing_providers,
    )

    if not selected:
        return None

    providers: dict[str, ProviderConfig] = {}
    for name in selected:
        existing_pc = existing.providers.get(name) if existing else None
        env_key = PROVIDER_ENV_KEYS.get(name, "")

        api_key = prompter.password(
            message=f"Enter your {name} API key ({env_key}):",
            default=existing_pc.api_key if existing_pc else "",
        )

        plan_labels = [p[0] for p in PLAN_OPTIONS[name]]
        plan_keys = [p[1] for p in PLAN_OPTIONS[name]]
        plan_label = prompter.select(
            message=f"What {name} plan are you on?",
            choices=plan_labels,
            default=plan_labels[plan_keys.index(existing_pc.plan)] if existing_pc and existing_pc.plan in plan_keys else None,
        )
        plan_key = plan_keys[plan_labels.index(plan_label)]

        has_agent = False
        agent_model = None
        if name != "grok":
            has_agent = prompter.confirm(
                message=f"Do you have access to {name}'s coding agent?",
                default=existing_pc.has_coding_agent if existing_pc else True,
            )
            if has_agent:
                agent_model = _select_model(
                    prompter=prompter, provider_name=name,
                    message=f"Which model does your {name} coding agent use?",
                    existing=existing_pc.agent_model if existing_pc and existing_pc.agent_model else None,
                    default=DEFAULT_AGENT_MODELS.get(name, ""),
                )

        api_model = _select_model(
            prompter=prompter, provider_name=name,
            message=f"Which {name} model for the API?",
            existing=existing_pc.model if existing_pc else None,
            default=DEFAULT_MODELS.get(name, ""),
        )

        if not skip_validation and api_key:
            error = _validate_model(provider_name=name, api_key=api_key, model=api_model)
            if error:
                from rich.console import Console
                Console().print(f"[yellow]Warning: model '{api_model}' validation failed: {error}[/yellow]")

        providers[name] = ProviderConfig(
            api_key=api_key,
            model=api_model,
            agent_model=agent_model,
            plan=plan_key,
            has_coding_agent=has_agent,
        )

    default_provider = prompter.select(
        message="Set your default provider:",
        choices=selected,
        default=existing.default_provider if existing and existing.default_provider in selected else None,
    )

    return Config(default_provider=default_provider, providers=providers)


def run_setup(*, prompter: Prompter | None = None, skip_validation: bool = False) -> None:
    """Run the setup wizard. Uses QuestionaryPrompter if no prompter provided."""
    if prompter is None:
        prompter = QuestionaryPrompter()

    existing = load_config()
    config = gather_config(prompter=prompter, existing=existing, skip_validation=skip_validation)

    if config is None:
        return

    save_config(config=config)
