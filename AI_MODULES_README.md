# AI Modules Documentation

## Обзор

Папка `ai/` содержит 6 модулей для автоматизированной генерации SMM-контента:

1. **agent.py** - главный агент (уже существовал)
2. **analyzer.py** - анализ контента конкурентов
3. **writer.py** - генерация SEO-статей
4. **seo_checker.py** - проверка SEO-качества
5. **self_reviewer.py** - самопроверка и улучшение текстов
6. **image_gen.py** - генерация изображений через Nano Banana API

---

## 1. ContentAnalyzer (`analyzer.py`)

**Назначение:** Анализирует статьи конкурентов и выявляет ключевые тезисы, слабые места, SEO-ключи.

**Модель:** `openai/gpt-4o-mini`

### Использование

```python
from ai.analyzer import ContentAnalyzer

analyzer = ContentAnalyzer()

# Анализ статьи конкурента
analysis = await analyzer.analyze(
    title="Как правильно питаться",
    content="Полный текст статьи конкурента..."
)

print(analysis)
# Вернёт структурированный анализ:
# 1) 3-4 главных тезиса
# 2) Слабые места и что не раскрыто
# 3) Потенциальные SEO-ключи по теме
# 4) Угол атаки для более сильной статьи
```

### Параметры

- `title: str` - заголовок статьи
- `content: str` - текст статьи

### Возвращает

`str` - структурированный анализ

---

## 2. SEOWriter (`writer.py`)

**Назначение:** Генерирует SEO-оптимизированные статьи в формате Markdown.

**Модель:** Настраивается (по умолчанию `anthropic/claude-3-5-sonnet`)

### Использование

```python
from ai.writer import SEOWriter

writer = SEOWriter()

# Генерация статьи
article = await writer.write(
    analysis="Результат анализа от ContentAnalyzer",
    tone="профессиональный",
    keywords=["правильное питание", "здоровье", "диета"],
    llm_model="anthropic/claude-3-5-sonnet"  # опционально
)

print(article)
# Вернёт полноценную статью в Markdown с H1, H2/H3, списками, CTA
```

### Параметры

- `analysis: str` - результат анализа контента
- `tone: str` - тон статьи ("профессиональный", "дружелюбный", "экспертный")
- `keywords: list[str] | None` - список SEO-ключей (опционально)
- `llm_model: str` - модель для генерации (по умолчанию Claude 3.5 Sonnet)

### Возвращает

`str` - SEO-статья в Markdown

---

## 3. SEOChecker (`seo_checker.py`)

**Назначение:** Проверяет SEO-качество сгенерированных статей.

**Модель:** `openai/gpt-4o-mini`

### Использование

```python
from ai.seo_checker import SEOChecker

checker = SEOChecker()

# Проверка статьи
result = await checker.check(
    text="# Заголовок\n\nТекст статьи...",
    keywords=["правильное питание", "здоровье"]
)

print(result)
# {
#     "score": 85,
#     "has_h1": True,
#     "has_h2": True,
#     "length": 2500,
#     "keyword_density": 1.2,
#     "issues": [],
#     "passed": True
# }
```

### Параметры

- `text: str` - текст статьи
- `keywords: list[str] | None` - ключевые слова для проверки плотности

### Возвращает

```python
{
    "score": int,              # 0-100, общий SEO-рейтинг
    "has_h1": bool,            # есть ли H1 заголовок
    "has_h2": bool,            # есть ли H2 заголовки
    "length": int,             # длина текста в символах
    "keyword_density": float,  # плотность ключевых слов (%)
    "issues": list[str],       # список проблем
    "passed": bool             # score >= 70
}
```

### Логирование

- Если `passed=False`, в логах будет **WARNING** с перечислением `issues`
- Если `passed=True`, в логах будет **SUCCESS** с метриками

---

## 4. SelfReviewer (`self_reviewer.py`)

**Назначение:** Самостоятельно проверяет и улучшает тексты, устраняя выявленные проблемы.

**Модель:** `anthropic/claude-3-5-sonnet`

### Использование

```python
from ai.self_reviewer import SelfReviewer

reviewer = SelfReviewer()

# Улучшение текста
issues = ["Отсутствуют H2 заголовки", "Статья слишком короткая"]
improved_text = await reviewer.review(
    text="Исходный текст статьи...",
    issues=issues
)

print(improved_text)
# Вернёт улучшенную версию текста с устранёнными проблемами
```

### Параметры

- `text: str` - исходный текст статьи
- `issues: list[str]` - список проблем для устранения

### Возвращает

`str` - улучшенный текст

### Оптимизация

**Важно:** Если `issues` пустой, метод сразу возвращает исходный текст **без запроса к API** (экономия токенов).

---

## 5. NanoBananaGenerator (`image_gen.py`)

**Назначение:** Генерирует SMM-баннеры для статей через Nano Banana 2 API.

**API:** `https://api.nanobanana.com/v2/generate`

### Использование

```python
from ai.image_gen import NanoBananaGenerator

image_gen = NanoBananaGenerator()

# Генерация баннера
image_url = await image_gen.generate(
    title="10 правил здорового питания",
    topic="правильное питание и здоровье"
)

if image_url:
    print(f"Изображение: {image_url}")
else:
    print("Не удалось сгенерировать изображение")
```

