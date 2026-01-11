"""
Text processing utilities for spell-checking and content cleaning.
Handles:
- Spell correction for search queries and generated content
- Duplicate heading detection and removal
"""

import re
from typing import List, Tuple, Optional
from spellchecker import SpellChecker


# Initialize spell checker with English dictionary
_spell = SpellChecker()

# Domain-specific terms that should NOT be corrected
# Add technical/scientific terms here
DOMAIN_TERMS = {
    # Fitness & Exercise
    "calisthenics", "plyometrics", "hypertrophy", "isometric", "isotonic",
    "bodyweight", "reps", "cardio", "hiit", "tabata", "crossfit",

    # Medical & Scientific
    "pathophysiology", "etiology", "epidemiology", "pharmacokinetics",
    "biomarkers", "genomics", "proteomics", "metabolomics", "transcriptomics",
    "immunology", "oncology", "neurology", "cardiology", "endocrinology",

    # Technology
    "api", "apis", "sdk", "json", "html", "css", "javascript", "python",
    "microservices", "kubernetes", "docker", "devops", "ci", "cd",

    # General Academic
    "meta-analysis", "metaanalysis", "rct", "rcts", "pubmed", "doi",
    "peer-reviewed", "systematic", "qualitative", "quantitative",
}

# Add domain terms to the spell checker's known words
_spell.word_frequency.load_words(DOMAIN_TERMS)


def correct_spelling(text: str, preserve_case: bool = True) -> str:
    """
    Correct spelling mistakes in text while preserving:
    - Technical/domain-specific terms
    - Proper nouns (capitalized words not in headings)
    - URLs and email addresses
    - Numbers and special characters
    - Markdown formatting

    Args:
        text: Input text to correct
        preserve_case: If True, preserves original casing of corrected words

    Returns:
        Text with spelling corrections applied
    """
    if not text:
        return text

    # Protect URLs, emails, and markdown elements from modification
    protected = []

    # Protect URLs
    url_pattern = r'https?://[^\s\]\)]+|www\.[^\s\]\)]+'
    for match in re.finditer(url_pattern, text):
        protected.append((match.start(), match.end(), match.group()))

    # Protect email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    for match in re.finditer(email_pattern, text):
        protected.append((match.start(), match.end(), match.group()))

    # Protect markdown code blocks and inline code
    code_pattern = r'```[\s\S]*?```|`[^`]+`'
    for match in re.finditer(code_pattern, text):
        protected.append((match.start(), match.end(), match.group()))

    # Protect markdown links [text](url)
    link_pattern = r'\[[^\]]+\]\([^\)]+\)'
    for match in re.finditer(link_pattern, text):
        protected.append((match.start(), match.end(), match.group()))

    # Protect citations like [1], [S1-1], etc.
    citation_pattern = r'\[S?\d+(?:-\d+)?\]'
    for match in re.finditer(citation_pattern, text):
        protected.append((match.start(), match.end(), match.group()))

    # Identify markdown heading regions (words in headings should be spell-checked)
    heading_regions = []
    heading_pattern = r'^(#{1,6})\s+(.+)$'
    for match in re.finditer(heading_pattern, text, re.MULTILINE):
        # Store the region of the heading text (after the # symbols)
        heading_start = match.start(2)
        heading_end = match.end(2)
        heading_regions.append((heading_start, heading_end))

    def is_in_heading(pos: int) -> bool:
        """Check if position is within a markdown heading"""
        return any(start <= pos < end for start, end in heading_regions)

    # Word pattern - match words while excluding protected regions
    word_pattern = r'\b[A-Za-z]+\b'

    corrections = []

    for match in re.finditer(word_pattern, text):
        word = match.group()
        start, end = match.start(), match.end()

        # Skip if in protected region
        is_protected = any(p[0] <= start < p[1] for p in protected)
        if is_protected:
            continue

        # Skip proper nouns (capitalized words not at sentence start)
        # BUT always check words in markdown headings
        in_heading = is_in_heading(start)
        if not in_heading and word[0].isupper() and start > 0 and text[start-1] not in '.!?\n':
            continue

        # Skip short words (likely abbreviations or intentional)
        if len(word) <= 2:
            continue

        # Skip if it's a known domain term (case-insensitive)
        if word.lower() in DOMAIN_TERMS:
            continue

        # Check spelling
        word_lower = word.lower()
        if word_lower not in _spell:
            correction = _spell.correction(word_lower)
            if correction and correction != word_lower:
                # Preserve original case
                if preserve_case:
                    if word.isupper():
                        correction = correction.upper()
                    elif word[0].isupper():
                        correction = correction.capitalize()

                corrections.append((start, end, word, correction))

    # Apply corrections in reverse order to preserve positions
    result = text
    for start, end, original, correction in reversed(corrections):
        result = result[:start] + correction + result[end:]

    return result


