# SMM Factory - Celery Tasks Quick Start

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
cd C:\Users\Admin\smm_factory
pip install -r requirements.txt
playwright install chromium
```

### 2. Настройка окружения

```bash
# Скопировать .env.example в .env
cp .env.example .env

# Отредактировать .env и указать свои credentials
notepad .env
```

Обязательные настройки:
```env
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///./smm_factory.db
TELEGRAM_BOT_TOKEN=your_token_here
```

### 3. Запуск Redis

**Вариант A: Локально**
```bash
redis-server
```

**Вариант B: Docker**
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

**Вариант C: Docker Compose (все сервисы)**
```bash
docker-compose up -d
```

### 4. Инициализация базы данных

```bash
python start_worker.py
```

Это создаст:
- Таблицы в БД
- Примеры источников
- Настройки по умолчанию

### 5. Тестирование

```bash
python test_celery_tasks.py
```

Проверит:
- ✓ Импорты модулей
- ✓ Конфигурацию
- ✓ Подключение к БД
- ✓ Настройки Celery

### 6. Запуск Celery Worker

```bash
# Воркер (обрабатывает задачи)
celery -A tasks.celery_app worker --loglevel=info

# Воркер + Beat (с периодическими задачами)
celery -A tasks.celery_app worker --beat --loglevel=info
```

### 7. Мониторинг (опционально)

```bash
# Flower - веб-интерфейс
pip install flower
celery -A tasks.celery_app flower

# Открыть http://localhost:5555
```

## 📋 Использование задач

### Парсинг и генерация контента

**Python:**
```python
from tasks import parse_and_generate

# Запустить задачу асинхронно
result = parse_and_generate.delay()
print(f"Task ID: {result.id}")

# Получить результат (блокирующий вызов)
print(result.get(timeout=300))
```

**CLI:**
```bash
python -c "from tasks import parse_and_generate; parse_and_generate.delay()"
```

### Публикация поста

**Python:**
```python
from tasks import publish_post

# Опубликовать пост с ID=1
result = publish_post.delay(1)
print(result.get())
```

**CLI:**
```bash
python -c "from tasks import publish_post; publish_post.delay(1)"
```

## 🏗️ Структура проекта

```
smm_factory/
├── tasks/                      # Celery задачи
│   ├── celery_app.py          # Конфигурация Celery
│   ├── parse_task.py          # Задача парсинга и генерации
│   ├── publish_task.py        # Задача публикации
│   └── README.md              # Документация задач
│
├── models/                     # Модели базы данных
│   ├── __init__.py            # Source, Article, Post, UserSettings
│   └── database.py            # Подключение к БД
│
├── parser/                     # Модули парсинга
│   ├── article_parser.py      # Парсинг статей
│   └── serp_parser.py         # Парсинг поисковой выдачи
│
├── ai/                         # AI модули
│   └── __init__.py            # Analyzer, Writer, SEO, Reviewer, ImageGen
│
├── publisher/                  # Модули публикации
│   ├── tg_publisher.py        # Telegram
│   ├── vc_publisher.py        # VC.ru
│   ├── rbc_publisher.py       # RBC Companies
│   └── utm_injector.py        # UTM метки
│
├── core/                       # Конфигурация
│   └── config.py              # Настройки из .env
│
├── logs/                       # Логи (создается автоматически)
│
├── .env                        # Настройки окружения
├── requirements.txt            # Зависимости Python
├── docker-compose.yml          # Docker Compose конфигурация
├── Dockerfile                  # Docker образ
└── start_worker.py             # Скрипт инициализации
```

## 🔄 Workflow задач

### 1. parse_and_generate

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Получить Source из БД (is_active=True)                   │
├─────────────────────────────────────────────────────────────┤
│ 2. Получить UserSettings из БД                              │
├─────────────────────────────────────────────────────────────┤
│ 3. Собрать URL:                                              │
│    - fetch_links_from_page(source.url) для каждого Source  │
│    - SerpParser.search_all(keyword) для каждого ключа      │
├─────────────────────────────────────────────────────────────┤
│ 4. Фильтровать дубли и существующие Article                │
├─────────────────────────────────────────────────────────────┤
│ 5. Для каждого URL:                                          │
│    ┌────────────────────────────────────────────────────┐  │
│    │ a) ArticleParser.fetch_html(url)                   │  │
│    │ b) ArticleParser.parse_article(html)               │  │
│    │ c) Сохранить Article в БД                          │  │
│    │ d) ContentAnalyzer.analyze(title, content)         │  │
│    │ e) SEOWriter.write(analysis, tone, keywords, llm)  │  │
│    │ f) SEOChecker.check(text, keywords)                │  │
│    │ g) SelfReviewer.review(text, issues) если нужно    │  │
│    │ h) UTMInjector.inject(text, links, utm)            │  │
│    │ i) NanaBananaGenerator.generate(title)             │  │
│    │ j) Сохранить Post в БД (status="pending")          │  │
│    │ k) Обновить Article.is_processed=True              │  │
│    │ l) Если is_auto_publish:                           │  │
│    │       publish_post.delay(post.id)                  │  │
│    │    Иначе:                                           │  │
│    │       notify_admin(post.id)                        │  │
│    └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2. publish_post

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Получить Post по post_id                                 │
├─────────────────────────────────────────────────────────────┤
│ 2. Получить UserSettings                                     │
├─────────────────────────────────────────────────────────────┤
│ 3. Для каждого канала в tg_channels:                        │
│    TelegramPublisher.publish(bot, channel_id, text, image)  │
├─────────────────────────────────────────────────────────────┤
│ 4. Если VC_SESSION_TOKEN:                                    │
│    VCPublisher.publish(title, text, image_url)              │
├─────────────────────────────────────────────────────────────┤
│ 5. Если RBC_LOGIN:                                           │
│    RBCPublisher.publish(title, text, image_path)            │
├─────────────────────────────────────────────────────────────┤
│ 6. Обновить Post.status = "published"                       │
└─────────────────────────────────────────────────────────────┘
```