### Параметры

- `title: str` - заголовок статьи (будет на баннере)
- `topic: str` - тема статьи для контекста

### Возвращает

- `str` - URL сгенерированного изображения
- `None` - если API key не задан или произошла ошибка

### Конфигурация

В `.env` файле:
```
NANO_BANANA_API_KEY=your_api_key_here
```

Если ключ не задан, метод сразу возвращает `None` с **WARNING** в логах.

### Автоматический промпт

Генерируется автоматически:
```
Яркий SMM-баннер для статьи. Тема: {topic}.
Текст на баннере: '{title}'.
Стиль: современный, градиент, профессиональный дизайн.
Кириллица, русский язык.
```

Параметры изображения:
- Ширина: 1200px
- Высота: 630px
- Steps: 30

---

## Общие характеристики всех модулей

### 1. AsyncOpenAI клиент

Все модули используют:
```python
AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY
)
```

### 2. Type hints

Все функции и методы имеют полные type hints для статической типизации.

### 3. Loguru logging

- `logger.info()` - информационные сообщения
- `logger.success()` - успешное выполнение
- `logger.warning()` - предупреждения (429, пустые ключи API)
- `logger.error()` - ошибки с подробным контекстом
- `logger.debug()` - отладочная информация

### 4. Try/except блоки

Все API-запросы обёрнуты в try/except с логированием ошибок.

### 5. Exponential backoff (max 3 retry)

При ошибках:
- Попытка 1: задержка 1 секунда (2^0)
- Попытка 2: задержка 2 секунды (2^1)
- Попытка 3: задержка 4 секунды (2^2)

После 3 неудачных попыток выбрасывается `RuntimeError`.

---

## Пример полного рабочего процесса

```python
from ai.analyzer import ContentAnalyzer
from ai.writer import SEOWriter
from ai.seo_checker import SEOChecker
from ai.self_reviewer import SelfReviewer
from ai.image_gen import NanoBananaGenerator

async def generate_full_article(
    competitor_title: str,
    competitor_content: str,
    tone: str = "профессиональный",
    keywords: list[str] = None
):
    # 1. Анализ конкурента
    analyzer = ContentAnalyzer()
    analysis = await analyzer.analyze(competitor_title, competitor_content)
    
    # 2. Написание статьи
    writer = SEOWriter()
    article = await writer.write(
        analysis=analysis,
        tone=tone,
        keywords=keywords,
        llm_model="anthropic/claude-3-5-sonnet"
    )
    
    # 3. Проверка SEO
    checker = SEOChecker()
    seo_result = await checker.check(article, keywords)
    
    # 4. Если есть проблемы - улучшаем
    if not seo_result["passed"]:
        reviewer = SelfReviewer()
        article = await reviewer.review(article, seo_result["issues"])
        
        # Повторная проверка
        seo_result = await checker.check(article, keywords)
    
    # 5. Генерация изображения
    image_gen = NanoBananaGenerator()
    image_url = await image_gen.generate(
        title=competitor_title,
        topic=", ".join(keywords) if keywords else competitor_title
    )
    
    return {
        "article": article,
        "seo_score": seo_result["score"],
        "image_url": image_url,
        "passed": seo_result["passed"]
    }
```

---

## Настройка окружения

В `.env` файле:
```
OPENROUTER_API_KEY=your_openrouter_key
NANO_BANANA_API_KEY=your_nano_banana_key
```

В `requirements.txt`:
```
openai>=1.0
aiohttp
loguru
pydantic-settings>=2.0
```

---

## Метрики производительности

### Скорость работы модулей

| Модуль | Средняя задержка | Модель |
|--------|------------------|--------|
| ContentAnalyzer | 2-5 сек | gpt-4o-mini |
| SEOWriter | 10-20 сек | claude-3-5-sonnet |
| SEOChecker | 2-5 сек | gpt-4o-mini |
| SelfReviewer | 10-15 сек | claude-3-5-sonnet |
| NanoBananaGenerator | 30-60 сек | Nano Banana API |

### Стоимость (примерная)

| Модуль | Стоимость за вызов |
|--------|-------------------|
| ContentAnalyzer | $0.001-0.005 |
| SEOWriter | $0.02-0.05 |
| SEOChecker | $0.001-0.003 |
| SelfReviewer | $0.01-0.03 |
| NanoBananaGenerator | Зависит от API |

---

## Решение проблем

### "Module not found" ошибки

Установите зависимости:
```bash
pip install -r requirements.txt
```

### "API key not configured"

Проверьте `.env` файл:
```bash
cat .env | grep OPENROUTER_API_KEY
cat .env | grep NANO_BANANA_API_KEY
```

### "Rate limit exceeded" (429)

Модули автоматически делают exponential backoff при получении 429. Если ошибка сохраняется, подождите несколько минут.

### Низкий SEO score

Проверьте `issues` в результате `SEOChecker.check()` и используйте `SelfReviewer.review()` для улучшения.

---

## Лицензия

Все модули используют MIT License.
