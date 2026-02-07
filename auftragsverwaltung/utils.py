"""
Utility functions for auftragsverwaltung app.
"""

import bleach


def sanitize_html(html_content):
    """
    Sanitize HTML content using allowlist approach for Textbausteine.
    
    Allowed tags: p, br, strong, em, u, ul, ol, li, a
    Allowed attributes: a[href, target, rel]
    
    Args:
        html_content (str): Raw HTML content to sanitize
        
    Returns:
        str: Sanitized HTML content
    """
    # Define allowed HTML tags (MVP allowlist)
    allowed_tags = [
        'p', 'br', 'strong', 'em', 'u',
        'ul', 'ol', 'li', 'a'
    ]
    
    # Define allowed attributes for specific tags
    allowed_attributes = {
        'a': ['href', 'target', 'rel']
    }
    
    # Sanitize the HTML content
    sanitized = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        strip=True  # Remove disallowed tags instead of escaping
    )
    
    return sanitized
