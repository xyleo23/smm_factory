# SMM Factory - Publisher Module

Модуль публикации контента в различные каналы: Telegram, VC.ru, RBC Companies.

## Установка

```bash
pip install -r requirements.txt

# Для RBC Publisher требуется установка браузеров Playwright
playwright install chromium
```

## Конфигурация

Скопируйте `.env.example` в `.env` и заполните необходимые переменные:

```bash
cp .env.example .env
```

### Обязательные параметры

- `TELEGRAM_BOT_TOKEN` - токен бота от @BotFather
- `TELEGRAM_CHANNEL_ID` - ID канала (например, @mychannel или -100123456789)

### Опциональные параметры

- `VC_SESSION_TOKEN` - токен сессии VC.ru (если нужна публикация на VC.ru)
- `RBC_LOGIN` / `RBC_PASSWORD` - учетные данные для RBC Companies

## Использование

### UTMInjector - Добавление UTM-меток

```python
from publisher import UTMInjector

injector = UTMInjector()

text = "Интересная статья о маркетинге на example.com"
links = ["https://example.com/article"]
utm = "?utm_source=vc&utm_medium=article&utm_campaign=smm"

enhanced_text = injector.inject(text, links, utm)
# Результат: текст с встроенными ссылками [анкор](https://example.com/article?utm_source=vc&...)
```

### TelegramPublisher - Публикация в Telegram

```python
from aiogram import Bot
from publisher import TelegramPublisher
from core import config

bot = Bot(token=config.telegram_bot_token)
publisher = TelegramPublisher()

# Публикация текста
success = await publisher.publish(
    bot=bot,
    channel_id=config.telegram_channel_id,
    text="# Заголовок\n\nТекст статьи в Markdown",
    image_url=None
)

# Публикация с изображением
success = await publisher.publish(
    bot=bot,
    channel_id=config.telegram_channel_id,
    text="Описание к фото",
    image_url="https://example.com/image.jpg"
)
```

**Особенности:**
- Автоматическое разбиение длинных сообщений (>4096 символов)
- Поддержка Markdown разметки
- Для изображений с длинным текстом: сначала фото, затем текст частями

### VCPublisher - Публикация на VC.ru

```python
from publisher import VCPublisher

publisher = VCPublisher()

success = publisher.publish(
    title="Заголовок статьи",
    text="Содержимое статьи",
    image_url="https://example.com/cover.jpg"
)
```

**Статус:** Заглушка. Требуется реализация API интеграции.

**TODO:**
- Реализовать POST запрос к `https://api.vc.ru/v2.8/articles/add`
- Обработка ответов и ошибок
- Retry логика для rate limiting

### RBCPublisher - Публикация на RBC Companies

```python
from publisher import RBCPublisher

publisher = RBCPublisher()

success = await publisher.publish(
    title="Заголовок материала",
    text="Текст материала",
    image_path="/path/to/image.jpg"  # опционально
)
```

**Особенности:**
- Использует Playwright для автоматизации браузера
- Автоматический логин
- Заполнение формы создания материала
- Загрузка изображений
- Отправка на модерацию
- Скриншоты ошибок сохраняются в `logs/rbc_errors/`

## Архитектура

```
smm_factory/
├── core/
│   ├── __init__.py
│   └── config.py          # Конфигурация через Pydantic
├── publisher/
│   ├── __init__.py
│   ├── utm_injector.py    # Добавление UTM-меток
│   ├── tg_publisher.py    # Telegram публикация
│   ├── vc_publisher.py    # VC.ru публикация (TODO)
│   └── rbc_publisher.py   # RBC браузерная автоматизация
├── logs/
│   └── rbc_errors/        # Скриншоты ошибок RBC
├── .env.example
├── requirements.txt
└── README.md
```

## Логирование

Все модули используют `loguru` для логирования:

```python
from loguru import logger

# Логи автоматически включают контекст и уровень
logger.info("Успешная публикация")
logger.warning("Токен не задан")
logger.error("Ошибка при публикации")
```

## Обработка ошибок

Все publisher'ы возвращают `bool`:
- `True` - успешная публикация
- `False` - ошибка (детали в логах)

RBCPublisher при ошибках сохраняет скриншоты для отладки в `logs/rbc_errors/`.

## Зависимости

- **pydantic** - валидация конфигурации
- **loguru** - структурированное логирование
- **aiogram** - Telegram Bot API
- **playwright** - браузерная автоматизация
- **aiohttp** - HTTP клиент для API запросов

## Разработка

### Добавление нового публикатора

1. Создайте класс в `publisher/your_publisher.py`
2. Реализуйте метод `publish()` возвращающий `bool`
3. Добавьте в `publisher/__init__.py`
4. Добавьте конфигурацию в `core/config.py`
5. Обновите `.env.example`

### Тестирование RBC Publisher

Playwright позволяет запускать в видимом режиме для отладки:

```python
browser = await p.chromium.launch(headless=False, slow_mo=100)
```

## Лицензия

MIT
