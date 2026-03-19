# Test Scenarios: Triumvirate LLM Bot v2.2

Generated: {{DATE}}
Status: DRAFT / UNDER REVIEW / APPROVED
Total estimated tests: {{N}}

---

## Module: `notation_converter.py`

### Public Interface

| Function/Method          | Signature                                    | Description                      |
|--------------------------|----------------------------------------------|----------------------------------|
| `to_triumvirate`         | `(server_notation: str) -> str`              | Server -> Triumvirate notation   |
| `to_server`              | `(tri_notation: str) -> str`                 | Triumvirate -> Server notation   |
| `convert_legal_moves`    | `(legal: dict) -> dict`                      | Batch convert legal moves        |
| `convert_legal_moves_back` | `(tri_legal: dict) -> dict`                | Reverse batch convert            |
| `convert_board`          | `(board: list[dict]) -> list[dict]`          | Add tri_notation to pieces       |
| `convert_move_back`      | `(tri_from, tri_to) -> (str, str)`           | Single move reverse convert      |

### Scenarios

#### Happy Path
- [ ] `test_to_triumvirate_known_cells` — parametrize 10+ known pairs
- [ ] `test_to_server_known_cells` — reverse of above
- [ ] `test_convert_legal_moves_simple` — dict of moves converted correctly
- [ ] `test_convert_board_adds_tri_notation` — each piece gets tri_notation field

#### Edge Cases
- [ ] `test_to_triumvirate_center_cells` — C/W.B, C/W.R etc (special center logic)
- [ ] `test_to_triumvirate_case_insensitive` — "a1" == "A1"
- [ ] `test_to_triumvirate_whitespace` — " A1 " trimmed
- [ ] `test_convert_board_missing_notation` — piece without notation field
- [ ] `test_convert_board_empty_list` — empty board returns empty list
- [ ] `test_convert_legal_moves_empty` — empty dict returns empty dict

#### Error Paths
- [ ] `test_to_triumvirate_invalid_raises_keyerror` — "Z99"
- [ ] `test_to_server_invalid_raises_keyerror` — "X1/Y2.3"

#### Property-Based (Hypothesis)
- [ ] `test_roundtrip_all_96_cells` — to_server(to_triumvirate(x)) == x
- [ ] `test_reverse_roundtrip_all_96` — to_triumvirate(to_server(x)) == x
- [ ] `test_lookup_tables_bijective` — |S2T| == |T2S| == 96, sets match
- [ ] `test_convert_legal_moves_roundtrip` — back(convert(m)) == m

---

## Module: `move_parser.py`

### Public Interface

| Function/Method            | Signature                                                    |
|----------------------------|--------------------------------------------------------------|
| `MoveParser.parse`         | `(text, legal, fmt, triumvirate=False) -> tuple | None`     |
| `_sanitize_json_string`    | `(raw: str) -> str`                                          |

### Scenarios

#### Happy Path — JSON format
- [ ] `test_parse_json_with_move_from_to` — standard JSON response
- [ ] `test_parse_json_thinking_ignores_thinking` — thinking field not parsed
- [ ] `test_parse_json_with_legacy_keys` — "from"/"to" instead of "move_from"/"move_to"
- [ ] `test_parse_json_with_promotion` — promotion field parsed correctly

#### Happy Path — Simple format
- [ ] `test_parse_simple_two_coords` — "A2 A3" extracted
- [ ] `test_parse_simple_with_promotion` — "A7 A8 =Q" extracts promotion
- [ ] `test_parse_simple_coords_in_text` — "I think A2 to A3" finds coords

#### Happy Path — Triumvirate
- [ ] `test_parse_json_triumvirate` — Triumvirate coords in JSON
- [ ] `test_parse_simple_triumvirate` — Triumvirate coords in text

#### Edge Cases — _sanitize_json_string
- [ ] `test_sanitize_strips_markdown_fences` — ```json ... ```
- [ ] `test_sanitize_escapes_control_chars` — \x00-\x1f inside strings
- [ ] `test_sanitize_escapes_newlines_in_strings` — literal \n -> \\n
- [ ] `test_sanitize_handles_escaped_quotes` — doesn't break on \"
- [ ] `test_sanitize_empty_string` — returns empty
- [ ] `test_sanitize_valid_json_unchanged` — valid JSON passes through

