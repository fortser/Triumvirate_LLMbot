# Plan: SmartBot-Powered LLM Move Evaluation

## Executive Summary

SmartBot `evaluation/` — полноценный шахматный движок для трёхсторонних шахмат с 5-компонентной системой оценки, тактической верификацией и pseudo-SEE. Его можно использовать как **оракул** для объективной оценки ходов LLM-моделей — аналог Stockfish в обычных шахматах.

**Ключевое открытие:** LLM-бот сохраняет `position_3pf` в трейсах, а SmartBot умеет восстанавливать полный `GameState` из 3PF через `parse_3pf()`. Это значит, что для каждого хода из лога LLM-бота мы можем:
1. Восстановить позицию → `GameState`
2. Прогнать SmartBot evaluation pipeline → рейтинг каждого легального хода
3. Сравнить ход LLM с лучшим ходом SmartBot → объективный `rating_gap`

---

## Текущие проблемы оценки LLM-моделей

| Проблема | Детали |
|----------|--------|
| **Нет эталона** | Система не знает, какой ход был бы лучшим |
| **Activity = buried_delta** | Движение к центру ≠ хороший ход; отступление может быть сильнее |
| **Tactical = check + capture** | Игнорирует тихие позиционные ходы, профилактику, контроль пространства |
| **Нет сравнения с альтернативами** | Неизвестно, сколько из легальных ходов были лучше выбранного |
| **Composite веса фиксированы** | 35/30/20/15 не калиброваны эмпирически |
| **Нет декомпозиции хода** | Непонятно, ход хорош за счёт material/tactical/positional/defense? |

---

## Идеи и возможности

### БЛОК 1: SmartBot как оракул (Rating Gap Analysis)

#### 1.1. Offline Move Evaluator — `smartbot_evaluator.py`

**Суть:** Скрипт, который для каждого трейса LLM-бота:
- Берёт `position_3pf` из `server_state_raw`
- Восстанавливает `GameState` через `parse_3pf()`
- Запускает полный SmartBot pipeline: `find_all_threats()` → `analyze_defenses()` → `calculate_move_rating()` для каждого легального хода → `tactical_verify()` → `select_move()`
- Находит ход LLM в списке оценённых ходов
- Записывает: `smartbot_best_rating`, `llm_move_rating`, `rating_gap`, `llm_move_rank`, `total_candidates`

**Данные из SmartBot, доступные для каждого хода:**
```python
MoveRating:
  rating: int                    # интегральный рейтинг
  components:
    material: int                # выгода от взятия (exchange evaluation)
    defense: int                 # бонус за защиту от угрозы
    tactical: int                # шах, вилка, создание угроз
    positional: int              # централизация, мобильность, promotion
    risk: int                    # штраф за подставление фигуры
  gives_check: bool
  gives_mate: bool
  is_capture: bool
  is_defense: bool
  exchange_result: ExchangeResult  # SEE с recapture, continuation
  threat_addressed: Threat         # какую угрозу ход устраняет
```

**Ценность:** Это даёт объективную числовую оценку каждого хода LLM. `rating_gap = best_rating - llm_rating` — главная метрика качества.

#### 1.2. Per-Move Component Breakdown

Для каждого хода LLM записываем 5 компонентов SmartBot-рейтинга:
- `material_component` — правильно ли LLM оценивает размены?
- `defense_component` — видит ли LLM угрозы?
- `tactical_component` — использует ли тактические возможности?
- `positional_component` — понимает ли позиционные нюансы?
- `risk_component` — подставляет ли фигуры?

**Ценность:** Позволяет определить *тип* слабости модели, а не только "модель плохо играет". Например:
- Модель A: хорошо в тактике, плохо в defence → не видит угрозы
- Модель B: хорошо в defence, плохо в positional → пассивная игра

#### 1.3. SmartBot Rating Gap как primary metric

Заменить текущий `auto_composite` (reliability + activity + tactical + efficiency) на метрику, основанную на `rating_gap`:

```
quality_score = 1 - normalized(median_rating_gap)
```

