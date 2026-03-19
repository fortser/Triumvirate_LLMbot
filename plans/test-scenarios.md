# Test Scenarios: Triumvirate LLM Bot v2.2

Generated: 2026-03-15
Status: DRAFT
Total estimated tests: **152**

---

## Module: `notation_converter.py`

**Приоритет: HIGH | Целевое покрытие: 100%**

### Public Interface

| Function/Method            | Signature                                       | Description                    |
|----------------------------|-------------------------------------------------|--------------------------------|
| `to_triumvirate`           | `(server_notation: str) -> str`                 | Server → Triumvirate notation  |
| `to_server`                | `(tri_notation: str) -> str`                    | Triumvirate → Server notation  |
| `convert_legal_moves`      | `(legal: dict) -> dict`                         | Batch convert legal moves      |
| `convert_legal_moves_back` | `(tri_legal: dict) -> dict`                     | Reverse batch convert          |
| `convert_board`            | `(board: list[dict]) -> list[dict]`             | Add tri_notation to pieces     |
| `convert_move_back`        | `(tri_from, tri_to) -> (str, str)`              | Single move reverse convert    |

### Scenarios

#### Happy Path
- [ ] `test_to_triumvirate_known_cells` — parametrize 12+ known pairs: ("A1","W3/B3.0"), ("D4","C/W.B"), ("E4","C/W.R"), ("A8","B3/W0.0"), ("H12","R3/B3.0"), ("L12","R3/W3.3"), ("D1","W3/W3.3"), ("A4","W3/B0.0"), ("D8","B3/W0.3"), ("H9","R3/B0.0"), ("E1","W3/R3.3"), ("I5","B3/R0.0")
- [ ] `test_to_server_known_cells` — reverse of above, parametrize same pairs
- [ ] `test_convert_legal_moves_simple` — {"A2": ["A3","A4"]} → converted correctly, keys and values are Triumvirate
- [ ] `test_convert_legal_moves_back_simple` — reverse of above
- [ ] `test_convert_board_adds_tri_notation` — each piece dict gets "tri_notation" field
- [ ] `test_convert_move_back` — ("W3/B3.0", "W3/B2.0") → ("A1", "A2")

#### Edge Cases
- [ ] `test_to_triumvirate_center_cells_both` — D4→C/W.B (col 4) and E4→C/W.R (col 5), special center logic branch
- [ ] `test_to_triumvirate_case_insensitive` — "a1" and "A1" and "a1 " all → same result
- [ ] `test_to_triumvirate_whitespace` — " A1 " trimmed before lookup
- [ ] `test_convert_board_piece_without_notation` — piece has empty notation → no tri_notation added, piece still in result
- [ ] `test_convert_board_empty_list` — [] → []
- [ ] `test_convert_legal_moves_empty` — {} → {}
- [ ] `test_convert_board_does_not_mutate_original` — original list[dict] unchanged after call

#### Error Paths
- [ ] `test_to_triumvirate_invalid_raises_keyerror` — "Z99" → KeyError with descriptive message
- [ ] `test_to_server_invalid_raises_keyerror` — "X1/Y2.3" → KeyError
- [ ] `test_convert_board_invalid_notation_keeps_original` — piece with notation="Z99" → tri_notation="Z99" (try/except in code)

#### Property-Based (Hypothesis)
- [ ] `test_roundtrip_all_96_cells` — to_server(to_triumvirate(x)) == x for all 96 server notations
- [ ] `test_reverse_roundtrip_all_96` — to_triumvirate(to_server(x)) == x for all 96 Triumvirate notations
- [ ] `test_lookup_tables_bijective` — len(_SERVER_TO_TRI) == len(_TRI_TO_SERVER) == 96, sets of values/keys match
- [ ] `test_convert_legal_moves_roundtrip` — convert_legal_moves_back(convert_legal_moves(m)) == m for arbitrary valid moves

**Subtotal: 20 tests** (12 unit + 4 property + 4 edge/error)

---

## Module: `move_parser.py`

**Приоритет: HIGH | Целевое покрытие: 95%+**

### Public Interface

| Function/Method         | Signature                                                     |
|-------------------------|---------------------------------------------------------------|
| `MoveParser.parse`      | `(text, legal, fmt, triumvirate=False) -> tuple \| None`      |
| `_sanitize_json_string` | `(raw: str) -> str`                                           |

### Scenarios

