

# Triumvirate Trace Analyzer

## Назначение

Веб-инструмент для визуального анализа и отладки trace-логов бота Triumvirate LLM Bot. Позволяет быстро находить ошибки, сравнивать модели, изучать reasoning и экспортировать выборки для глубокого анализа.

## Данные

Работает с JSON trace-файлами (`move_*.json`), которые бот сохраняет в `logs/game_*/`. Рассчитан на масштаб до ~10 игр × 30 ходов.

## Функционал

**Tab 1 — Overview.** Дашборд: карточки метрик по играм, таблица сравнения моделей, scatter-графики (время/токены/стоимость по ходам), секция аномалий (медленные ходы, ретраи, ошибки).

**Tab 2 — Moves.** Сортируемая таблица всех ходов с фильтрами по модели, исходу, игре. Цветовые индикаторы времени, стоимости, ретраев. Поиск по тексту reasoning. Клик по строке открывает детальный просмотр.

**Tab 3 — Thinking Gallery.** Карточки с полным текстом reasoning каждого хода. Фильтры, сортировка, мультивыбор. Экспорт выбранных ходов в Markdown или JSON в буфер обмена.

**Tab 4 — Move Detail.** Детальный разбор одного хода: 7 раскрываемых секций (Thinking, Prompt Pipeline, LLM Request/Response, Parser, Server, Statistics, Raw JSON). Навигация Prev/Next. Кнопки копирования каждой секции в MD/JSON.

## Стек

Python, NiceGUI (≥2.0), Apache ECharts (через `ui.echart`).

## Структура проекта

```
trace_analyzer/
├── app.py                 # точка входа, layout, табы
├── data_loader.py         # загрузка и нормализация trace-файлов
├── export_utils.py        # форматирование в Markdown / JSON
├── requirements.txt       # nicegui>=2.0
└── views/
    ├── __init__.py
    ├── overview.py        # Tab 1 — дашборд
    ├── moves_table.py     # Tab 2 — таблица ходов
    ├── thinking_gallery.py # Tab 3 — галерея reasoning
    └── move_detail.py     # Tab 4 — детали хода
```

## Установка и запуск

```bash
cd trace_analyzer
pip install -r requirements.txt
```

**Базовый запуск** (логи ищутся в `../logs` или `./logs`):
```bash
python app.py
```

**Указать папку с логами:**
```bash
python app.py --logs /path/to/logs
```

**Указать порт и хост:**
```bash
python app.py --logs ./logs --port 8091 --host 0.0.0.0
```

Интерфейс доступен в браузере: `http://localhost:8091`