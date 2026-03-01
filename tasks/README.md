# SMM Factory - Celery Tasks

Автоматизированная система парсинга, генерации и публикации контента с использованием Celery и Redis.

## Структура задач

### 1. `tasks/celery_app.py`
Конфигурация Celery приложения:
- Broker: Redis
- Backend: Redis
- Сериализация: JSON
- Таймзона: Europe/Moscow
- `task_acks_late=True` - задача не удаляется из очереди пока не выполнена

### 2. `tasks/parse_task.py`
Задача `parse_and_generate` - полный конвейер парсинга и генерации:

**Что делает:**
1. Получает активные источники (`Source`) из БД
2. Получает настройки пользователя (`UserSettings`)
3. Собирает URL для обработки:
   - Из каждого источника: `fetch_links_from_page()`
   - Из SERP keywords: `SerpParser.search_all()`
4. Фильтрует дубликаты и существующие статьи
5. Для каждого нового URL:
   - Парсит статью (`ArticleParser`)
   - Анализирует контент (`ContentAnalyzer`)
   - Генерирует текст (`SEOWriter`)
   - Проверяет SEO (`SEOChecker`)
   - Улучшает при необходимости (`SelfReviewer`)
   - Добавляет UTM метки (`UTMInjector`)
   - Генерирует изображение (`NanaBananaGenerator`)
   - Сохраняет пост в БД
   - Публикует или уведомляет админа

**Retry:** 3 попытки с экспоненциальной задержкой (300s, 600s, 1200s)

### 3. `tasks/publish_task.py`
Задача `publish_post` - публикация поста на платформы:

**Что делает:**
1. Получает пост из БД по `post_id`
2. Получает настройки пользователя
3. Публикует в Telegram каналы (из `tg_channels`)
4. Публикует на VC.ru (если `VC_SESSION_TOKEN` задан)
5. Публикует на RBC Companies (если `RBC_LOGIN` задан)
6. Обновляет статус поста в БД

**Retry:** 3 попытки с экспоненциальной задержкой (60s, 120s, 240s)

## Установка и запуск

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Настройка .env

```env
# Redis
REDIS_URL=redis://localhost:6379/0

# Database
DATABASE_URL=sqlite:///./smm_factory.db

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# VC.ru (опционально)
VC_SESSION_TOKEN=your_vc_token

# RBC (опционально)
RBC_LOGIN=your_email@example.com
RBC_PASSWORD=your_password
```

### 3. Запуск Redis

```bash
# Локально
redis-server

# Или через Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### 4. Инициализация БД

```bash
python start_worker.py
```

### 5. Запуск Celery Worker

```bash
# Воркер
celery -A tasks.celery_app worker --loglevel=info

# Воркер + Beat (для периодических задач)
celery -A tasks.celery_app worker --beat --loglevel=info

# Только Beat
celery -A tasks.celery_app beat --loglevel=info
```

### 6. Мониторинг (опционально)

```bash
# Flower - веб-интерфейс для мониторинга
pip install flower
celery -A tasks.celery_app flower

# Открыть http://localhost:5555
```

## Использование

### Запуск задачи парсинга вручную

```python
from tasks import parse_and_generate

# Асинхронно (добавить в очередь)
result = parse_and_generate.delay()
print(f"Task ID: {result.id}")

# Синхронно (для тестирования)
result = parse_and_generate.apply()
print(result.get())
```

### Запуск задачи публикации

```python
from tasks import publish_post

# Асинхронно
result = publish_post.delay(post_id=1)