#### Happy Path — JSON format
- [ ] `test_parse_json_standard` — `'{"move_from":"A2","move_to":"A3"}'` → ("A2","A3",None)
- [ ] `test_parse_json_thinking_extracts_move_ignores_thinking` — `'{"thinking":"…","move_from":"A2","move_to":"A3"}'` → ("A2","A3",None), thinking not parsed as move
- [ ] `test_parse_json_legacy_keys` — `'{"from":"A2","to":"A3"}'` → ("A2","A3",None)
- [ ] `test_parse_json_with_promotion` — `'{"move_from":"A7","move_to":"A8","promotion":"queen"}'` → ("A7","A8","queen")
- [ ] `test_parse_json_with_markdown_fences` — `` '```json\n{"move_from":"A2","move_to":"A3"}\n```' `` → ("A2","A3",None)

#### Happy Path — Simple format
- [ ] `test_parse_simple_two_coords` — "A2 A3" → ("A2","A3",None)
- [ ] `test_parse_simple_with_promotion` — "A7 A8 =Q" → ("A7","A8","queen")
- [ ] `test_parse_simple_coords_in_text` — "I think A2 to A3 is good" → ("A2","A3",None)
- [ ] `test_parse_simple_skips_illegal_pairs` — first pair illegal, second legal → returns second pair

#### Happy Path — Triumvirate
- [ ] `test_parse_json_triumvirate` — `'{"move_from":"W3/B2.0","move_to":"W3/B1.0"}'` → ("W3/B2.0","W3/B1.0",None) with triumvirate=True
- [ ] `test_parse_simple_triumvirate` — "W3/B2.0 W3/B1.0" → correct tuple with triumvirate=True

#### Edge Cases — _sanitize_json_string
- [ ] `test_sanitize_strips_markdown_fences` — `` ```json\n{"a":1}\n``` `` → `{"a":1}`
- [ ] `test_sanitize_strips_markdown_fences_no_lang_tag` — `` ```\n{"a":1}\n``` `` → `{"a":1}`
- [ ] `test_sanitize_escapes_control_chars` — `'{"a":"text\x00here"}'` → control char escaped to `\u0000`
- [ ] `test_sanitize_escapes_newlines_in_strings` — literal `\n` inside JSON string value → `\\n`
- [ ] `test_sanitize_escapes_tabs_in_strings` — literal `\t` inside JSON string value → `\\t`
- [ ] `test_sanitize_escapes_carriage_return` — literal `\r` inside JSON string → `\\r`
- [ ] `test_sanitize_handles_escaped_quotes` — `\"` inside string not treated as string delimiter
- [ ] `test_sanitize_empty_string` — "" → ""
- [ ] `test_sanitize_valid_json_unchanged` — `'{"a":"b"}'` passes through without modification
- [ ] `test_sanitize_no_newline_outside_strings` — newlines outside JSON strings preserved as-is

#### Edge Cases — Parse
- [ ] `test_parse_strips_piece_prefix_server` — "NE2" → "E2" (Knight prefix stripped)
- [ ] `test_parse_strips_piece_prefix_server_parametrize` — parametrize: N, B, R, Q, K, P prefixes
- [ ] `test_parse_strips_piece_prefix_tri_without_separator` — "PW3/B2.0" → "W3/B2.0"
- [ ] `test_parse_strips_piece_prefix_tri_with_colon` — "L:W3/R3.3" → "W3/R3.3"
- [ ] `test_parse_strips_piece_prefix_tri_ambiguous_WBR` — "B" is both piece prefix and sector: "BW3/B2.0" should NOT strip (s[0] in "WBR" guard)
- [ ] `test_parse_json_no_braces` — no { } in response → None
- [ ] `test_parse_json_invalid_json` — broken JSON after sanitization → None
- [ ] `test_parse_json_missing_keys` — `'{"thinking":"just thinking"}'` → None (no move_from/move_to)
- [ ] `test_parse_illegal_move_returns_none` — coords exist but move not in legal → None
- [ ] `test_parse_same_coords_skipped` — "A2 A2 A3" → skip (A2,A2), find (A2,A3) if legal
- [ ] `test_parse_empty_text` — "" → None
- [ ] `test_parse_case_insensitive_legal` — legal keys uppercased, response lowercase → still matches
- [ ] `test_norm_promo_standard_names` — "queen","rook","bishop","knight" → pass through
- [ ] `test_norm_promo_single_letter` — "q"→"queen", "r"→"rook", "b"→"bishop", "n"→"knight"
- [ ] `test_norm_promo_triumvirate_names` — "marshal"→"queen", "train"→"rook", "drone"→"bishop", "noctis"→"knight"
- [ ] `test_norm_promo_none` — None → None
- [ ] `test_norm_promo_unknown` — "invalid" → None (not in any mapping)