#### Edge Cases — Parse
- [ ] `test_parse_strips_piece_prefix` — "NE2" -> "E2"
- [ ] `test_parse_strips_piece_prefix_tri` — "PW3/B2.0" -> "W3/B2.0"
- [ ] `test_parse_strips_piece_prefix_tri_with_colon` — "L:W3/R3.3" -> "W3/R3.3"
- [ ] `test_parse_json_no_braces` — no { } in response -> None
- [ ] `test_parse_json_invalid_json` — broken JSON -> None
- [ ] `test_parse_json_missing_keys` — JSON without move_from/move_to -> None
- [ ] `test_parse_illegal_move` — coords exist but not in legal -> None
- [ ] `test_parse_same_coords` — "A2 A2" (same from/to) -> skip pair
- [ ] `test_parse_empty_text` — "" -> None
- [ ] `test_norm_promo_triumvirate_names` — "marshal"->"queen", "noctis"->"knight"

#### Property-Based
- [ ] `test_parse_never_crashes_on_arbitrary_text` — Hypothesis text
- [ ] `test_parse_result_always_in_legal` — if not None, move is legal
- [ ] `test_sanitize_never_crashes` — arbitrary bytes -> no exception
- [ ] `test_sanitize_idempotent` — sanitize(sanitize(x)) == sanitize(x)

---

## Module: `constants.py`

### Scenarios
- [ ] `test_make_bot_name_standard` — known provider/model pairs
- [ ] `test_make_bot_name_truncation` — name > 80 chars truncated
- [ ] `test_make_bot_name_empty_model` — model="" -> "unknown"
- [ ] `test_make_bot_name_unknown_provider` — uses first word
- [ ] `test_make_bot_name_spaces_in_model` — spaces replaced with hyphens
- [ ] `test_providers_dict_structure` — all required keys present
- [ ] `test_provider_env_key_has_entries` — OpenAI, Anthropic, OpenRouter

---

## Module: `pricing.py`

### Scenarios
- [ ] `test_calc_cost_basic` — known tokens + rates -> expected USD
- [ ] `test_calc_cost_zero_tokens` — all zeros -> all zeros
- [ ] `test_calc_cost_reasoning_at_completion_rate` — reasoning billed as completion
- [ ] `test_extract_usage_openai_format` — standard usage block
- [ ] `test_extract_usage_with_reasoning_tokens` — native_tokens_reasoning
- [ ] `test_extract_usage_with_provider_cost` — total_cost field
- [ ] `test_extract_usage_empty` — no usage block -> zeros
- [ ] `test_fetch_openrouter_success` — respx mock of /api/v1/models
- [ ] `test_fetch_openrouter_model_not_found` — model not in list
- [ ] `test_fetch_openrouter_network_error` — httpx error -> fetch_error
- [ ] `test_fetch_openrouter_empty_model` — model="" -> early return
- [ ] `test_set_zero` — sets not_openrouter source

---

## Module: `settings.py`

### Scenarios
- [ ] `test_settings_defaults` — fresh Settings has all DEFAULTS
- [ ] `test_settings_save_load_roundtrip` — save then reload matches
- [ ] `test_settings_virtual_key_system_prompt` — reads from file
- [ ] `test_settings_virtual_key_user_template` — reads from file
- [ ] `test_settings_api_key_from_env` — falls back to os.environ
- [ ] `test_settings_api_key_from_json` — prefers stored key
- [ ] `test_settings_migrate_legacy_prompts` — inline text -> files
- [ ] `test_settings_blocks_legacy_key_write` — __setitem__ ignores "system_prompt"
- [ ] `test_settings_prompt_file_fallback` — missing file -> _FALLBACK_*
- [ ] `test_get_response_format_from_file` — reads prompts/format_*.txt
- [ ] `test_get_response_format_fallback` — missing file -> DEFAULT_RESPONSE_FORMAT
- [ ] `test_load_dotenv` — .env file loaded into os.environ
- [ ] `test_load_dotenv_does_not_overwrite` — existing env vars preserved

---

## Module: `prompt_builder.py`

