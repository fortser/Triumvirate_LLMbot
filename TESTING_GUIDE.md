# Отчёт: тестовое покрытие Triumvirate LLM Bot v2.2

## Итоги

| Метрика | Значение |
|---------|----------|
| Тестов всего | **250** |
| Проходят | **250 (100%)** |
| Покрытие кода | **79.2%** (без gui.py) |
| Время прогона | ~7 сек |
| Зависимости | pytest, pytest-asyncio, respx, hypothesis |

---

## Созданные файлы (23 шт.)

### Инфраструктура (5 файлов)

| Файл | Назначение |
|------|-----------|
| `tests/__init__.py` | Пакет тестов |
| `tests/unit/__init__.py` | Пакет юнит-тестов |
| `tests/integration/__init__.py` | Пакет интеграционных тестов |
| `tests/property/__init__.py` | Пакет property-based тестов |
| `tests/conftest.py` | Фикстуры: sample_state, sample_legal_moves, sample_board, settings_factory, pricing_manager |

### Новый модуль (1 файл)

| Файл | Строк | Назначение |
|------|-------|-----------|
| `gui_helpers.py` | 77 | Чистые функции из gui.py: format_state_text, format_game_list, collect_settings, apply_provider_preset, mask_api_key, format_hint |

### Изменённые файлы (1 файл)

| Файл | Изменение |
|------|-----------|
| `pyproject.toml` | gui.py добавлен в omit покрытия; порог: 75% |

### Тестовые файлы (16 файлов)

| # | Файл | Тестов |
|---|------|--------|
| 1 | `tests/unit/test_constants.py` | 19 |
| 2 | `tests/unit/test_notation_converter.py` | 31 |
| 3 | `tests/unit/test_sanitize_json.py` | 10 |
| 4 | `tests/unit/test_move_parser.py` | 31 |
| 5 | `tests/unit/test_pricing_calc.py` | 12 |
| 6 | `tests/property/test_notation_roundtrip.py` | 4 |
| 7 | `tests/property/test_parser_fuzzing.py` | 2 |
| 8 | `tests/property/test_sanitize_json_fuzzing.py` | 2 |
| 9 | `tests/integration/test_settings.py` | 23 |
| 10 | `tests/integration/test_prompt_builder.py` | 21 |
| 11 | `tests/integration/test_tracer.py` | 11 |
| 12 | `tests/integration/test_llm_client.py` | 14 |
| 13 | `tests/integration/test_arena_client.py` | 12 |
| 14 | `tests/integration/test_pricing_fetch.py` | 12 |
| 15 | `tests/integration/test_bot_runner.py` | 15 |
| 16 | `tests/integration/test_gui_logic.py` | 24 |
| 17 | `tests/integration/test_gui_screens.py` | 7 |

---

## Все тесты (250 шт.)

### tests/unit/test_constants.py — 19 тестов

| Тест | Проверяет |
|------|-----------|
| `test_make_bot_name_standard[Ollama]` | LLM_Ollama_llama3.2 |
| `test_make_bot_name_standard[OpenAI]` | LLM_OpenAI_gpt-4o-mini |
| `test_make_bot_name_standard[Anthropic]` | LLM_Anthropic_claude-... |
| `test_make_bot_name_standard[OpenRouter]` | LLM_OpenRouter_openai/gpt-4.1-nano |
| `test_make_bot_name_standard[LM Studio]` | LLM_LMStudio_qwen2.5-7b |
| `test_make_bot_name_standard[Кастомный URL]` | LLM_Custom_my-model |
| `test_make_bot_name_truncation` | Модель 80+ символов → len ≤ 80 |
| `test_make_bot_name_empty_model` | model="" → "_unknown" |
| `test_make_bot_name_unknown_provider` | "Some Provider" → "LLM_Some_" |
| `test_make_bot_name_spaces_in_model` | "my model" → "my-model" |
| `test_make_bot_name_never_exceeds_80[0]` | Длинная модель OpenRouter |
| `test_make_bot_name_never_exceeds_80[1]` | Длинный путь модели |
| `test_make_bot_name_never_exceeds_80[2]` | Модель с пробелами |
| `test_providers_dict_structure` | Все провайдеры имеют base_url, api_key, model, compat, response_format |
| `test_provider_env_key_known[OpenAI]` | OPENAI_API_KEY |
| `test_provider_env_key_known[Anthropic]` | ANTHROPIC_API_KEY |
| `test_provider_env_key_known[OpenRouter]` | OPENROUTER_API_KEY |
| `test_provider_short_covers_all` | Все PROVIDERS в _PROVIDER_SHORT |
| `test_version_format` | VERSION = r"\d+\.\d+\.\d+" |