#### Property-Based
- [ ] `test_parse_never_crashes_on_arbitrary_text` — Hypothesis text(), legal={fixed}, fmt in ("simple","json","json_thinking") → never raises
- [ ] `test_parse_result_always_in_legal` — if result is not None, result[0] in legal and result[1] in legal[result[0]]
- [ ] `test_sanitize_never_crashes` — arbitrary text() → no exception
- [ ] `test_sanitize_idempotent` — sanitize(sanitize(x)) == sanitize(x)

**Subtotal: 40 tests** (36 unit + 4 property)

---

## Module: `constants.py`

**Приоритет: MEDIUM | Целевое покрытие: 100%**

### Public Interface

| Function/Constant | Description                              |
|-------------------|------------------------------------------|
| `VERSION`         | Version string                           |
| `PROVIDERS`       | Dict of provider presets                 |
| `PROVIDER_ENV_KEY`| Dict of provider → env var name          |
| `make_bot_name`   | `(provider: str, model: str) -> str`     |

### Scenarios
- [ ] `test_make_bot_name_standard` — parametrize: каждый провайдер из PROVIDERS + его дефолтная модель → проверить формат "LLM_{short}_{model}"
- [ ] `test_make_bot_name_truncation` — model name > 70 chars → total name truncated to 80
- [ ] `test_make_bot_name_empty_model` — model="" → "LLM_{short}_unknown"
- [ ] `test_make_bot_name_unknown_provider` — "Some Provider" → uses "Some" (first word)
- [ ] `test_make_bot_name_spaces_in_model` — "my model name" → "my-model-name" (spaces → hyphens)
- [ ] `test_make_bot_name_never_exceeds_80_chars` — property: len(result) <= 80 для различных inputs
- [ ] `test_providers_dict_structure` — all entries have required keys: base_url, api_key, model, compat, response_format
- [ ] `test_provider_env_key_known_providers` — OpenAI, Anthropic, OpenRouter all have env key mappings
- [ ] `test_provider_short_covers_all_providers` — every key in PROVIDERS has mapping in _PROVIDER_SHORT
- [ ] `test_version_format` — VERSION matches semver pattern X.Y.Z

**Subtotal: 10 tests**

---

## Module: `pricing.py`

**Приоритет: HIGH | Целевое покрытие: 90%+**

### Public Interface

| Method                 | Signature                                                        |
|------------------------|------------------------------------------------------------------|
| `PricingManager()`     | Constructor, initializes empty state                             |
| `.is_loaded`           | Property: True if source != "none"                               |
| `.get_pricing()`       | Returns current pricing dict                                     |
| `.fetch_openrouter()`  | `async (api_key, model) -> dict`                                 |
| `.set_zero()`          | Sets zero pricing for non-OpenRouter                             |
| `.calc_cost()`         | `(prompt_tokens, completion_tokens, reasoning_tokens=0) -> dict` |
| `.extract_usage()`     | `(response_body, is_openrouter) -> dict`                         |

### Scenarios

#### Unit — calc_cost
- [ ] `test_calc_cost_basic` — known tokens + rates → expected USD: 1000 prompt × 0.15/1M = 0.00015, etc.
- [ ] `test_calc_cost_zero_tokens` — all 0 → all values 0.0
- [ ] `test_calc_cost_reasoning_at_completion_rate` — reasoning tokens billed at completion rate
- [ ] `test_calc_cost_all_values_non_negative` — property: calc_cost(p, c, r).values() >= 0 for any non-negative inputs
- [ ] `test_calc_cost_total_equals_sum` — total_cost_usd == input + output + reasoning