### Scenarios
- [ ] `test_build_basic_messages` — returns [system, user] messages
- [ ] `test_build_includes_format_instruction` — OUTPUT FORMAT section present
- [ ] `test_build_with_additional_rules` — rules appended to system
- [ ] `test_build_triumvirate_mode` — tri_legal used instead of server legal
- [ ] `test_build_check_text` — check info formatted correctly
- [ ] `test_build_last_move_text` — last_move formatted
- [ ] `test_build_last_move_none` — "none (game start)"
- [ ] `test_fmt_legal_empty` — returns "(none)"
- [ ] `test_fmt_board_server` — pieces grouped by color
- [ ] `test_fmt_board_tri` — Triumvirate piece symbols (L/M/T/D/N/P)
- [ ] `test_fill_template_double_braces` — {{key}} substitution
- [ ] `test_fill_template_single_braces` — {key} substitution

---

## Module: `llm_client.py`

### Scenarios
- [ ] `test_ask_openai_compat` — respx mock, returns (text, body)
- [ ] `test_ask_anthropic_native` — respx mock, returns (text, body)
- [ ] `test_ask_openai_with_custom_headers` — headers passed through
- [ ] `test_ask_openai_error_status` — 400+ -> RuntimeError
- [ ] `test_ask_anthropic_error_status` — 400+ -> RuntimeError
- [ ] `test_ask_anthropic_extracts_system` — system message separated from user

---

## Module: `arena_client.py`

### Scenarios
- [ ] `test_join_stores_token_game_color` — sets self.token, game_id, color
- [ ] `test_get_state_sends_auth_header` — Authorization: Bearer token
- [ ] `test_make_move_returns_status_data` — (status_code, data) tuple
- [ ] `test_make_move_with_promotion` — promotion in body
- [ ] `test_health_check` — returns dict
- [ ] `test_resign` — respx mock
- [ ] `test_skip_waiting` — respx mock
- [ ] `test_list_games` — returns list

---

## Module: `tracer.py`

### Scenarios
- [ ] `test_init_sets_fields` — game_id, move_number, timestamp
- [ ] `test_add_llm_response_accumulates` — multiple responses tracked
- [ ] `test_finalize_statistics_sums_correctly` — totals match components
- [ ] `test_save_creates_directory_and_file` — game_<id>__<model>/move_NNN.json
- [ ] `test_save_model_name_sanitized` — special chars replaced with _
- [ ] `test_save_empty_data_skipped` — no file written if _data empty
- [ ] `test_full_trace_cycle` — init -> add_* -> finalize -> save -> read JSON

---

## Module: `bot_runner.py` (partial)

### Scenarios
- [ ] `test_detect_openrouter_by_provider` — provider="OpenRouter" -> True
- [ ] `test_detect_openrouter_by_url` — "openrouter.ai" in URL -> True
- [ ] `test_detect_openrouter_false` — other provider -> False
- [ ] `test_choose_move_success` — respx LLM mock -> valid move returned
- [ ] `test_choose_move_retry_on_bad_response` — first bad, then good
- [ ] `test_choose_move_all_retries_exhausted` — returns None
- [ ] `test_choose_move_temperature_escalation` — temp increases per retry
- [ ] `test_stats_updated_after_choose_move` — llm_calls, retries counted
- [ ] `test_start_stop` — start sets _running, stop cancels task

---

## Module: `gui.py`

### Предварительный шаг: Извлечение логики

Перед написанием тестов создать `gui_helpers.py` — извлечь чистые функции
из closures `create_gui()`. Это первый шаг декомпозиции GUI.

### Public Interface (после извлечения в gui_helpers.py)

| Function                      | Извлечено из          | Описание                               |
|-------------------------------|----------------------|-----------------------------------------|
| `format_state_text(state)`    | `_on_state` (62-89)  | State dict -> (state_md, legal_md)     |
| `format_game_list(games)`     | `on_list_games` (300) | Games list -> markdown                 |
| `collect_settings(values)`    | `_collect` (101-131)  | UI values -> settings dict             |
| `apply_provider_preset(prov)` | `_on_provider` (132)  | Provider name -> preset values         |
| `mask_api_key(key)`           | `on_test_llm` (246)   | API key -> masked string               |
| `format_hint(fmt)`            | `_on_fmt` (169-175)   | Format name -> hint string             |

### Scenarios — Extracted Logic (test_gui_logic.py)