# Синхронно
result = publish_post.apply(args=[1])
print(result.get())
```

### Периодические задачи

Добавьте в `tasks/celery_app.py`:

```python
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'parse-every-hour': {
        'task': 'tasks.parse_task.parse_and_generate',
        'schedule': crontab(minute=0),  # Каждый час
    },
}
```

## Модели данных

### Source
Источники контента для парсинга:
- `url` - URL источника
- `name` - название источника
- `is_active` - активен ли источник
- `last_parsed_at` - время последнего парсинга

### UserSettings
Настройки пользователя:
- `serp_keywords` - ключевые слова для SERP
- `internal_links` - внутренние ссылки для UTM
- `utm_template` - шаблон UTM меток
- `tone` - тон текста (professional, casual, etc.)
- `keywords` - SEO ключевые слова
- `selected_llm` - выбранная LLM модель
- `tg_channels` - список Telegram каналов
- `is_auto_publish` - автоматическая публикация

### Article
Распарсенные статьи:
- `url` - URL статьи
- `title` - заголовок
- `content` - содержание
- `is_processed` - обработана ли статья
- `parsed_at` - время парсинга

### Post
Сгенерированные посты:
- `title` - заголовок
- `text` - текст поста
- `image_url` - URL изображения
- `status` - статус (pending, published, failed)
- `published_at` - время публикации

### ParsingHistory
История попыток парсинга:
- `url` - URL
- `status` - статус (success, failed, skipped)
- `error_message` - сообщение об ошибке
- `attempted_at` - время попытки

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                     Celery Worker                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────┐         ┌────────────────┐             │
│  │ parse_and_     │         │ publish_post   │             │
│  │ generate       │────────▶│                │             │
│  └────────────────┘         └────────────────┘             │
│         │                           │                       │
│         ▼                           ▼                       │
│  ┌─────────────────────────────────────────┐               │
│  │          Redis Queue                     │               │
│  └─────────────────────────────────────────┘               │
│         │                           │                       │
└─────────┼───────────────────────────┼───────────────────────┘
          │                           │
          ▼                           ▼
   ┌─────────────┐           ┌──────────────┐
   │  Parsers    │           │  Publishers  │
   ├─────────────┤           ├──────────────┤
   │ - Article   │           │ - Telegram   │
   │ - SERP      │           │ - VC.ru      │
   └─────────────┘           │ - RBC        │
          │                  └──────────────┘
          ▼
   ┌─────────────┐
   │  AI Modules │
   ├─────────────┤
   │ - Analyzer  │
   │ - Writer    │
   │ - SEO Check │
   │ - Reviewer  │
   │ - Image Gen │
   └─────────────┘
          │
          ▼
   ┌─────────────┐
   │  Database   │
   │  (SQLite)   │
   └─────────────┘
```

## Troubleshooting

### Redis не запускается
```bash
# Проверить, запущен ли Redis
redis-cli ping
# Должно вернуть PONG

# Или через Docker
docker ps | grep redis
```

### Celery не видит задачи
```bash
# Проверить автообнаружение
celery -A tasks.celery_app inspect registered

# Должны быть видны:
# - tasks.parse_task.parse_and_generate
# - tasks.publish_task.publish_post
```

### Задачи не выполняются
```bash
# Проверить статус воркера
celery -A tasks.celery_app inspect active

# Проверить очередь
celery -A tasks.celery_app inspect reserved
```

### Ошибки в логах
Логи сохраняются в `logs/worker_*.log`

```bash
tail -f logs/worker_*.log
```

## TODO

### Парсер модули (требуют реализации)
- [ ] `SerpParser.search_all()` - интеграция с Google Custom Search API или SerpAPI
- [ ] `ArticleParser` - улучшение определения контента (Readability, Newspaper3k)

### AI модули (требуют реализации)
- [ ] `ContentAnalyzer.analyze()` - интеграция с OpenAI/Anthropic
- [ ] `SEOWriter.write()` - генерация контента через LLM
- [ ] `SelfReviewer.review()` - улучшение контента через LLM
- [ ] `NanaBananaGenerator.generate()` - генерация изображений (DALL-E, Midjourney, SD)

### Publisher модули
- [x] `TelegramPublisher` - реализовано
- [ ] `VCPublisher` - требует реализации API интеграции
- [x] `RBCPublisher` - реализовано через Playwright

### Дополнительные функции
- [ ] Уведомление админа в Telegram бота
- [ ] Веб-интерфейс для управления
- [ ] Periodic tasks через Celery Beat
- [ ] Retry policies для разных типов ошибок
- [ ] Rate limiting для внешних API
- [ ] Кэширование результатов парсинга

## Лицензия

MIT
