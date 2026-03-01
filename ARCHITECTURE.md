# SMM Factory - Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SMM Factory System                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          Configuration Layer                        │
├─────────────────────────────────────────────────────────────────────┤
│  core/config.py                                                     │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ Settings (Pydantic BaseSettings)                            │  │
│  │ • telegram_bot_token    • telegram_channel_id              │  │
│  │ • vc_session_token      • rbc_login / rbc_password         │  │
│  │ • logs_dir                                                  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                              ↓ .env                                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          Publisher Layer                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────┐   ┌────────────────────┐                  │
│  │  UTMInjector       │   │  TelegramPublisher │                  │
│  ├────────────────────┤   ├────────────────────┤                  │
│  │ inject()           │   │ publish()          │                  │
│  │ • _add_utm_params  │   │ • _publish_photo   │                  │
│  │ • _generate_anchor │   │ • _publish_text    │                  │
│  └────────────────────┘   │ • _split_text      │                  │
│           │                └────────────────────┘                  │
│           │                         │                              │
│           │                    aiogram Bot                         │
│           │                         ↓                              │
│           │                  Telegram API                          │
│           │                                                        │
│  ┌────────▼───────────┐   ┌────────────────────┐                  │
│  │  VCPublisher       │   │  RBCPublisher      │                  │
│  ├────────────────────┤   ├────────────────────┤                  │
│  │ publish()          │   │ publish()          │                  │
│  │ • Check token      │   │ • Login flow       │                  │
│  │ • TODO: API call   │   │ • Create material  │                  │
│  └────────────────────┘   │ • Upload image     │                  │
│           │                │ • Submit           │                  │
│           │                │ • Screenshot err   │                  │
│      (Stub with TODO)     └────────────────────┘                  │
│                                     │                              │
│                                 Playwright                         │
│                                     ↓                              │
│                            RBC Companies Site                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          Logging Layer                              │
├─────────────────────────────────────────────────────────────────────┤
│  loguru                                                             │
│  ┌──────────────────┐  ┌──────────────────┐                       │
│  │ Console output   │  │ File logs        │                       │
│  │ • INFO           │  │ • logs/*.log     │                       │
│  │ • WARNING        │  │ • rbc_errors/    │                       │
│  │ • ERROR          │  │   └─ *.png       │                       │
│  └──────────────────┘  └──────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════
                          Data Flow Example
═══════════════════════════════════════════════════════════════════════

1. Content Creation
   ┌──────────────────────────────────────────────────────────────┐
   │ title = "Article Title"                                      │
   │ text = "Content with links..."                               │
   │ links = ["https://example.com/page"]                         │
   │ utm = "?utm_source=telegram&utm_medium=post"                 │
   └──────────────────────────────────────────────────────────────┘
                               ↓

2. UTM Injection
   ┌──────────────────────────────────────────────────────────────┐
   │ injector = UTMInjector()                                     │
   │ enhanced_text = injector.inject(text, links, utm)            │
   │ → "Content with [Page](https://example.com/page?utm...)"     │
   └──────────────────────────────────────────────────────────────┘
                               ↓

3. Publishing
   ┌──────────────────────────────────────────────────────────────┐
   │ Telegram:  publisher.publish(bot, channel, enhanced_text)    │
   │ VC.ru:     publisher.publish(title, enhanced_text)           │
   │ RBC:       publisher.publish(title, enhanced_text, image)    │
   └──────────────────────────────────────────────────────────────┘
                               ↓

4. Results
   ┌──────────────────────────────────────────────────────────────┐
   │ • True/False status returned                                 │
   │ • Logs written to console & files                            │
   │ • Screenshots saved on RBC errors                            │
   │ • UTM tracking enabled for analytics                         │
   └──────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════
                         Module Dependencies
═══════════════════════════════════════════════════════════════════════

External Libraries:
┌────────────────────────────────────────────────────────────────────┐
│ pydantic-settings  →  Configuration validation                    │
│ loguru             →  Structured logging                          │
│ aiogram            →  Telegram Bot API (async)                    │
│ playwright         →  Browser automation (RBC)                    │
│ aiohttp            →  HTTP client (future VC.ru)                  │
│ pytest             →  Testing framework                           │
└────────────────────────────────────────────────────────────────────┘

Standard Library:
┌────────────────────────────────────────────────────────────────────┐
│ urllib.parse       →  URL parsing & manipulation                  │
│ pathlib            →  Path operations                             │
│ datetime           →  Timestamps                                  │
│ typing             →  Type hints                                  │
│ asyncio            →  Async runtime                               │
└────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════
                         Error Handling Flow
═══════════════════════════════════════════════════════════════════════

                            try:
                              │
                ┌─────────────┴──────────────┐
                ↓                            ↓
          Success Path                 Exception Path
                │                            │
        ┌───────▼──────────┐         ┌──────▼──────────┐
        │ Log: INFO        │         │ Log: ERROR      │
        │ Return: True     │         │ Screenshot (RBC)│
        └──────────────────┘         │ Return: False   │
                                     └─────────────────┘

═══════════════════════════════════════════════════════════════════════
                      Testing & Quality Assurance
═══════════════════════════════════════════════════════════════════════

test_publishers.py
├── TestUTMInjector (8 tests)
│   ├── Empty links handling
│   ├── UTM addition
│   ├── Param preservation
│   ├── Multiple links
│   ├── Anchor text generation
│   └── URL parameter handling
│
├── TestTelegramPublisher (3 tests)
│   ├── Text splitting
│   ├── Long text handling
│   └── Paragraph preservation
│
├── TestVCPublisher (1 test)
│   └── Token validation
│
└── TestRBCPublisher (1 test)
    └── Credentials validation

═══════════════════════════════════════════════════════════════════════
                          File Size Summary
═══════════════════════════════════════════════════════════════════════

Core Implementation:
  utm_injector.py     →  3.5 KB  (UTM injection logic)
  tg_publisher.py     →  4.9 KB  (Telegram publishing)
  vc_publisher.py     →  2.4 KB  (VC.ru stub + TODO)
  rbc_publisher.py    →  9.2 KB  (RBC automation)
  config.py           →  1.4 KB  (Configuration)

Documentation:
  README.md           →  6.3 KB  (Full documentation)
  QUICKSTART.md       → 10.5 KB  (Quick start guide)
  IMPLEMENTATION.md   → 14.3 KB  (This summary)

Supporting Files:
  test_publishers.py  →  5.4 KB  (Unit tests)
  example_usage.py    →  3.0 KB  (Usage examples)
  setup.py            →  2.5 KB  (Setup automation)
  requirements.txt    →  0.3 KB  (Dependencies)
  .env.example        →  0.6 KB  (Config template)

═══════════════════════════════════════════════════════════════════════