Или расширить composite:
```
auto_composite = 0.25 × reliability
               + 0.35 × smartbot_quality   # NEW: median rating_gap, нормализован
               + 0.15 × tactical_events    # check_rate, capture_win_rate
               + 0.10 × efficiency
               + 0.15 × win_rate
```

---

### БЛОК 2: Threat Awareness Analysis

#### 2.1. Threat Detection Rate

SmartBot находит все угрозы через `find_all_threats()`. Мы можем:
- Для каждой позиции получить список угроз от SmartBot
- Проверить, адресовал ли ход LLM самую приоритетную угрозу (`find_threat_addressed()`)
- Метрика: `threat_addressed_rate` = % ходов, где LLM правильно реагирует на угрозу

**Данные SmartBot:**
```python
Threat:
  severity: CRITICAL/HIGH/MEDIUM/LOW
  target: Piece          # какая фигура под угрозой
  attacker: Piece        # кто угрожает
  moves_until_attack: int
  is_real: bool          # выгоден ли размен противнику
  exchange_value: int    # потери при размене
  third_player_factor: AMPLIFIER/DETERRENT/NEUTRAL
```

#### 2.2. Critical Threat Handling

Отдельная метрика: `critical_threat_response_rate` = когда SmartBot видит CRITICAL угрозу (шах или два противника атакуют одну фигуру), реагирует ли LLM адекватно?

Можно также проверять: выбирает ли LLM лучшую защиту из доступных (`best_defense` vs выбранный ход).

#### 2.3. Missed Mate Detection

SmartBot проверяет `gives_mate` для каждого хода. Если среди легальных ходов есть мат, а LLM его не нашёл — это `missed_mate`. Метрика: `missed_mate_count` и `mate_found_rate`.

---

### БЛОК 3: Tactical Verification от SmartBot

#### 3.1. Blunder Detection

SmartBot's `tactical_verify()` проверяет:
- **Мат в 1 ход от противника** после нашего хода — `_check_mate_threat()`
- **Discovered attacks** — вскрытые атаки на свои фигуры — `_check_discovered_attacks()`

Для каждого хода LLM можно проверить: ведёт ли ход к мату от противника? Открывает ли атаку на свою фигуру?
- Метрика: `blunder_rate` = % ходов, после которых противник мог поставить мат
- Метрика: `discovery_blunder_rate` = % ходов, открывающих атаку на свои фигуры

#### 3.2. Material Loss Analysis

Используя `calculate_exchange()` из SmartBot, оценить: привёл ли ход LLM к материальным потерям?
- `risk_penalty` > 0 означает, что фигура поставлена на атакованное поле без защиты
- Метрика: `avg_risk_penalty` = средний штраф за подставление фигур

---

### БЛОК 4: Political & Three-Player Dynamics

#### 4.1. Political Move Correctness

SmartBot использует `political_matrix` для выбора цели:
```python
'political_matrix': {
    'leader':   {'leader': 0, 'middle':  0, 'underdog': -20},
    'middle':   {'leader': 50, 'middle':  0, 'underdog': -30},
    'underdog': {'leader': 70, 'middle': 20, 'underdog':   0},
}
```

Можно оценить: атакует ли LLM правильную цель?
- `get_player_role()` определяет роль каждого игрока (leader/middle/underdog)
- Если LLM атакует underdog будучи leader — это стратегическая ошибка
- Метрика: `political_correctness_rate` = % ходов с правильным выбором цели

#### 4.2. Third Player Awareness

Из `third_player_factor` в анализе угроз:
- Когда третий игрок AMPLIFIER (тоже атакует нашу фигуру) — ситуация критическая
- Когда третий игрок DETERRENT (атакует нашего атакующего) — можно рискнуть
- Метрика: `third_player_awareness` — учитывает ли LLM расстановку третьего игрока в thinking

---

### БЛОК 5: Позиционная оценка (Position Quality)

#### 5.1. Material Advantage Tracking

SmartBot вычисляет `get_material_advantage()` — разницу между материалом игрока и средним противников. Можно трекать для каждого хода LLM:
- `material_advantage_before` и `material_advantage_after`
- `material_advantage_trend` по ходам партии — растёт или падает?

