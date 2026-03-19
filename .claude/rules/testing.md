---
globs: ["tests/**", "test_*", "*_test.py", "conftest.py"]
---

# Правила для тестовых файлов

При работе с тестами ВСЕГДА загружай:
1. Skill(writing-tests) — философия тестирования
2. Skill(pytest-patterns) — механика pytest
3. Skill(project-test-generator) — оркестрация проекта

Для файлов в `tests/property/` дополнительно:
4. Skill(property-based-testing)

## Обязательные принципы
- НИКОГДА не мокай внутренние модули проекта (move_parser, notation_converter, prompt_builder, pricing, tracer, settings, constants)
- ВСЕГДА используй реальные зависимости где возможно
- Внешние HTTP-вызовы (LLM API, Arena API, OpenRouter) мокать через `respx`
- ВСЕГДА запускай `pytest <file> -v` после написания тестов
- Используй parametrize вместо копипасты похожих тестов
- Имена тестов описывают ПОВЕДЕНИЕ: `test_parser_extracts_move_from_json_with_thinking`
- Минимум 1 поведенческое утверждение на тест
- Для файловых операций (Settings, Tracer) используй `tmp_path` fixture
- asyncio-тесты используй `pytest.mark.asyncio` с `asyncio_mode = "auto"`
- gui.py — тестируется двумя способами:
  1. Бизнес-логика извлекается в gui_helpers.py и тестируется как обычные функции
  2. UI-сценарии тестируются через `nicegui.testing.Screen`
- При тестировании GUI — проверять поведение (что показывается, что происходит), а не стили/layout
