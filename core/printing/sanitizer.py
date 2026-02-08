"""
HTML Sanitizer for Printing Framework

Provides a second layer of protection for HTML content before rendering to PDF.
Note: Quill-HTML is already sanitized when saved, this is an optional additional layer.
"""

import bleach


def sanitize_html(html_content: str) -> str:
    """
    Sanitize HTML content using allowlist approach.
    
    Reuses the same allowlist as the Quill editor fields for consistency.
    
    Allowed tags: p, br, strong, em, u, ul, ol, li, a
    Allowed attributes: a[href, target, rel]
    
    Args:
        html_content: Raw HTML content to sanitize
        
    Returns:
        Sanitized HTML content
    """
    # Define allowed HTML tags (consistent with Quill editor)
    allowed_tags = [
        'p', 'br', 'strong', 'em', 'u',
        'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 
        'table', 'thead', 'tbody', 'tr', 'th', 'td',
        'div', 'span'
    ]
    
    # Define allowed attributes for specific tags
    allowed_attributes = {
        'a': ['href', 'target', 'rel'],
        'div': ['class'],
        'span': ['class'],
        'table': ['class'],
        'td': ['colspan', 'rowspan'],
        'th': ['colspan', 'rowspan'],
    }
    
    # Sanitize the HTML content
    sanitized = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True  # Remove disallowed tags instead of escaping
    )
    
    return sanitized