## ⚙️ Конфигурация

### Celery настройки (tasks/celery_app.py)

```python
task_serializer="json"              # Сериализация JSON
timezone="Europe/Moscow"            # Таймзона МСК
task_acks_late=True                 # Задача не удаляется пока не выполнена
task_reject_on_worker_lost=True     # Вернуть в очередь если воркер упал
worker_prefetch_multiplier=1        # Брать по 1 задаче за раз
```

### Retry политики

**parse_and_generate:**
- max_retries=3
- countdown=300s × 2^retry_count
- Итого: 300s → 600s → 1200s

**publish_post:**
- max_retries=3
- countdown=60s × 2^retry_count
- Итого: 60s → 120s → 240s

## 🗄️ База данных

### Модели

**Source** - источники контента
- `url` - URL источника
- `name` - название
- `is_active` - активен ли
- `last_parsed_at` - время последнего парсинга

**UserSettings** - настройки пользователя
- `serp_keywords` - ключевые слова для поиска
- `internal_links` - внутренние ссылки
- `utm_template` - шаблон UTM меток
- `tone` - тон текста
- `keywords` - SEO ключевые слова
- `selected_llm` - выбранная LLM
- `tg_channels` - список Telegram каналов
- `is_auto_publish` - автопубликация

**Article** - распарсенные статьи
- `url` - URL статьи
- `title` - заголовок
- `content` - содержание
- `is_processed` - обработана ли

**Post** - сгенерированные посты
- `title` - заголовок
- `text` - текст поста
- `image_url` - URL изображения
- `status` - статус (pending, published, failed)

**ParsingHistory** - история парсинга
- `url` - URL
- `status` - статус
- `error_message` - ошибка

## 🐛 Troubleshooting

### Redis не подключается

```bash
# Проверить, запущен ли Redis
redis-cli ping
# Ответ: PONG

# Проверить порт
netstat -an | findstr 6379
```

### Celery не видит задачи

```bash
# Проверить зарегистрированные задачи
celery -A tasks.celery_app inspect registered
```

Должны быть видны:
- `tasks.parse_task.parse_and_generate`
- `tasks.publish_task.publish_post`

### Задачи не выполняются

```bash
# Проверить активные задачи
celery -A tasks.celery_app inspect active

# Проверить очередь
celery -A tasks.celery_app inspect reserved

# Проверить воркеры
celery -A tasks.celery_app inspect stats
```

### Ошибки импортов

```bash
# Убедиться что вы в правильной директории
cd C:\Users\Admin\smm_factory

# Установить зависимости
pip install -r requirements.txt

# Запустить тесты
python test_celery_tasks.py
```

## 📊 Мониторинг

### Flower (Web UI)

```bash
celery -A tasks.celery_app flower
```

Откройте http://localhost:5555 для:
- Просмотра активных задач
- Статистики выполнения
- Графиков производительности
- Управления воркерами

### Логи

Логи сохраняются в `logs/`:
```bash
# Последние логи
tail -f logs/worker_*.log

# Логи с ошибками
grep ERROR logs/worker_*.log
```

## 🔗 Полезные команды

```bash
# Запустить воркер
celery -A tasks.celery_app worker --loglevel=info

# Запустить beat (планировщик)
celery -A tasks.celery_app beat --loglevel=info

# Запустить flower (мониторинг)
celery -A tasks.celery_app flower

# Очистить все задачи
celery -A tasks.celery_app purge

# Статистика
celery -A tasks.celery_app inspect stats

# Список воркеров
celery -A tasks.celery_app inspect active_queues
```

## 📝 TODO

- [ ] Реализовать `SerpParser.search_all()` (Google API, SerpAPI)
- [ ] Реализовать AI модули (OpenAI, Anthropic, local LLM)
- [ ] Реализовать `VCPublisher` API интеграцию
- [ ] Добавить уведомления админу в Telegram бота
- [ ] Настроить периодические задачи (Celery Beat)
- [ ] Добавить веб-интерфейс для управления

## 📖 Дополнительная документация

- Полная документация: `tasks/README.md`
- Примеры использования: `example_usage.py`
- Тесты: `test_celery_tasks.py`
