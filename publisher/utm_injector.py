"""UTM parameter injection for links in text."""

import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


class UTMInjector:
    """Injects UTM parameters into links and embeds them in text with anchor tags."""
    
    def inject(self, text: str, links: list[str], utm_template: str) -> str:
        """
        Add UTM parameters to links and embed them organically in text.
        
        Args:
            text: Original text content
            links: List of URLs to inject
            utm_template: UTM query string (e.g., "?utm_source=vc&utm_medium=article&utm_campaign=smm")
        
        Returns:
            Text with embedded Markdown links containing UTM parameters
        """
        if not links:
            return text
        
        result_text = text
        
        for link in links:
            # Add UTM parameters to the link
            enhanced_link = self._add_utm_params(link, utm_template)
            
            # Extract domain or generate anchor text
            anchor_text = self._generate_anchor_text(link)
            
            # Find a good place to insert the link
            # Strategy: Look for sentences that might relate to the link's domain or topic
            markdown_link = f"[{anchor_text}]({enhanced_link})"
            
            # If the link domain is mentioned in text, replace it with markdown link
            domain = urlparse(link).netloc.replace("www.", "")
            if domain in result_text and f"[{anchor_text}]" not in result_text:
                result_text = result_text.replace(domain, markdown_link, 1)
            else:
                # Otherwise, append at the end with context
                result_text += f"\n\n🔗 {markdown_link}"
        
        return result_text
    
    def _add_utm_params(self, url: str, utm_template: str) -> str:
        """Add UTM parameters to a URL, preserving existing query params."""
        # Parse URL
        parsed = urlparse(url)
        
        # Parse existing query parameters
        query_params = parse_qs(parsed.query)
        
        # Parse UTM template (remove leading ? if present)
        utm_template_clean = utm_template.lstrip("?")
        utm_params = parse_qs(utm_template_clean)
        
        # Merge parameters (UTM params override existing)
        for key, value in utm_params.items():
            query_params[key] = value
        
        # Flatten query params (parse_qs returns lists)
        flat_params = {k: v[0] if isinstance(v, list) and v else v for k, v in query_params.items()}
        
        # Build new query string
        new_query = urlencode(flat_params, doseq=False)
        
        # Reconstruct URL
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)
    
    def _generate_anchor_text(self, url: str) -> str:
        """Generate human-readable anchor text from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        
        # Try to extract meaningful text from path
        path_parts = [p for p in parsed.path.split("/") if p and not p.endswith((".html", ".php"))]
        
        if path_parts:
            # Use last meaningful path segment
            anchor = path_parts[-1].replace("-", " ").replace("_", " ").title()
            return anchor
        
        return domain
