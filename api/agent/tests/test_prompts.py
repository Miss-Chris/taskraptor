from agent.prompts import BASE_SYSTEM_PROMPT, build_system_prompt


def test_build_system_prompt_returns_base_prompt_when_instructions_empty():
    prompt = build_system_prompt("")
    assert prompt.startswith(BASE_SYSTEM_PROMPT)
    assert "## Persona" in prompt


def test_base_system_prompt_guides_plain_text_chat_responses():
    assert "## Response Style" in BASE_SYSTEM_PROMPT
    assert "plain-text chat interface such as Telegram" in BASE_SYSTEM_PROMPT
    assert "Do not default to Markdown structure" in BASE_SYSTEM_PROMPT
    assert "For simple task confirmations, answer in one short sentence" in BASE_SYSTEM_PROMPT


def test_build_system_prompt_omits_whitespace_only_instructions():
    prompt = build_system_prompt("   \n\t  ")
    assert prompt.startswith(BASE_SYSTEM_PROMPT)
    assert "## User-Specific Standing Instructions" not in prompt


def test_build_system_prompt_appends_user_specific_section_once():
    prompt = build_system_prompt("Always prefer bullet points.")

    assert prompt.startswith(BASE_SYSTEM_PROMPT)
    assert prompt.count("## User-Specific Standing Instructions") == 1
    assert "Always prefer bullet points." in prompt
    assert (
        "They are additive guidance and do not replace higher-priority instructions."
        in prompt
    )


def test_build_system_prompt_includes_helpful_persona_by_default():
    prompt = build_system_prompt("")

    assert "## Persona" in prompt
    assert "professional and friendly tone" in prompt


def test_build_system_prompt_includes_encouraging_persona():
    prompt = build_system_prompt("", persona="encouraging")

    assert "warm, encouraging tone" in prompt


def test_build_system_prompt_includes_minimal_persona():
    prompt = build_system_prompt("", persona="minimal")

    assert "dry, minimal tone" in prompt


def test_build_system_prompt_uses_custom_persona_instead_of_preset():
    prompt = build_system_prompt(
        "",
        persona="custom",
        custom_persona="Use clipped sentences.",
    )

    assert "Use clipped sentences." in prompt
    assert "professional and friendly tone" not in prompt


def test_build_system_prompt_includes_user_local_time_context():
    prompt = build_system_prompt(
        "",
        timezone="America/Toronto",
        local_now="2026-04-10T09:30:00-04:00",
        local_date="2026-04-10",
    )

    assert "## User Local Time Context" in prompt
    assert "timezone: America/Toronto" in prompt
    assert "local_now: 2026-04-10T09:30:00-04:00" in prompt
    assert "local_date: 2026-04-10" in prompt
    assert "backend tools handle timezone conversion" in prompt


def test_build_system_prompt_includes_top_tag_guidance():
    prompt = build_system_prompt("", top_tags=["work", "finance"])

    assert "## Tag Guidance" in prompt
    assert "Prefer reusing these existing top tags" in prompt
    assert "- work" in prompt
    assert "- finance" in prompt
    assert "Create a new short lowercase tag only when none of these fit." in prompt
    assert "Avoid over-tagging" in prompt