#### Unit — extract_usage
- [ ] `test_extract_usage_openai_format` — standard {"prompt_tokens":100,"completion_tokens":50,"total_tokens":150}
- [ ] `test_extract_usage_with_native_reasoning_tokens` — is_openrouter=True + native_tokens_reasoning → extracted
- [ ] `test_extract_usage_with_completion_details_reasoning` — is_openrouter=True + completion_tokens_details.reasoning_tokens → extracted when native absent
- [ ] `test_extract_usage_reasoning_ignored_non_openrouter` — is_openrouter=False → reasoning_tokens always 0
- [ ] `test_extract_usage_with_provider_cost_in_usage` — usage.total_cost → provider_reported_cost_usd
- [ ] `test_extract_usage_with_provider_cost_top_level` — response_body.total_cost (not in usage) → still extracted
- [ ] `test_extract_usage_empty` — no usage block → all zeros
- [ ] `test_extract_usage_total_tokens_fallback` — total_tokens=0 → fallback to prompt+completion sum

#### Integration — fetch_openrouter (respx)
- [ ] `test_fetch_openrouter_success` — respx mock /api/v1/models with model match → pricing converted to per 1M
- [ ] `test_fetch_openrouter_model_not_found` — model not in list → source="openrouter_model_not_found", prices 0.0
- [ ] `test_fetch_openrouter_network_error` — httpx error → source="openrouter_fetch_error"
- [ ] `test_fetch_openrouter_empty_model` — model="" → early return, source="none"

#### Unit — set_zero / is_loaded / get_pricing
- [ ] `test_set_zero` — source="not_openrouter", prices 0.0
- [ ] `test_is_loaded_initially_false` — PricingManager() → is_loaded == False
- [ ] `test_is_loaded_after_set_zero` — .set_zero() → is_loaded == True

**Subtotal: 20 tests**

---

## Module: `settings.py`

**Приоритет: HIGH | Целевое покрытие: 90%+**

### Public Interface

| Method/Function        | Description                                         |
|------------------------|-----------------------------------------------------|
| `Settings()`           | Constructor, loads from file or defaults             |
| `Settings.__getitem__` | Get setting, virtual keys for prompts & api_key      |
| `Settings.__setitem__` | Set setting, blocks legacy prompt keys               |
| `Settings.get()`       | Get with default, routes virtual keys                |
| `Settings.save()`      | Persist to JSON, excludes inline prompts             |
| `get_response_format()`| Get format instruction from file or fallback         |
| `_load_dotenv()`       | Load .env into os.environ (setdefault)               |

### Scenarios

#### Settings lifecycle (all use tmp_path + monkeypatch)
- [ ] `test_settings_defaults` — fresh Settings (no file) has all DEFAULTS values
- [ ] `test_settings_save_load_roundtrip` — save then reload → values match
- [ ] `test_settings_save_excludes_legacy_keys` — saved JSON does NOT contain "system_prompt" or "user_template" keys

#### Virtual keys
- [ ] `test_settings_virtual_key_system_prompt_reads_file` — settings["system_prompt"] reads from prompts/system_prompt.txt
- [ ] `test_settings_virtual_key_user_template_reads_file` — settings["user_template"] reads from prompts/user_prompt_template.txt
- [ ] `test_settings_virtual_key_fallback_when_file_missing` — no prompt file → returns _FALLBACK_SYSTEM / _FALLBACK_USER_TEMPLATE
- [ ] `test_settings_virtual_key_fallback_when_file_empty` — empty prompt file → returns fallback

#### API key resolution
- [ ] `test_settings_api_key_from_json` — stored non-empty api_key → returned directly
- [ ] `test_settings_api_key_from_env` — empty api_key in JSON + env var set → returns env var
- [ ] `test_settings_api_key_no_env_mapping` — provider not in PROVIDER_ENV_KEY → returns ""

#### Setter blocking
- [ ] `test_settings_blocks_legacy_key_write` — settings["system_prompt"] = "text" → ignored, value unchanged

#### Migration
- [ ] `test_settings_migrate_legacy_prompts` — JSON with inline "system_prompt" string → written to file, key replaced with "system_prompt_file"
- [ ] `test_settings_migrate_saves_both_prompts` — both system_prompt and user_template migrated in single load

#### Response format
- [ ] `test_get_response_format_from_file` — prompts/format_json.txt exists → returns file content
- [ ] `test_get_response_format_fallback_known` — no file, fmt="simple" → returns DEFAULT_RESPONSE_FORMAT["simple"]
- [ ] `test_get_response_format_fallback_unknown` — no file, fmt="xyz" → returns DEFAULT_RESPONSE_FORMAT["json_thinking"]