#### format_state_text
- [ ] `test_format_state_basic` — move_number, current_player, game_status отображаются
- [ ] `test_format_state_with_check` — check info форматируется с предупреждением
- [ ] `test_format_state_with_last_move` — last_move показывает from->to
- [ ] `test_format_state_no_last_move` — отображается "—"
- [ ] `test_format_state_legal_moves` — каждый src: dsts в markdown
- [ ] `test_format_state_no_legal_moves` — "(нет допустимых ходов)"

#### format_game_list
- [ ] `test_format_game_list_multiple` — несколько игр форматируются
- [ ] `test_format_game_list_empty` — пустой список -> сообщение

#### collect_settings
- [ ] `test_collect_parses_custom_headers_json` — valid JSON -> dict
- [ ] `test_collect_invalid_headers_json` — invalid JSON -> empty dict
- [ ] `test_collect_empty_headers` — empty string -> empty dict
- [ ] `test_collect_api_key_from_env_fallback` — пустой ключ -> env var
- [ ] `test_collect_strips_whitespace` — пробелы в URL, model убираются

#### apply_provider_preset
- [ ] `test_preset_openai` — base_url, model, compat для OpenAI
- [ ] `test_preset_anthropic` — compat=False для Anthropic
- [ ] `test_preset_openrouter` — custom_headers заполнены
- [ ] `test_preset_ollama` — localhost, response_format=simple
- [ ] `test_preset_unknown_provider` — неизвестный провайдер -> без изменений

#### mask_api_key
- [ ] `test_mask_long_key` — "sk-1234567890abcdef" -> "sk-12345...cdef"
- [ ] `test_mask_short_key` — "short" -> "***"
- [ ] `test_mask_empty_key` — "" -> пустая строка или спец.текст

#### format_hint
- [ ] `test_hint_simple` — "Ответ: «E2 E4»"
- [ ] `test_hint_json` — содержит {"from","to"}
- [ ] `test_hint_json_thinking` — содержит {"thinking","from","to"}
- [ ] `test_hint_unknown` — пустая строка

### Scenarios — NiceGUI Screen Tests (test_gui_screens.py)

#### Рендеринг
- [ ] `test_gui_renders_header` — заголовок с версией присутствует
- [ ] `test_gui_renders_all_tabs` — "Игра", "Лог", "Лобби" присутствуют
- [ ] `test_gui_renders_provider_select` — список провайдеров из PROVIDERS

#### Взаимодействие — Провайдер
- [ ] `test_switch_provider_updates_fields` — выбор провайдера меняет base_url, model
- [ ] `test_switch_provider_loads_env_key` — env var API key подгружается

#### Взаимодействие — Кнопки (с respx-моками)
- [ ] `test_start_creates_runner` — после клика runner != None
- [ ] `test_stop_disables_runner` — после клика runner._running == False
- [ ] `test_test_server_ping` — respx мок /health -> UI notification
- [ ] `test_test_llm_sends_request` — respx мок LLM -> лог содержит ответ
- [ ] `test_list_games_shows_lobby` — respx мок /games -> games_md обновляется
- [ ] `test_save_settings_persists` — настройки сохранены в файл

#### Взаимодействие — Промпты
- [ ] `test_reset_prompts_rewrites_files` — файлы промптов содержат fallback текст

---

## Summary

| Module                  | Unit | Integration | Screen | Property | Total |
|-------------------------|------|-------------|--------|----------|-------|
| `notation_converter.py` | 10   | 0           | 0      | 4        | 14    |
| `move_parser.py`        | 18   | 0           | 0      | 4        | 22    |
| `constants.py`          | 7    | 0           | 0      | 0        | 7     |
| `pricing.py`            | 5    | 4           | 0      | 1        | 10    |
| `settings.py`           | 0    | 13          | 0      | 0        | 13    |
| `prompt_builder.py`     | 0    | 12          | 0      | 0        | 12    |
| `tracer.py`             | 0    | 7           | 0      | 0        | 7     |
| `llm_client.py`         | 0    | 6           | 0      | 0        | 6     |
| `arena_client.py`       | 0    | 8           | 0      | 0        | 8     |
| `bot_runner.py`         | 3    | 6           | 0      | 0        | 9     |
| `gui.py`                | 18   | 0           | 13     | 0        | 31    |
| **TOTAL**               | 61   | 56          | 13     | 9        | **139** |
