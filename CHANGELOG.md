# Changelog

## [1.0.0] - 2026-03-01

### Initial Release - UTM Injector & Publishers

#### ✨ Added

**Core Modules:**
- `publisher/utm_injector.py` - UTM parameter injection with intelligent link placement
- `publisher/tg_publisher.py` - Telegram channel publisher with message splitting
- `publisher/vc_publisher.py` - VC.ru publisher stub with detailed API specification
- `publisher/rbc_publisher.py` - RBC Companies browser automation publisher
- `core/config.py` - Pydantic-based configuration management

**Features:**
- Smart UTM parameter injection preserving existing query params
- Telegram message auto-splitting for long content (>4096 chars)
- Intelligent paragraph-based text splitting
- RBC login automation with error screenshots
- Multiple selector fallbacks for robust form filling
- Comprehensive error handling on all publishers
- Async/await support throughout

**Documentation:**
- `README.md` - Complete project documentation
- `QUICKSTART.md` - Quick start guide with 4 practical examples
- `ARCHITECTURE.md` - System architecture visualization
- `IMPLEMENTATION_SUMMARY.md` - Detailed implementation notes

**Development Tools:**
- `test_publishers.py` - Unit test suite with 13+ test cases
- `example_usage.py` - Complete usage examples
- `setup.py` - Automated dependency installation
- `.env.example` - Environment configuration template
- `.gitignore` - Git ignore rules
- `requirements.txt` - Python dependencies

#### 🔧 Configuration

**Environment Variables:**
- `TELEGRAM_BOT_TOKEN` - Bot token from @BotFather
- `TELEGRAM_CHANNEL_ID` - Target channel ID
- `VC_SESSION_TOKEN` - VC.ru session token (optional)
- `RBC_LOGIN` - RBC Companies login (optional)
- `RBC_PASSWORD` - RBC Companies password (optional)
- `LOGS_DIR` - Log directory path (default: logs/)

#### 📦 Dependencies

- pydantic >= 2.0.0 - Configuration validation
- pydantic-settings >= 2.0.0 - Settings management
- loguru >= 0.7.0 - Structured logging
- aiogram >= 3.0.0 - Telegram Bot API
- playwright >= 1.40.0 - Browser automation
- aiohttp >= 3.9.0 - HTTP client
- pytest >= 7.4.0 - Testing framework
- pytest-asyncio >= 0.21.0 - Async test support

#### 🎯 Implementation Details

**UTMInjector:**
- URL parsing and reconstruction
- Query parameter merging
- Anchor text generation from URL paths
- Domain-based link placement in text
- Markdown link formatting

**TelegramPublisher:**
- Photo with caption support
- Text-only messaging
- 4096 character limit handling
- 1024 character caption limit
- Paragraph-aware text splitting
- Fallback to character-based splitting
- Full Markdown support

**VCPublisher:**
- Token validation
- Detailed API specification in comments
- Implementation roadmap
- Error handling patterns
- Retry logic documentation

**RBCPublisher:**
- Playwright async automation
- Multi-step login flow
- Form filling with multiple selector strategies
- Rich text editor support (Quill, TinyMCE, contenteditable)
- Image upload handling
- Error screenshot capture (timestamped)
- Graceful browser cleanup
- 30-second timeouts with retry

#### 🧪 Testing

**Test Coverage:**
- UTMInjector: 8 test cases
- TelegramPublisher: 3 test cases
- VCPublisher: 1 test case
- RBCPublisher: 1 test case

**Test Categories:**
- Unit tests for core logic
- Integration test examples
- Async test support
- Stub validation

#### 📝 Code Quality

- Type hints throughout (Python 3.10+ syntax)
- Comprehensive docstrings
- Error handling on all external calls
- Structured logging with context
- Clean separation of concerns
- Single Responsibility Principle
- Async/await best practices
- Pydantic validation

#### 🔒 Security

- No hardcoded credentials
- Environment variable-based config
- .env excluded from git
- Optional credential parameters
- No sensitive data in logs

#### 📊 Logging

- Console output with colors (loguru)
- File-based logging
- Error screenshots for RBC (PNG)
- Timestamp-based log rotation
- Structured log messages with context

#### 🚀 Setup

- Automated setup script
- Dependency installation
- Playwright browser setup
- Environment template
- Configuration validation

#### 💡 Examples

- Basic Telegram publishing
- Image with caption
- UTM injection workflow
- Multi-channel publishing
- Error handling patterns

#### 📖 Documentation Highlights

- Installation guide (3-minute setup)
- Configuration instructions
- Usage examples (4 different scenarios)
- API specifications
- Error debugging guide
- Production checklist
- FAQ section
- Architecture diagrams

### Known Limitations

- VC.ru publisher is a stub (requires API implementation)
- RBC selectors may need adjustment per site updates
- Telegram Markdown v1 (not v2)
- RBC runs in headless mode (configurable)

### Next Steps

1. Implement VC.ru API integration
2. Add more publisher platforms (VK, Дзен, OK)
3. Add scheduling capabilities
4. Add analytics tracking
5. Add content queue management
6. Add webhook support for notifications

---

## Release Notes

**Version:** 1.0.0  
**Date:** 2026-03-01  
**Status:** Production Ready (Telegram, RBC) / Stub (VC.ru)  
**Python:** 3.10+  
**License:** MIT

### What's Working

✅ UTM Injector - Fully functional  
✅ Telegram Publisher - Production ready  
✅ RBC Publisher - Fully automated (may need selector tuning)  
⚠️ VC.ru Publisher - Stub with implementation spec

### Installation

```bash
cd C:\Users\Admin\smm_factory
python setup.py
```

### Quick Test

```bash
# Run tests
pytest test_publishers.py -v

# Try example
python example_usage.py
```

### Support

For issues or questions:
1. Check QUICKSTART.md
2. Review logs/ directory
3. Check rbc_errors/ for screenshots
4. Run tests to verify setup

---

**Built with ❤️ using Python 3.10+, Playwright, and aiogram**