#### .env loading
- [ ] `test_load_dotenv_sets_env_vars` — .env with KEY=VALUE → os.environ[KEY] set
- [ ] `test_load_dotenv_does_not_overwrite` — existing env var → NOT overwritten by .env
- [ ] `test_load_dotenv_ignores_comments` — lines starting with # → skipped
- [ ] `test_load_dotenv_strips_quotes` — VALUE wrapped in single/double quotes → stripped
- [ ] `test_load_dotenv_nonexistent_file` — no .env file → no error

#### Properties
- [ ] `test_system_prompt_path_absolute` — system_prompt_path returns absolute Path
- [ ] `test_user_template_path_absolute` — user_template_path returns absolute Path

**Subtotal: 23 tests**

---

## Module: `prompt_builder.py`

**Приоритет: MEDIUM | Целевое покрытие: 90%+**

### Public Interface

| Method             | Signature                                                |
|--------------------|----------------------------------------------------------|
| `PromptBuilder.build` | `(state, settings, *, tri_legal, tri_board, tri_last_move) -> list[dict]` |

### Scenarios

#### build — basic
- [ ] `test_build_returns_system_and_user_messages` — returns list of 2 dicts with role "system" and "user"
- [ ] `test_build_includes_format_instruction` — system message contains "OUTPUT FORMAT" section
- [ ] `test_build_with_additional_rules` — additional_rules in settings → "ADDITIONAL RULES" appended to system

#### build — game state rendering
- [ ] `test_build_last_move_text` — last_move present → "from_sq → to_sq" in user prompt
- [ ] `test_build_last_move_with_type` — move_type != "normal" → type appended in parens
- [ ] `test_build_last_move_none` — no last_move → "none (game start)"
- [ ] `test_build_check_text_from_check_field` — check.is_check=True → "CHECK" warning in user prompt
- [ ] `test_build_check_text_from_player_status` — no check field, but player status="in_check" → "YOU ARE IN CHECK" warning
- [ ] `test_build_no_check` — no check info → no check text

#### build — Triumvirate mode
- [ ] `test_build_triumvirate_mode_uses_tri_legal` — tri_legal provided → used in legal_moves section
- [ ] `test_build_triumvirate_last_move` — tri_last_move provided → Triumvirate coords in last_move text
- [ ] `test_build_triumvirate_board` — tri_board provided → Triumvirate piece symbols used (L/M/T/D/N/P)

#### Helpers
- [ ] `test_fmt_legal_empty` — {} → "(none)"
- [ ] `test_fmt_legal_sorted` — multiple sources → sorted output
- [ ] `test_fmt_board_server_grouped_by_color` — pieces grouped by color, sorted, "← YOU" tag on my_color
- [ ] `test_fmt_board_server_captured_piece` — owner != color → "(owner[0])" suffix
- [ ] `test_fmt_board_tri_piece_symbols` — type "KING"→"L", "QUEEN"→"M", "ROOK"→"T", "BISHOP"→"D"
- [ ] `test_fmt_board_empty` — [] → ""
- [ ] `test_fill_template_double_braces` — "{{key}}" substituted
- [ ] `test_fill_template_single_braces` — "{key}" substituted
- [ ] `test_fill_template_missing_key` — placeholder not in subs → left as-is

**Subtotal: 21 tests**

---

## Module: `llm_client.py`

**Приоритет: HIGH | Целевое покрытие: 90%+**

### Public Interface

| Method          | Signature                                                          |
|-----------------|--------------------------------------------------------------------|
| `LLMClient.ask` | `async (messages, base_url, api_key, model, temperature, max_tokens, compat, custom_headers, timeout) -> (str, dict)` |

### Scenarios (all integration with respx)
- [ ] `test_ask_openai_compat_returns_text_and_body` — respx mock /chat/completions → returns (text, body)
- [ ] `test_ask_openai_sends_correct_payload` — verify model, messages, temperature, max_tokens in request body
- [ ] `test_ask_openai_sends_auth_header` — api_key → "Bearer {key}" in Authorization header
- [ ] `test_ask_openai_no_auth_when_key_empty` — api_key="" → no Authorization header
- [ ] `test_ask_openai_with_custom_headers` — custom_headers → merged into request headers
- [ ] `test_ask_openai_error_status_raises` — parametrize 400, 429, 500 → RuntimeError with status code
- [ ] `test_ask_openai_error_json_detail` — error response with JSON body → detail in exception message
- [ ] `test_ask_anthropic_native_returns_text_and_body` — respx mock /v1/messages → returns (text, body)
- [ ] `test_ask_anthropic_extracts_system_message` — system message separated from user messages, put in body.system
- [ ] `test_ask_anthropic_sends_api_key_header` — x-api-key header present
- [ ] `test_ask_anthropic_error_status_raises` — 4xx/5xx → RuntimeError