### tests/unit/test_notation_converter.py — 31 тест

| Тест | Проверяет |
|------|-----------|
| `test_to_triumvirate_known_cells[A1]` | A1 → W3/B3.0 |
| `test_to_triumvirate_known_cells[A2]` | A2 → W3/B2.0 |
| `test_to_triumvirate_known_cells[A3]` | A3 → W3/B1.0 |
| `test_to_triumvirate_known_cells[A4]` | A4 → W3/B0.0 |
| `test_to_triumvirate_known_cells[D1]` | D1 → W3/B3.3 |
| `test_to_triumvirate_known_cells[D4]` | D4 → C/W.B |
| `test_to_triumvirate_known_cells[E4]` | E4 → C/W.R |
| `test_to_triumvirate_known_cells[H1]` | H1 → W3/R3.0 |
| `test_to_triumvirate_known_cells[A8]` | A8 → B3/R3.0 |
| `test_to_triumvirate_known_cells[I5]` | I5 → C/B.W |
| `test_to_triumvirate_known_cells[L12]` | L12 → R3/B3.0 |
| `test_to_triumvirate_known_cells[H12]` | H12 → R3/W3.0 |
| `test_to_server_known_cells[A1]` | W3/B3.0 → A1 |
| `test_to_server_known_cells[D4]` | C/W.B → D4 |
| `test_to_server_known_cells[E4]` | C/W.R → E4 |
| `test_to_server_known_cells[A8]` | B3/R3.0 → A8 |
| `test_to_server_known_cells[L12]` | R3/B3.0 → L12 |
| `test_convert_legal_moves_simple` | Конвертация dict легальных ходов |
| `test_convert_legal_moves_back_simple` | Обратная конвертация → исходный dict |
| `test_convert_board_adds_tri_notation` | Фигуре добавляется tri_notation |
| `test_convert_move_back` | Пара tri → серверные координаты |
| `test_to_triumvirate_center_cells_both` | D4 ≠ E4 (разные центральные ячейки) |
| `test_to_triumvirate_case_insensitive` | "a1" = "A1" |
| `test_to_triumvirate_whitespace` | " A1 " → "A1" |
| `test_convert_board_empty_list` | [] → [] |
| `test_convert_legal_moves_empty` | {} → {} |
| `test_convert_board_does_not_mutate_original` | Оригинал не изменяется |
| `test_convert_board_piece_without_notation` | Без notation → без tri_notation |
| `test_to_triumvirate_invalid_raises_keyerror` | "Z99" → KeyError |
| `test_to_server_invalid_raises_keyerror` | "X1/Y2.3" → KeyError |
| `test_convert_board_invalid_notation_keeps_original` | "Z99" → tri_notation="Z99" |

### tests/unit/test_sanitize_json.py — 10 тестов

