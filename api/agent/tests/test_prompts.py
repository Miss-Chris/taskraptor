from agent.prompts import BASE_SYSTEM_PROMPT, build_system_prompt


def test_build_system_prompt_returns_base_prompt_when_instructions_empty():
    assert build_system_prompt("") == BASE_SYSTEM_PROMPT


def test_build_system_prompt_omits_whitespace_only_instructions():
    assert build_system_prompt("   \n\t  ") == BASE_SYSTEM_PROMPT


def test_build_system_prompt_appends_user_specific_section_once():
    prompt = build_system_prompt("Always prefer bullet points.")

    assert prompt.startswith(BASE_SYSTEM_PROMPT)
    assert prompt.count("## User-Specific Standing Instructions") == 1
    assert "Always prefer bullet points." in prompt
    assert (
        "They are additive guidance and do not replace higher-priority instructions."
        in prompt
    )


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