**Subtotal: 11 tests**

---

## Module: `arena_client.py`

**Приоритет: HIGH | Целевое покрытие: 90%+**

### Public Interface

| Method           | Signature                                                  |
|------------------|------------------------------------------------------------|
| `ArenaClient()`  | `(server_url: str)` — constructor, builds base URL         |
| `.health()`      | `async () -> dict`                                         |
| `.join()`        | `async (name, model) -> dict`                              |
| `.get_state()`   | `async () -> dict`                                         |
| `.make_move()`   | `async (from_sq, to_sq, move_number, promotion) -> (int, Any)` |
| `.skip_waiting()`| `async () -> dict`                                         |
| `.resign()`      | `async () -> dict`                                         |
| `.list_games()`  | `async () -> list`                                         |

### Scenarios (all integration with respx)
- [ ] `test_constructor_builds_base_url` — "https://example.com" → _base = "https://example.com/api/v1"
- [ ] `test_constructor_strips_trailing_slash` — "https://example.com/" → same _base
- [ ] `test_join_stores_token_game_color` — response fields stored on self
- [ ] `test_join_with_model` — model passed → included in request body
- [ ] `test_get_state_sends_auth_header` — Authorization: Bearer token in request
- [ ] `test_make_move_returns_status_and_data` — (200, {…}) tuple
- [ ] `test_make_move_with_promotion` — promotion included in request body
- [ ] `test_make_move_non_json_response` — response not JSON → data is text string
- [ ] `test_health_returns_dict` — respx mock /health → dict returned
- [ ] `test_resign_calls_correct_endpoint` — POST /resign with auth header
- [ ] `test_skip_waiting_calls_correct_endpoint` — POST /skip-waiting with auth header
- [ ] `test_list_games_returns_list` — GET /games → list returned

**Subtotal: 12 tests**

---

## Module: `tracer.py`

**Приоритет: MEDIUM | Целевое покрытие: 90%+**

### Public Interface

| Method                   | Description                                  |
|--------------------------|----------------------------------------------|
| `MoveTracer(logs_dir)`   | Constructor                                  |
| `.init(game_id, move_num, model)` | Start new trace                     |
| `.add_llm_response(…)`   | Record LLM response with usage/cost          |
| `.add_llm_request(…)`    | Record LLM request                           |
| `.add_parser_attempt(…)` | Record parser attempt                        |
| `.set_*(…)`              | Various setters (model_pricing, outcome, etc)|
| `.finalize_statistics()` | Compute summary statistics                   |
| `.save()`                | Write trace to disk as JSON                  |

### Scenarios (all use tmp_path)
- [ ] `test_init_sets_fields` — game_id, move_number, timestamp populated in _data
- [ ] `test_init_sanitizes_model_name` — special chars in model → replaced with _
- [ ] `test_add_llm_response_accumulates` — multiple add_llm_response calls → all in llm_responses list
- [ ] `test_add_llm_response_with_usage_and_cost` — usage/cost dicts stored in entry
- [ ] `test_finalize_statistics_sums_correctly` — totals match individual entries: prompt_tokens, completion_tokens, cost
- [ ] `test_finalize_statistics_retries_count` — retries = len(llm_responses) - 1
- [ ] `test_finalize_statistics_provider_cost_accumulates` — multiple provider costs summed
- [ ] `test_finalize_statistics_provider_cost_none_when_absent` — no provider cost → None in statistics
- [ ] `test_save_creates_directory_and_file` — game_<id>__<model>/move_001.json exists after save
- [ ] `test_save_file_content_valid_json` — saved file parses as valid JSON with expected keys
- [ ] `test_save_empty_data_skipped` — _data is empty dict → no file written
- [ ] `test_full_trace_cycle` — init → set_model_pricing → add_llm_request → add_llm_response → set_move_selected → set_outcome → finalize → save → verify JSON file

**Subtotal: 12 tests**

---

## Module: `bot_runner.py` (partial)

**Приоритет: MEDIUM | Целевое покрытие: 70%+**

### Testable Public Interface

