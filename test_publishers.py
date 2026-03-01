"""Unit tests for publisher modules."""

import pytest
from publisher import UTMInjector


class TestUTMInjector:
    """Test UTM parameter injection functionality."""
    
    def test_inject_with_empty_links(self):
        """Test that empty links list returns original text."""
        injector = UTMInjector()
        text = "Sample text"
        result = injector.inject(text, [], "?utm_source=test")
        assert result == text
    
    def test_inject_adds_utm_params(self):
        """Test that UTM parameters are added to links."""
        injector = UTMInjector()
        text = "Visit example.com for more info"
        links = ["https://example.com/page"]
        utm = "?utm_source=vc&utm_medium=article"
        
        result = injector.inject(text, links, utm)
        assert "utm_source=vc" in result
        assert "utm_medium=article" in result
        assert "example.com" in result
    
    def test_inject_preserves_existing_params(self):
        """Test that existing URL parameters are preserved."""
        injector = UTMInjector()
        text = "Sample text"
        links = ["https://example.com/page?foo=bar"]
        utm = "?utm_source=test"
        
        result = injector.inject(text, links, utm)
        assert "foo=bar" in result
        assert "utm_source=test" in result
    
    def test_inject_multiple_links(self):
        """Test injection of multiple links."""
        injector = UTMInjector()
        text = "Visit example.com and test.com"
        links = ["https://example.com", "https://test.com"]
        utm = "?utm_source=test"
        
        result = injector.inject(text, links, utm)
        assert result.count("utm_source=test") == 2
    
    def test_generate_anchor_text_from_path(self):
        """Test anchor text generation from URL path."""
        injector = UTMInjector()
        url = "https://example.com/marketing-guide"
        anchor = injector._generate_anchor_text(url)
        assert anchor == "Marketing Guide"
    
    def test_generate_anchor_text_from_domain(self):
        """Test anchor text generation falls back to domain."""
        injector = UTMInjector()
        url = "https://example.com"
        anchor = injector._generate_anchor_text(url)
        assert anchor == "example.com"
    
    def test_add_utm_params_with_question_mark(self):
        """Test UTM template with leading question mark."""
        injector = UTMInjector()
        url = "https://example.com/page"
        utm = "?utm_source=test&utm_medium=article"
        
        result = injector._add_utm_params(url, utm)
        assert result == "https://example.com/page?utm_source=test&utm_medium=article"
    
    def test_add_utm_params_without_question_mark(self):
        """Test UTM template without leading question mark."""
        injector = UTMInjector()
        url = "https://example.com/page"
        utm = "utm_source=test&utm_medium=article"
        
        result = injector._add_utm_params(url, utm)
        assert result == "https://example.com/page?utm_source=test&utm_medium=article"


class TestTelegramPublisher:
    """Test Telegram publisher functionality."""
    
    def test_split_text_short(self):
        """Test that short text is not split."""
        from publisher import TelegramPublisher
        
        publisher = TelegramPublisher()
        text = "Short text"
        chunks = publisher._split_text(text)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_split_text_long(self):
        """Test that long text is split into chunks."""
        from publisher import TelegramPublisher
        
        publisher = TelegramPublisher()
        # Create text longer than MAX_MESSAGE_LENGTH
        text = "A" * 5000
        chunks = publisher._split_text(text)
        
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= publisher.MAX_MESSAGE_LENGTH
    
    def test_split_text_preserves_paragraphs(self):
        """Test that text splitting tries to preserve paragraph boundaries."""
        from publisher import TelegramPublisher
        
        publisher = TelegramPublisher()
        text = "Paragraph 1\n\nParagraph 2\n\nParagraph 3"
        chunks = publisher._split_text(text)
        
        assert len(chunks) == 1  # Short text shouldn't be split
        assert chunks[0] == text


class TestVCPublisher:
    """Test VC.ru publisher functionality."""
    
    def test_publish_without_token(self):
        """Test that publishing without token returns False."""
        from publisher import VCPublisher
        
        publisher = VCPublisher()
        result = publisher.publish("Title", "Text")
        
        assert result is False


class TestRBCPublisher:
    """Test RBC publisher functionality."""
    
    @pytest.mark.asyncio
    async def test_publish_without_credentials(self):
        """Test that publishing without credentials returns False."""
        from publisher import RBCPublisher
        
        publisher = RBCPublisher()
        result = await publisher.publish("Title", "Text")
        
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
