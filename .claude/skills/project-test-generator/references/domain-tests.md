# Domain-Specific Test Patterns: Triumvirate LLM Bot

## 1. Notation Converter Tests

Ключевой домен проекта: конвертация между серверной нотацией (A1-L12)
и Triumvirate v4.0 (W3/B3.0, C/W.B).

### Known conversion pairs for parametrize

```python
# Corner cells (3 sectors x 4 corners = 12 critical pairs)
KNOWN_PAIRS = [
    # White sector corners
    ("A1", "W3/B3.0"),   # bottom-left
    ("D1", "W3/W3.3"),   # bottom-right near center
    ("A4", "W3/B0.0"),   # top-left
    # Center cells (special logic in _compute_notation)
    ("D4", "C/W.B"),     # center, col 4
    ("E4", "C/W.R"),     # center, col 5
    # Black sector
    ("A8", "B3/W0.0"),
    ("D8", "B3/W0.3"),
    # Red sector
    ("H12", "R3/B3.0"),
    ("L12", "R3/W3.3"),
]
```

### Board structure invariants

```python
# 3 sectors x 8 columns x 4 rows = 96 cells
# But NOT all 12x12=144 combinations are valid:
# Only cells that belong to the three player sectors exist
assert len(_SERVER_TO_TRI) == 96
assert len(_TRI_TO_SERVER) == 96

# No duplicates: each server notation maps to exactly one Triumvirate
assert len(set(_SERVER_TO_TRI.values())) == 96
```

## 2. Move Parser Tests

### JSON format test data

```python
# Standard response
'{"thinking": "analyzing...", "move_from": "A2", "move_to": "A3"}'

# With markdown fences (common LLM artifact)
'```json\n{"move_from": "A2", "move_to": "A3"}\n```'

# With control characters (Gemini quirk)
'{"thinking": "line1\x00line2", "move_from": "A2", "move_to": "A3"}'

# Legacy keys
'{"from": "A2", "to": "A3"}'

# With promotion
'{"move_from": "A7", "move_to": "A8", "promotion": "queen"}'

# Triumvirate promotion names
'{"move_from": "W3/B2.0", "move_to": "W3/B1.0", "promotion": "marshal"}'
# "marshal" -> "queen", "train" -> "rook", "drone" -> "bishop", "noctis" -> "knight"
```

### Piece prefix stripping

```python
# Server notation: N, B, R, Q, K, P prefixes
"NE2" -> "E2"   # Knight at E2
"QD1" -> "D1"   # Queen at D1

# Triumvirate: L, M, T, D, N, P prefixes
"PW3/B2.0" -> "W3/B2.0"    # Pawn (no separator)
"L:W3/R3.3" -> "W3/R3.3"   # Leader with colon separator
```

## 3. Pricing Tests

### calc_cost precision

```python
# OpenRouter standard rates for gpt-4o-mini:
# Input: $0.15/1M tokens, Output: $0.60/1M tokens
pm._pricing = {"prompt_per_1m": 0.15, "completion_per_1m": 0.60}

cost = pm.calc_cost(prompt_tokens=1000, completion_tokens=500, reasoning_tokens=200)
# input_cost  = 1000 * 0.15 / 1_000_000 = 0.00000015
# output_cost = 500 * 0.60 / 1_000_000  = 0.00000030
# reason_cost = 200 * 0.60 / 1_000_000  = 0.00000012
# total = 0.00000057
```

### extract_usage edge cases

```python
# OpenRouter reasoning tokens (two possible locations)
usage = {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150,
    "native_tokens_reasoning": 30,  # OpenRouter-specific
}

# Alternative location
usage = {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150,
    "completion_tokens_details": {"reasoning_tokens": 30},
}

# Provider-reported cost (two possible locations)
response = {"usage": {...}, "total_cost": 0.001}
# or
response = {"usage": {"total_cost": 0.001, ...}}
```

## 4. Settings Tests

### Migration scenario

```python
# Legacy format (stored inline prompts):
legacy_json = {
    "system_prompt": "You are a chess engine...",
    "user_template": "Move #{{move_number}}...",
    "model": "gpt-4o-mini",
}
# After migration:
# - prompts/system_prompt.txt contains "You are a chess engine..."
# - prompts/user_prompt_template.txt contains "Move #{{move_number}}..."
# - JSON has system_prompt_file and user_template_file instead
```

### .env loading

```python
# .env file:
# OPENAI_API_KEY=sk-test123
# ANTHROPIC_API_KEY=sk-ant-test456

# os.environ.setdefault means existing env vars are NOT overwritten
```

## 5. BotRunner Tests — _choose_move isolation

```python
# Setup:
# 1. Real Settings (from tmp_path)
# 2. Real MoveParser, PromptBuilder, MoveTracer
# 3. respx mock for LLM HTTP call
# 4. Noop callbacks

# Test: successful move
# Mock LLM returns '{"move_from": "A2", "move_to": "A3"}'
# Assert: _choose_move returns ("A2", "A3", None)
# Assert: stats["llm_calls"] == 1

# Test: retry
# Mock LLM returns garbage first, valid JSON second
# Assert: _choose_move returns valid tuple
# Assert: stats["retries"] == 1

# Test: all retries fail
# Mock LLM always returns garbage
# Assert: _choose_move returns None
# Assert: stats["retries"] == max_retries - 1
```