| Method/Field          | Description                                      |
|-----------------------|--------------------------------------------------|
| `BotRunner(…)`        | Constructor                                      |
| `.start()`            | Creates and starts asyncio task                  |
| `.stop()`             | Sets _running=False, cancels task                |
| `._detect_openrouter()`| Checks provider name or URL                    |
| `._choose_move(…)`    | Core move selection with LLM (async)             |
| `.stats`              | Running statistics dict                          |

### Scenarios

#### Unit — _detect_openrouter
- [ ] `test_detect_openrouter_by_provider` — provider="OpenRouter" → True
- [ ] `test_detect_openrouter_by_url` — base_url contains "openrouter.ai" → True
- [ ] `test_detect_openrouter_false` — provider="OpenAI API", url="api.openai.com" → False

#### Integration — _choose_move (respx mock for LLM)
- [ ] `test_choose_move_success` — LLM returns valid JSON move → returns (from, to, None)
- [ ] `test_choose_move_with_promotion` — LLM returns move + promotion → returns (from, to, promo)
- [ ] `test_choose_move_retry_on_bad_response` — first response garbage, second valid → returns valid tuple, stats["retries"] == 1
- [ ] `test_choose_move_all_retries_exhausted` — all responses garbage → returns None
- [ ] `test_choose_move_temperature_escalation` — verify temperature increases: base + attempt*0.2, capped at 1.0
- [ ] `test_choose_move_retry_hint_appended_json` — retry message contains "REMINDER" about JSON format
- [ ] `test_choose_move_retry_hint_appended_simple` — retry message contains "REMINDER" about text format

#### Stats tracking
- [ ] `test_stats_updated_after_choose_move` — llm_calls, total_prompt_chars, total_resp_chars incremented
- [ ] `test_stats_tokens_accumulated` — total_prompt_tokens, total_completion_tokens updated from usage

#### Lifecycle
- [ ] `test_start_sets_running` — start() → _running=True, _task is not None
- [ ] `test_stop_clears_running` — stop() → _running=False, _task cancelled
- [ ] `test_start_when_already_running_noop` — second start() call → no new task

**Subtotal: 15 tests**

---

## Module: `gui.py`

**Приоритет: MEDIUM | Целевое покрытие: 60%+**

### Предварительный шаг: Извлечение логики

Перед написанием тестов создать `gui_helpers.py` — извлечь чистые функции из closures `create_gui()`.

### Public Interface (после извлечения в gui_helpers.py)

| Function                      | Извлечено из          | Описание                               |
|-------------------------------|----------------------|-----------------------------------------|
| `format_state_text(state)`    | `_on_state` (62-89)  | State dict → (state_md, legal_md)      |
| `format_game_list(games)`     | `on_list_games` (300) | Games list → markdown                 |
| `collect_settings(values)`    | `_collect` (101-131)  | UI values → settings dict             |
| `apply_provider_preset(prov)` | `_on_provider` (132)  | Provider name → preset values          |
| `mask_api_key(key)`           | `on_test_llm` (246)   | API key → masked string               |
| `format_hint(fmt)`            | `_on_fmt` (169-175)   | Format name → hint string              |

### Scenarios — Extracted Logic (test_gui_logic.py)

#### format_state_text
- [ ] `test_format_state_basic` — move_number, current_player, game_status отображаются в markdown
- [ ] `test_format_state_with_check` — check.is_check → "CHECK" + checked_colors в state_md
- [ ] `test_format_state_with_last_move` — last_move dict → "from→to" в state_md
- [ ] `test_format_state_no_last_move` — None → "—"
- [ ] `test_format_state_legal_moves` — legal_moves dict → каждый src: dsts в legal_md
- [ ] `test_format_state_no_legal_moves` — empty legal_moves → "(нет допустимых ходов)"

#### format_game_list
- [ ] `test_format_game_list_multiple` — несколько игр → markdown с game_id, players, move_number
- [ ] `test_format_game_list_empty` — [] → "(активных игр нет)"

#### collect_settings_from_values
- [ ] `test_collect_parses_custom_headers_json` — valid JSON string → parsed dict
- [ ] `test_collect_invalid_headers_json` — invalid JSON → empty dict
- [ ] `test_collect_empty_headers` — "" → empty dict
- [ ] `test_collect_api_key_from_env_fallback` — empty api_key + env var set → returns env value
- [ ] `test_collect_strips_whitespace` — " url " → "url", " model " → "model"

