---
name: writing-tests
description: >
  Writes behavior-focused tests using Testing Trophy model with real
  dependencies. Use when writing tests, choosing test types, or avoiding
  anti-patterns like testing mocks.
---

# Writing Tests

**Core principle:** Test user-observable behavior with real dependencies.
Tests should survive refactoring.

> "The more your tests resemble the way your software is used,
> the more confidence they can give you." — Kent C. Dodds

## Testing Trophy Model

| Priority | Type        | When                                            |
|----------|-------------|-------------------------------------------------|
| 1st      | Integration | Default — multiple units with real dependencies |
| 2nd      | E2E         | Complete user workflows                         |
| 3rd      | Unit        | Pure functions only (no dependencies)           |

## Mocking Guidelines

**Default: Don't mock. Use real dependencies.**

**Only mock:**
- External HTTP/API calls (LLM providers, Arena server, OpenRouter pricing) — через `respx`
- Time/randomness (datetime.now, random, uuid)
- Файловая система — только когда нужен `tmp_path` для изоляции

**Never mock:**
- Internal modules (move_parser, notation_converter, prompt_builder, pricing, constants)
- Business logic (парсинг ходов, конвертация нотации, расчёт стоимости)
- Your own code calling your own code

**Before mocking, ask:** "Какие побочные эффекты у этого? Нужны ли
они моему тесту?" Если не уверен — сначала запусти с реальной
зависимостью, потом добавь минимальный мок только где необходимо.

## Test Type Decision

```
Полный пользовательский workflow?     → E2E test
Чистая функция (без side effects)?    → Unit test
Всё остальное                         → Integration test
```

## Assertion Strategy

| Context             | Assert On                        | Avoid                        |
|---------------------|----------------------------------|------------------------------|
| MoveParser          | Returned (from, to, promo) tuple | Internal regex state         |
| NotationConverter   | Converted notation string        | Lookup table internals       |
| LLMClient           | Returned (text, body) tuple      | httpx internals              |
| ArenaClient         | Returned dict / state changes    | HTTP request details         |
| PricingManager      | Cost dict values                 | Internal _pricing dict       |
| PromptBuilder       | Message list content             | Template substitution steps  |
| Settings            | Resolved values via __getitem__  | Internal _d dict             |
| MoveTracer          | Saved JSON file content          | Internal _data dict          |
| BotRunner           | Stats dict, log calls, outcomes  | Internal loop state          |

## Anti-Patterns

| Pattern                              | Fix                              |
|--------------------------------------|----------------------------------|
| Testing mock calls                   | Test actual outcome              |
| Mocking MoveParser in BotRunner test | Use real MoveParser              |
| `time.sleep(N)`                      | Use condition-based waiting      |
| Asserting on internal state          | Assert on observable output      |
| 500-line test function               | Split into focused tests         |
| Copy-pasted tests with tiny diffs    | Use @pytest.mark.parametrize     |

## Quality Checklist

- [ ] Happy path covered
- [ ] Error conditions handled
- [ ] Boundary/edge cases included
- [ ] Real dependencies used (minimal mocking)
- [ ] Tests survive renaming internal fields/methods
- [ ] Test names describe behavior, not implementation
- [ ] No test depends on execution order of other tests

## Language-Specific Patterns
- **Python**: See [references/python.md](references/python.md)

---
**Remember:** Behavior over implementation. Real over mocked.
Outputs over internals.