def remove_duplicate_headings(text: str) -> str:
    """
    Remove duplicate or near-duplicate headings from markdown text.

    Handles cases like:
    - Exact duplicates: "## Introduction" appearing twice
    - Case variations: "## Introduction" and "## introduction"
    - Minor variations: "## Introduction" and "## Introduction:"

    Args:
        text: Markdown text with potential duplicate headings

    Returns:
        Text with duplicate headings removed (keeps first occurrence)
    """
    if not text:
        return text

    lines = text.split('\n')
    seen_headings = {}  # normalized_heading -> first_line_index
    lines_to_remove = set()

    for i, line in enumerate(lines):
        # Check if line is a markdown heading (# through ######)
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2)

            # Normalize heading for comparison
            normalized = _normalize_heading(heading_text)
            key = (level, normalized)

            if key in seen_headings:
                # This is a duplicate - mark for removal
                lines_to_remove.add(i)
                # Also remove any blank lines immediately after
                if i + 1 < len(lines) and not lines[i + 1].strip():
                    lines_to_remove.add(i + 1)
            else:
                seen_headings[key] = i

    # Rebuild text without duplicate headings
    result_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
    return '\n'.join(result_lines)


def _normalize_heading(heading: str) -> str:
    """
    Normalize a heading for duplicate comparison.

    - Converts to lowercase
    - Removes punctuation at the end
    - Removes extra whitespace
    - Removes common suffixes like "and the"
    """
    # Convert to lowercase
    normalized = heading.lower().strip()

    # Remove trailing punctuation
    normalized = re.sub(r'[:\.\-]+$', '', normalized).strip()

    # Normalize whitespace
    normalized = ' '.join(normalized.split())

    return normalized


def clean_report_text(text: str) -> str:
    """
    Apply all text cleaning operations to a report:
    1. Spell checking
    2. Duplicate heading removal

    Args:
        text: Raw report text

    Returns:
        Cleaned report text
    """
    # First remove duplicate headings
    text = remove_duplicate_headings(text)

    # Then apply spell checking
    text = correct_spelling(text)

    return text


def correct_query(query: str) -> Tuple[str, List[str]]:
    """
    Correct spelling in a search query.
    Returns the corrected query and a list of corrections made.

    Args:
        query: Search query string

    Returns:
        Tuple of (corrected_query, list of correction descriptions)
    """
    if not query:
        return query, []

    corrections_made = []
    words = query.split()
    corrected_words = []

    for word in words:
        # Clean word for checking (remove punctuation at edges)
        clean_word = re.sub(r'^[^\w]+|[^\w]+$', '', word)

        if not clean_word or len(clean_word) <= 2:
            corrected_words.append(word)
            continue

        # Skip if it's a known domain term
        if clean_word.lower() in DOMAIN_TERMS:
            corrected_words.append(word)
            continue

        # Check spelling
        word_lower = clean_word.lower()
        if word_lower not in _spell:
            correction = _spell.correction(word_lower)
            if correction and correction != word_lower:
                # Preserve case
                if clean_word.isupper():
                    correction = correction.upper()
                elif clean_word[0].isupper():
                    correction = correction.capitalize()

                # Replace the word while preserving surrounding punctuation
                new_word = word.replace(clean_word, correction)
                corrected_words.append(new_word)
                corrections_made.append(f"'{clean_word}' -> '{correction}'")
            else:
                corrected_words.append(word)
        else:
            corrected_words.append(word)

    return ' '.join(corrected_words), corrections_made


def add_domain_terms(terms: List[str]) -> None:
    """
    Add additional domain-specific terms to the spell checker.
    These terms will not be flagged as spelling errors.

    Args:
        terms: List of terms to add to the known words
    """
    for term in terms:
        DOMAIN_TERMS.add(term.lower())
    _spell.word_frequency.load_words([t.lower() for t in terms])