#### apply_provider_preset
- [ ] `test_preset_openai` — returns base_url, model, compat=True
- [ ] `test_preset_anthropic` — compat=False
- [ ] `test_preset_openrouter` — custom_headers non-empty
- [ ] `test_preset_ollama` — localhost, response_format="simple"
- [ ] `test_preset_unknown_provider` — unknown → empty dict

#### mask_api_key
- [ ] `test_mask_long_key` — "sk-1234567890abcdef" → "sk-12345...cdef"
- [ ] `test_mask_short_key` — "short" (<=12 chars) → "***"
- [ ] `test_mask_empty_key` — "" → ""

#### format_hint
- [ ] `test_hint_simple` — "simple" → contains "E2 E4"
- [ ] `test_hint_json` — "json" → contains "from" and "to"
- [ ] `test_hint_json_thinking` — "json_thinking" → contains "thinking"
- [ ] `test_hint_unknown` — "xyz" → ""

### Scenarios — NiceGUI Screen Tests (test_gui_screens.py)

#### Рендеринг
- [ ] `test_gui_renders_header_with_version` — "Triumvirate LLM Bot" + VERSION присутствует
- [ ] `test_gui_renders_all_tabs` — "Игра", "Лог", "Лобби" присутствуют
- [ ] `test_gui_renders_provider_select` — список провайдеров из PROVIDERS
- [ ] `test_gui_initial_status` — "Не запущен" отображается

#### Взаимодействие — Провайдер
- [ ] `test_switch_provider_updates_fields` — выбор провайдера → base_url, model обновлены

#### Взаимодействие — Кнопки (с respx-моками)
- [ ] `test_test_server_ping` — respx mock /health → UI notification positive
- [ ] `test_save_settings_persists` — кнопка "Сохранить" → файл настроек создан

**Subtotal: 31 tests** (24 unit + 7 screen)

---

## Summary

| Module                  | Unit | Integration | Screen | Property | Total |
|-------------------------|------|-------------|--------|----------|-------|
| `notation_converter.py` | 12   | 0           | 0      | 4        | **20**|
| `move_parser.py`        | 36   | 0           | 0      | 4        | **40**|
| `constants.py`          | 10   | 0           | 0      | 0        | **10**|
| `pricing.py`            | 13   | 4           | 0      | 1*       | **20**|
| `settings.py`           | 0    | 23          | 0      | 0        | **23**|
| `prompt_builder.py`     | 0    | 21          | 0      | 0        | **21**|
| `tracer.py`             | 0    | 12          | 0      | 0        | **12**|
| `llm_client.py`         | 0    | 11          | 0      | 0        | **11**|
| `arena_client.py`       | 0    | 12          | 0      | 0        | **12**|
| `bot_runner.py`         | 3    | 12          | 0      | 0        | **15**|
| `gui.py`                | 24   | 0           | 7      | 0        | **31**|
| **TOTAL**               | **98** | **95**   | **7**  | **9**    | **152** |

*\* calc_cost non-negative включён как unit-тест с parametrize, но по сути property check*

---

## Порядок реализации (Шаг 2)

```
1. pyproject.toml + conftest.py        — конфигурация и общие fixtures
2. tests/unit/test_constants.py        — leaf, без зависимостей, быстрый старт
3. tests/unit/test_notation_converter.py — leaf, без зависимостей
4. tests/property/test_notation_roundtrip.py — hypothesis для notation
5. tests/unit/test_sanitize_json.py    — _sanitize_json_string выделен
6. tests/unit/test_move_parser.py      — парсер, depends on sanitize
7. tests/property/test_parser_fuzzing.py — hypothesis для parser
8. tests/property/test_sanitize_json_fuzzing.py — hypothesis для sanitize
9. tests/unit/test_pricing_calc.py     — чистая математика
10. tests/integration/test_settings.py  — tmp_path, monkeypatch
11. tests/integration/test_prompt_builder.py — real Settings + game states
12. tests/integration/test_tracer.py    — tmp_path
13. tests/integration/test_llm_client.py — respx
14. tests/integration/test_arena_client.py — respx
15. tests/integration/test_pricing_fetch.py — respx
16. tests/integration/test_bot_runner.py — respx + real modules
17. gui_helpers.py                      — extract logic from gui.py
18. tests/integration/test_gui_logic.py — extracted GUI logic
19. tests/integration/test_gui_screens.py — NiceGUI Screen tests
```
