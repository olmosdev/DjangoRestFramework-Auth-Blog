import bleach
import re

ALLOWED_TAGS = [
    "p", "h1", "h2", "ul", "ol", "li", "sub", "sup", "blockquote",
    "pre", "a", "span", "strong", "em", "u", "s", "br"
]
ALLOWED_ATTRIBUTES = {"a": ["href", "title"]}
ALLOWED_SCHEMES = ['http', 'https']

def sanitize_string(string: str) -> str:
    if string is None:
        return ""

    # Sanitize using bleach to remove any unwanted tags
    cleaned_string = bleach.clean(string, tags=[], strip=True)

    # Allow only letters, numbers, spaces, apostrophes, quotation marks, commas, and periods
    pattern = re.compile(r"[^a-zA-Z0-9\s',:.?-ÁÉÍÓÚáéíóúÑñüÜ]")

    # Remove unwanted characters
    sanitized_string = pattern.sub("", cleaned_string)

    return sanitized_string

def sanitize_html(content):
    if content is None:
        return ""
    
    return bleach.clean(
        content, 
        tags=ALLOWED_TAGS, 
        attributes=ALLOWED_ATTRIBUTES, 
        protocols=ALLOWED_SCHEMES, 
        strip=True
    )