#### 5.2. Trapped Pieces Detection

SmartBot проверяет `trapped_pieces_penalty()` — запертые фигуры с 0-2 ходами.
- Метрика: приводит ли ход LLM к увеличению числа запертых фигур?
- `trapped_piece_delta` = разница штрафов до и после хода

#### 5.3. Game Phase Awareness

`get_game_phase()` и `is_endgame()` — SmartBot различает фазы игры.
- В эндшпиле пешечное продвижение важнее (×2.5 бонус)
- Метрика: адаптирует ли LLM стратегию под фазу игры?

---

### БЛОК 6: Сравнение SmartBot vs LLM в реальных партиях

#### 6.1. Dual Evaluation Mode

Для каждой партии LLM-бота параллельно "проигрывать" ходы SmartBot-а:
- На каждой позиции записывать: `llm_move`, `smartbot_best_move`, `rating_gap`
- Строить графики расхождения по ходам партии
- Определять фазы партии, где LLM играет хуже/лучше SmartBot

#### 6.2. Move Category Classification

Классифицировать каждый ход LLM по шкале SmartBot:
```
Brilliant:  llm_rating > smartbot_best × 0.9  (< 10% потерь)
Good:       llm_rating > smartbot_best × 0.7  (< 30% потерь)
Inaccuracy: llm_rating > smartbot_best × 0.3  (< 70% потерь)
Mistake:    llm_rating > 0, но < smartbot_best × 0.3
Blunder:    llm_rating < 0 (ход активно вредит позиции)
```

Метрика: распределение ходов по категориям для каждой модели.

#### 6.3. Win Contribution Score

Не просто win/loss, а вклад каждого хода в результат:
- Сумма `rating_gap` за всю партию = совокупные потери от неоптимальных ходов
- `avg_centipawn_loss` (в терминах SmartBot-оценки) — аналог ACL в обычных шахматах

---

### БЛОК 7: Улучшение метрик Smartbot trace_parser

#### 7.1. Перенос 28 метрик из trace_parser

SmartBot's `trace_parser/metrics.py` вычисляет 28 метрик, разделённых на Tier 1/2/3. Многие из них полезны и для LLM-оценки:

**Tier 1 (ключевые):**
- `avg_rating_gap` — медиана разницы между лучшим и выбранным ходом (уже есть у SmartBot, нужно для LLM)
- `p10_selected_rating` — 10-й перцентиль рейтинга выбранных ходов (показывает "дно" качества)
- `selected_rank_1_pct` — % ходов, где модель выбрала лучший ход

**Tier 2:**
- `capture_win_rate_pct` — % выгодных взятий (exchange_net >= 0)
- `median_rating_spread` — разброс рейтингов кандидатов (complexity metric)

**Tier 3:**
- `component_averages` — средние по 5 компонентам
- `material_advantage_by_quarter` — материальное преимущество по четвертям партии

#### 7.2. Wilson Score CI

SmartBot использует `wilson_ci()` для confidence intervals вместо простого mean. Это даёт более надёжные оценки при малом количестве игр. Стоит перенести в LLM metrics.

#### 7.3. Complexity Buckets

SmartBot группирует метрики по сложности позиции (число легальных ходов): `legal_1-10`, `legal_11-20`, `legal_21-30`, `legal_31+`. Это важно: модель может хорошо играть в простых позициях и плохо в сложных.

---

### БЛОК 8: Hallucination Detection через Board State

#### 8.1. Automated Board Accuracy Check

Сейчас hallucination detection делается вручную агентом model-evaluator. Но из `server_state_raw.board` (доступен в каждом трейсе) и `llm_responses[].raw_response` (thinking) можно автоматизировать:

1. Извлечь координаты из thinking (regex для серверной и TRIUMVIRATE нотаций)
2. Для каждой упомянутой координаты проверить: совпадает ли фигура на доске с тем, что описывает LLM?
3. Метрика: `board_accuracy_rate` = % корректных упоминаний фигур

#### 8.2. Move Legality Awareness

Из `legal_moves` в трейсе: проверить, упоминает ли LLM в thinking только легальные ходы или "рассматривает" нелегальные варианты.