| Тест | Проверяет |
|------|-----------|
| `test_sanitize_strips_markdown_fences` | \`\`\`json ... \`\`\` → чистый JSON |
| `test_sanitize_strips_markdown_fences_no_lang_tag` | \`\`\` ... \`\`\` без тега языка |
| `test_sanitize_escapes_control_chars` | \x00 → \u0000 |
| `test_sanitize_escapes_newlines_in_strings` | \n внутри строки → \\n |
| `test_sanitize_escapes_tabs_in_strings` | \t внутри строки → \\t |
| `test_sanitize_escapes_carriage_return` | \r внутри строки → \\r |
| `test_sanitize_handles_escaped_quotes` | \" не ломает парсинг |
| `test_sanitize_empty_string` | "" → "" |
| `test_sanitize_valid_json_unchanged` | Валидный JSON проходит без изменений |
| `test_sanitize_no_newline_outside_strings` | \n вне строк сохраняется |

### tests/unit/test_move_parser.py — 31 тест

| Тест | Проверяет |
|------|-----------|
| `test_parser_extracts_move_from_standard_json` | JSON {"move_from","move_to"} |
| `test_parser_extracts_move_from_json_with_thinking` | JSON с полем thinking |
| `test_parser_extracts_move_from_legacy_keys` | Legacy {"from","to"} |
| `test_parser_extracts_promotion_from_json` | promotion в JSON |
| `test_parser_handles_markdown_fences_json` | \`\`\`json обёртка |
| `test_parser_extracts_move_from_simple_two_coords` | "A2 A4" → (A2, A4) |
| `test_parser_extracts_promotion_from_simple` | "A7 A8 =Q" → queen |
| `test_parser_extracts_coords_in_text` | Координаты внутри текста |
| `test_parser_skips_illegal_simple` | Нелегальный ход пропускается |
| `test_parser_extracts_tri_json` | Triumvirate JSON |
| `test_parser_extracts_tri_simple` | Triumvirate simple |
| `test_parser_strips_piece_prefix_server[N]` | NE2 → E2 |
| `test_parser_strips_piece_prefix_server[B]` | BE2 → E2 |
| `test_parser_strips_piece_prefix_server[R]` | RE2 → E2 |
| `test_parser_strips_piece_prefix_server[Q]` | QE2 → E2 |
| `test_parser_strips_piece_prefix_server[K]` | KE2 → E2 |
| `test_parser_strips_piece_prefix_server[P]` | PE2 → E2 |
| `test_parser_strips_tri_prefix_with_colon` | P:W3/B2.0 → W3/B2.0 |
| `test_parser_strips_tri_prefix_without_colon` | PW3/B2.0 → W3/B2.0 |
| `test_parser_tri_prefix_ambiguous_wbr_not_stripped` | W/B/R не удаляются |
| `test_parser_no_braces_returns_none` | Нет {} → None |
| `test_parser_invalid_json_returns_none` | Невалидный JSON → None |
| `test_parser_missing_keys_returns_none` | Нет move_from/to → None |
| `test_parser_illegal_move_returns_none` | Нелегальный ход → None |
| `test_parser_same_coords_skipped` | A2 A2 → пропуск |
| `test_parser_empty_text_returns_none` | "" → None |
| `test_parser_case_insensitive` | "a2" = "A2" |
| `test_promotion_standard_names` | queen/rook/bishop/knight |
| `test_promotion_single_letter` | q/r/b/n |
| `test_promotion_triumvirate_names` | marshal/train/drone/noctis |
| `test_promotion_none_and_unknown` | None → None, "xyz" → None |

### tests/unit/test_pricing_calc.py — 12 тестов

| Тест | Проверяет |
|------|-----------|
| `test_calc_cost_basic` | 1000 prompt + 500 completion → $0.0105 |
| `test_calc_cost_zero_tokens` | Все нули → $0 |
| `test_calc_cost_reasoning_at_completion_rate` | reasoning × completion_rate |
| `test_calc_cost_total_equals_sum` | total = input + output + reasoning |
| `test_calc_cost_all_values_non_negative[0,0,0]` | Неотрицательность |
| `test_calc_cost_all_values_non_negative[1,0,0]` | Неотрицательность |
| `test_calc_cost_all_values_non_negative[0,1,0]` | Неотрицательность |
| `test_calc_cost_all_values_non_negative[0,0,1]` | Неотрицательность |
| `test_calc_cost_all_values_non_negative[1M,1M,1M]` | Неотрицательность |
| `test_set_zero` | source="not_openrouter", pricing=0 |
| `test_is_loaded_initially_false` | is_loaded = False |
| `test_is_loaded_after_set_zero` | is_loaded = True |

### tests/property/test_notation_roundtrip.py — 4 теста

| Тест | Проверяет |
|------|-----------|
| `test_roundtrip_all_96_cells` | to_server(to_triumvirate(x)) == x ∀96 |
| `test_reverse_roundtrip_all_96` | to_triumvirate(to_server(x)) == x ∀96 |
| `test_lookup_tables_bijective` | len=96, множества совпадают |
| `test_convert_legal_moves_roundtrip` | Roundtrip dict ходов |

### tests/property/test_parser_fuzzing.py — 2 теста

| Тест | Проверяет |
|------|-----------|
| `test_parse_never_crashes_on_arbitrary_text` | 200 рандомных строк → без исключений |
| `test_parse_result_always_in_legal` | Результат ∈ legal_moves |

### tests/property/test_sanitize_json_fuzzing.py — 2 теста

| Тест | Проверяет |
|------|-----------|
| `test_sanitize_never_crashes` | 200 рандомных строк → без исключений |
| `test_sanitize_idempotent` | sanitize(sanitize(x)) == sanitize(x) |

### tests/integration/test_settings.py — 23 теста

| Тест | Проверяет |
|------|-----------|
| `test_settings_defaults` | Дефолтные значения |
| `test_settings_save_load_roundtrip` | Сохранение → загрузка |
| `test_settings_save_excludes_legacy_keys` | system_prompt/user_template не в JSON |
| `test_settings_system_prompt_reads_file` | Чтение из prompts/system_prompt.txt |
| `test_settings_user_template_reads_file` | Чтение из prompts/user_prompt_template.txt |
| `test_settings_system_prompt_fallback_when_missing` | Fallback при отсутствии файла |
| `test_settings_system_prompt_fallback_when_empty` | Fallback при пустом файле |
| `test_settings_api_key_from_json` | Ключ из JSON |
| `test_settings_api_key_from_env` | Ключ из env OPENAI_API_KEY |
| `test_settings_api_key_no_env_mapping` | Ollama → без env-маппинга |
| `test_settings_legacy_key_write_ignored` | s["system_prompt"] = ... игнорируется |
| `test_settings_migrates_legacy_system_prompt` | system_prompt → файл + *_file ключ |
| `test_settings_migrates_legacy_user_template` | user_template → файл + *_file ключ |
| `test_response_format_from_file` | Формат из prompts/format_json.txt |
| `test_response_format_fallback_known` | simple → hardcoded fallback |
| `test_response_format_fallback_unknown` | unknown → json_thinking fallback |
| `test_dotenv_sets_vars` | .env → os.environ |
| `test_dotenv_doesnt_overwrite` | Не перезаписывает существующие |
| `test_dotenv_ignores_comments` | # строки пропускаются |
| `test_dotenv_strips_quotes` | "value" → value |
| `test_dotenv_nonexistent_file` | Несуществующий .env → без ошибки |
| `test_system_prompt_path_is_absolute` | Абсолютный путь |
| `test_user_template_path_is_absolute` | Абсолютный путь |

### tests/integration/test_prompt_builder.py — 21 тест

| Тест | Проверяет |
|------|-----------|
| `test_build_returns_system_and_user` | 2 сообщения: system + user |
| `test_build_includes_output_format` | "OUTPUT FORMAT" в system |
| `test_build_includes_additional_rules` | "ADDITIONAL RULES" в system |
| `test_build_last_move_text` | E7 → E5 в user |
| `test_build_last_move_with_type` | (capture) в user |
| `test_build_last_move_none` | "none (game start)" |
| `test_build_check_from_check_field` | CHECK из check.is_check |
| `test_build_check_from_player_status` | CHECK из player.status="in_check" |
| `test_build_no_check` | Нет CHECK в тексте |
| `test_build_with_tri_legal` | Triumvirate координаты в user |
| `test_build_with_tri_last_move` | Triumvirate last_move |
| `test_build_with_tri_board` | Triumvirate board |
| `test_fmt_legal_empty` | {} → "(none)" |
| `test_fmt_legal_sorted` | Сортировка по ключам |
| `test_fmt_board_grouped` | Группировка по цветам + ← YOU |
| `test_fmt_board_captured` | Захваченная фигура (owner≠color) |
| `test_fmt_board_tri_symbols` | KING → L (Leader) |
| `test_fmt_board_empty` | [] → "" |
| `test_fill_template_double_braces` | {{name}} → World |
| `test_fill_template_single_braces` | {name} → World |
| `test_fill_template_missing_key` | {{unknown}} остаётся |

### tests/integration/test_tracer.py — 11 тестов

| Тест | Проверяет |
|------|-----------|
| `test_init_sets_fields` | game_id, move_number, model |
| `test_init_sanitizes_model_name` | Спецсимволы → _ |
| `test_add_llm_response_accumulates` | 2 ответа → len=2 |
| `test_add_llm_response_with_usage_and_cost` | usage/cost в entry |
| `test_finalize_statistics_sums_correctly` | Суммирование токенов |
| `test_finalize_statistics_retries_count` | 3 вызова → retries=2 |
| `test_finalize_statistics_provider_cost_accumulates` | 0.005+0.003=0.008 |
| `test_finalize_statistics_provider_cost_none` | Нет cost → None |
| `test_save_creates_dir_and_file` | game_abc-123__model/move_005.json |
| `test_save_empty_data_skipped` | Пустой data → нет файлов |
| `test_full_trace_cycle` | Полный цикл: init→...→save |

### tests/integration/test_llm_client.py — 14 тестов

| Тест | Проверяет |
|------|-----------|
| `test_openai_returns_text_and_body` | text="Hello!", usage в body |
| `test_openai_correct_payload` | model, temperature, max_tokens, messages |
| `test_openai_auth_header` | Authorization: Bearer sk-... |
| `test_openai_no_auth_when_empty` | Пустой ключ → нет заголовка |
| `test_openai_custom_headers` | X-Title: Bot |
| `test_openai_error_status[400]` | RuntimeError с кодом 400 |
| `test_openai_error_status[429]` | RuntimeError с кодом 429 |
| `test_openai_error_status[500]` | RuntimeError с кодом 500 |
| `test_openai_error_json_detail` | "invalid model" в сообщении |
| `test_anthropic_returns_text_and_body` | text="Hi there" |
| `test_anthropic_extracts_system_message` | system в body, не в messages |
| `test_anthropic_api_key_header` | x-api-key: sk-ant-key |
| `test_anthropic_error_status[400]` | RuntimeError |
| `test_anthropic_error_status[500]` | RuntimeError |

### tests/integration/test_arena_client.py — 12 тестов

| Тест | Проверяет |
|------|-----------|
| `test_constructor_builds_url` | server/api/v1 |
| `test_constructor_strips_trailing_slash` | Нет двойного / |
| `test_join_stores_token_game_id_color` | token, game_id, color |
| `test_join_with_model` | model в payload |
| `test_get_state_sends_auth_header` | Authorization: Bearer |
| `test_make_move_returns_status_and_data` | (200, {...}) |
| `test_make_move_with_promotion` | promotion в payload |
| `test_make_move_non_json_response` | 500 → text как data |
| `test_health_returns_dict` | {status, active_games} |
| `test_resign_correct_endpoint` | /api/v1/resign |
| `test_skip_waiting_correct_endpoint` | /api/v1/skip-waiting |
| `test_list_games_returns_list` | [{game_id, players}] |

### tests/integration/test_pricing_fetch.py — 12 тестов

| Тест | Проверяет |
|------|-----------|
| `test_fetch_success_converts_to_per_1m` | 0.000003 → 3.0 per 1M |
| `test_fetch_model_not_found` | source=openrouter_model_not_found |
| `test_fetch_network_error` | source=openrouter_fetch_error |
| `test_fetch_empty_model` | Ранний возврат, source=none |
| `test_extract_usage_openai_format` | prompt/completion/total |
| `test_extract_usage_native_reasoning_openrouter` | native_tokens_reasoning |
| `test_extract_usage_completion_details_reasoning` | completion_tokens_details |
| `test_extract_usage_reasoning_ignored_non_openrouter` | reasoning=0 без OpenRouter |
| `test_extract_usage_provider_cost_in_usage` | total_cost в usage |
| `test_extract_usage_provider_cost_top_level` | total_cost в корне |
| `test_extract_usage_empty` | {} → все нули |
| `test_extract_usage_total_tokens_fallback` | prompt+completion |

### tests/integration/test_bot_runner.py — 15 тестов

| Тест | Проверяет |
|------|-----------|
| `test_detect_openrouter_by_provider` | provider="OpenRouter" → True |
| `test_detect_openrouter_by_url` | "openrouter.ai" в URL → True |
| `test_detect_openrouter_false` | OpenAI → False |
| `test_choose_move_success` | JSON → (A2, A4, None) |
| `test_choose_move_promotion` | → (A7, A8, "queen") |
| `test_choose_move_retry_on_bad_response` | 1й ответ плохой, 2й ок |
| `test_choose_move_all_retries_exhausted` | → None |
| `test_choose_move_temperature_escalation` | 0.3 → 0.5 → 0.7 |
| `test_choose_move_retry_hint_json` | "REMINDER" + "move_from" |
| `test_choose_move_retry_hint_simple` | "FROM TO" |
| `test_stats_after_choose_move` | llm_calls=1 |
| `test_stats_tokens_accumulated` | prompt=50, completion=20, total=70 |
| `test_start_sets_running` | _running=True |
| `test_stop_clears_running` | _running=False |
| `test_start_when_already_running_noop` | Тот же task |

### tests/integration/test_gui_logic.py — 24 теста

| Тест | Проверяет |
|------|-----------|
| `test_format_state_basic` | WHITE, #5 |
| `test_format_state_check` | CHECK в тексте |
| `test_format_state_last_move` | E7, E5 |
| `test_format_state_no_last_move` | Em dash |
| `test_format_state_legal_moves` | A2, A3 |
| `test_format_state_no_legal_moves` | "нет" |
| `test_format_game_list_multiple` | 2 игры, Bot1 |
| `test_format_game_list_empty` | "нет" |
| `test_collect_settings_custom_headers_json` | JSON → dict |
| `test_collect_settings_invalid_json` | "{bad" → {} |
| `test_collect_settings_empty_headers` | "" → {} |
| `test_collect_settings_env_fallback` | OPENAI_API_KEY |
| `test_collect_settings_strips_whitespace` | " url " → "url" |
| `test_apply_preset_openai` | base_url, model, compat |
| `test_apply_preset_anthropic` | compat=False, claude |
| `test_apply_preset_openrouter` | openrouter URL, headers |
| `test_apply_preset_ollama` | localhost |
| `test_apply_preset_unknown` | → {} |
| `test_mask_api_key_long` | sk-12345...cdef |
| `test_mask_api_key_short` | *** |
| `test_mask_api_key_empty` | "" |
| `test_format_hint_simple` | "E2 E4" |
| `test_format_hint_json` | "from" |
| `test_format_hint_json_thinking` | "thinking" |

### tests/integration/test_gui_screens.py — 7 тестов

| Тест | Проверяет |
|------|-----------|
| `test_gui_creates_without_error` | create_gui не падает |
| `test_gui_helpers_mask_api_key` | mask_api_key |
| `test_gui_helpers_format_hint` | format_hint 3 формата + unknown |
| `test_gui_helpers_format_state_basic` | format_state_text |
| `test_gui_helpers_collect_settings_basic` | collect_settings |
| `test_gui_helpers_apply_preset` | apply_provider_preset |
| `test_gui_helpers_format_game_list` | format_game_list |

---

## Покрытие по модулям

| Модуль | Покрытие | Непокрытые строки |
|--------|----------|-------------------|
| `arena_client.py` | **100%** | — |
| `constants.py` | **100%** | — |
| `notation_converter.py` | **100%** | — |
| `gui_helpers.py` | **100%** | — |
| `move_parser.py` | **98%** | 188-189 (except json.loads) |
| `tracer.py` | **98%** | 61, 185 (server_interaction, except save) |
| `pricing.py` | **97%** | 153, 158 (except ValueError) |
| `prompt_builder.py` | **97%** | 94, 96, 174 (append board/check fallback) |
| `settings.py` | **96%** | 28, 201-202, 254, 296 (except ветки) |
| `llm_client.py` | **92%** | 69-70, 114-115 (except non-JSON errors) |
| `bot_runner.py` | **43%** | 93-432+ (полный game loop `_run()`) |
| `gui.py` | исключён | UI-код, требует Selenium |

---

## Команды

```bash
pytest -v                                     # Все 250 тестов
pytest --cov=. --cov-report=term-missing      # С покрытием
pytest tests/unit/ -v                         # Только unit (103)
pytest tests/integration/ -v                  # Только integration (139)
pytest tests/property/ -v                     # Только property (8)
pytest tests/unit/test_move_parser.py -v      # Один файл
pytest --lf                                   # Только упавшие
```