---

### БЛОК 9: Exchange Quality Analysis

#### 9.1. SEE-based Capture Evaluation

SmartBot's `calculate_exchange()` реализует pseudo-SEE (Static Exchange Evaluation) с учётом:
- Recapture opponents
- Check после взятия (противник не может recapture)
- Continuation (наш ответ на recapture)
- Simplification bonus/penalty при материальном преимуществе/отставании
- ExchangeClassification: WINNING/FAVORABLE/EQUAL/UNFAVORABLE/LOSING

Для каждого взятия LLM можно получить: было ли взятие WINNING/LOSING по SEE?
- Метрика: `exchange_quality` = распределение по ExchangeClassification

---

### БЛОК 10: Архитектура реализации

#### 10.1. Adapter Module — `smartbot_adapter.py`

Изолированный модуль, который:
- Добавляет пути SmartBot в `sys.path` (read-only)
- Импортирует нужные функции: `parse_3pf`, `find_all_threats`, `analyze_defenses`, `calculate_move_rating`, `tactical_verify`, `select_move`, `build_move`
- Предоставляет API: `evaluate_position(position_3pf, legal_moves) → SmartBotEvaluation`

```python
@dataclass
class SmartBotEvaluation:
    best_move: str           # "FROM TO"
    best_rating: int
    all_ratings: list[dict]  # [{move, rating, components, ...}]
    threats: list[dict]
    threat_summary: dict
    game_phase: float
    material_advantage: int
    player_role: str         # leader/middle/underdog
```

#### 10.2. Интеграция в metrics pipeline

```
trace_analyzer/
  move_metrics.py        # существующие per-move метрики (без изменений)
  smartbot_evaluator.py  # NEW: SmartBot evaluation per move
  aggregator.py          # расширить: smartbot-based метрики
  metrics.py             # CLI: добавить --smartbot flag
```

#### 10.3. Performance Considerations

SmartBot evaluation на одну позицию = ~50-200ms (зависит от числа фигур и легальных ходов). Для 1000 ходов = ~100 секунд. Приемлемо для offline analysis.

Можно оптимизировать:
- Параллелизация через `concurrent.futures.ProcessPoolExecutor`
- Кэширование `parse_3pf` результатов
- Пропуск ходов с `outcome = fallback_random` (и так рандомные)

---

## Приоритизация

| Приоритет | Идея | Ценность | Сложность |
|-----------|------|----------|-----------|
| **P0** | 1.1 SmartBot Evaluator + rating_gap | Критическая — даёт объективный эталон | Средняя |
| **P0** | 1.2 Component breakdown | Высокая — определяет тип слабости | Низкая (часть 1.1) |
| **P1** | 3.1 Blunder detection | Высокая — ловит критические ошибки | Средняя |
| **P1** | 2.1 Threat detection rate | Высокая — оценивает оборонительное мышление | Средняя |
| **P1** | 6.2 Move category classification | Высокая — наглядная шкала качества | Низкая (после 1.1) |
| **P2** | 9.1 Exchange quality (SEE) | Средняя — оценивает качество разменов | Средняя |
| **P2** | 4.1 Political correctness | Средняя — уникальна для 3-player | Средняя |
| **P2** | 5.1 Material tracking | Средняя — трекинг тренда | Низкая |
| **P2** | 7.1 Wilson CI + complexity buckets | Средняя — статистическая надёжность | Низкая |
| **P3** | 8.1 Automated hallucination detection | Средняя — пока делается вручную | Высокая |
| **P3** | 6.1 Dual evaluation mode | Интересно, но требует визуализации | Высокая |
| **P3** | 4.2 Third player awareness | Нишевая, требует NLP анализа thinking | Высокая |

---

## Техническая реализация P0

### Шаг 1: `smartbot_adapter.py`

```python
"""Адаптер для использования SmartBot evaluation в LLM metrics pipeline.

Импортирует evaluation-код SmartBot (read-only) и предоставляет
единый API для оценки позиций из LLM trace-файлов.
"""
import sys
from pathlib import Path
from dataclasses import dataclass

SMARTBOT_ROOT = Path("T:/test_python/Triumvirate_Smartbot")
# Добавляем SmartBot в sys.path для импортов
if str(SMARTBOT_ROOT) not in sys.path:
    sys.path.insert(0, str(SMARTBOT_ROOT))

from game_io.position_3pf import parse_3pf
from board.coordinates import Coordinate
from bot.move_builder import build_move
from evaluation.threats import find_all_threats
from evaluation.defense import analyze_defenses
from evaluation.rating import calculate_move_rating
from evaluation.tactical import tactical_verify
from evaluation.selection import select_move
from evaluation.piece_values import get_material_advantage, get_player_role, get_game_phase

@dataclass
class MoveEvaluation:
    move_from: str
    move_to: str
    rating: int
    rank: int  # 1 = лучший
    components: dict  # material, defense, tactical, positional, risk
    gives_check: bool
    gives_mate: bool
    is_capture: bool
    is_defense: bool
    exchange_classification: str | None

@dataclass
class PositionEvaluation:
    total_legal_moves: int
    best_move: MoveEvaluation
    llm_move: MoveEvaluation | None
    rating_gap: int
    llm_rank: int
    all_moves: list[MoveEvaluation]
    # Position context
    threats_count: int
    critical_threats: int
    material_advantage: int
    player_role: str  # leader/middle/underdog
    game_phase: float  # 1.0=opening, 0.0=endgame
    # Blunder detection
    allows_mate: bool  # ход LLM позволяет противнику мат?
    has_discovered_attack: bool  # ход открывает атаку на свою фигуру?

def evaluate_position(
    position_3pf: str,
    legal_moves: dict,
    llm_move_from: str,
    llm_move_to: str,
) -> PositionEvaluation:
    """Полная оценка позиции и хода LLM через SmartBot pipeline."""
    ...
```

### Шаг 2: Расширение `move_metrics.py`

Добавить поля в `MoveMetrics`:
```python
# SmartBot evaluation
smartbot_rating: int = 0          # рейтинг хода LLM по SmartBot
smartbot_best_rating: int = 0     # рейтинг лучшего хода
smartbot_rating_gap: int = 0      # разница (ключевая метрика)
smartbot_rank: int = 0            # ранг хода LLM среди всех
smartbot_total_moves: int = 0     # сколько ходов оценено
smartbot_components: dict = {}    # 5 компонентов
smartbot_allows_mate: bool = False
smartbot_material_advantage: int = 0
smartbot_player_role: str = ""
smartbot_game_phase: float = 0.0
smartbot_move_category: str = ""  # brilliant/good/inaccuracy/mistake/blunder
```

### Шаг 3: Расширение `aggregator.py`

Новые поля в `ModelStats`:
```python
# SmartBot quality
avg_rating_gap: float = 0.0
median_rating_gap: float = 0.0
p10_rating_gap: float = 0.0  # worst 10%
rank_1_rate: float = 0.0     # % лучших ходов
blunder_rate: float = 0.0
brilliant_rate: float = 0.0
avg_material_advantage: float = 0.0

# Move category distribution
category_brilliant: float = 0.0
category_good: float = 0.0
category_inaccuracy: float = 0.0
category_mistake: float = 0.0
category_blunder: float = 0.0

# Component weaknesses
weakness_material: float = 0.0   # avg негативный material component
weakness_defense: float = 0.0
weakness_tactical: float = 0.0
weakness_positional: float = 0.0
weakness_risk: float = 0.0
```

---

## Ожидаемый результат

После реализации P0 мы получим:

1. **Объективный рейтинг каждого хода** — не "модель сделала check" (что может быть плохо), а "модель сделала ход на 87% оптимальности SmartBot"
2. **Типизация слабостей** — "модель X плохо видит угрозы, модель Y подставляет фигуры"
3. **Move category distribution** — наглядное: "40% brilliant, 30% good, 20% inaccuracy, 10% mistake"
4. **Замена subjective composite** на SmartBot-calibrated quality score
5. **Автоматическое обнаружение blunder'ов** — ходы, после которых противник мог поставить мат

Всё это без участия LLM-агента — чисто детерминированная алгоритмическая оценка.
