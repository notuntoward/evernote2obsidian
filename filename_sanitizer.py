#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# filename_sanitizer.py
# ====================
#
# Filename sanitization utilities for evernote2obsidian
# Modified to only shorten when necessary, from right to left


from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Set


# Cross-platform constraints
WINDOWS_RESERVED = {
    'CON', 'PRN', 'AUX', 'NUL',
    *{f'COM{i}' for i in range(1, 10)},
    *{f'LPT{i}' for i in range(1, 10)}
}

FORBIDDEN_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\[\]\^#%]|[\x00-\x1f]')
REPLACEMENT_CHAR = '_'

# File size limits
MAX_TOTAL_PATH = 260
MAX_COMPONENT = 255
DEFAULT_MAX_BASENAME = 150


# NLP-inspired shortening (only used when necessary)
STOPWORDS = {
    'the','a','an','and','or','but','if','then','else','when','while','for','to','of','in','on','at','by','from',
    'with','about','into','through','during','before','after','above','below','over','under','again','further',
    'is','are','was','were','be','been','being','do','does','did','doing','have','has','had','having',
    'it','its',"it's",'this','that','these','those','as','than','too','very','can','will','just','not','no',
    'you','your','yours','we','our','ours'
}

NOISE_TOKENS = {'index','default','home','page','http','https','www','html','htm'}

def tokenize_name(name: str) -> list[str]:
    """Extract alphanumeric tokens from a name."""
    return re.findall(r"[A-Za-z0-9']+", name)

def is_informative(tok: str) -> bool:
    """Check if a token is informative (not a stopword or noise token)."""
    t = tok.lower()
    if t in STOPWORDS or t in NOISE_TOKENS:
        return False
    return True

def abbreviate_token(tok: str, max_len: int = 10) -> str:
    """
    Abbreviate a single token using intelligent strategies.
    
    Strategies (in order):
    1. Return as-is if digit or already short enough
    2. Extract CamelCase initials
    3. Extract snake_case/hyphen-case initials
    4. Drop vowels from middle
    """
    if tok.isdigit():
        return tok

    if len(tok) <= max_len:
        return tok

    # CamelCase initials
    if re.search(r'[A-Z].*[A-Z]', tok):
        caps = ''.join(ch for ch in tok if ch.isupper())
        if 2 <= len(caps) <= max_len:
            return caps

    # snake/hyphen initials
    parts = re.split(r'[_\-]+', tok)
    if len(parts) > 1:
        initials = ''.join(p[0] for p in parts if p)
        if 2 <= len(initials) <= max_len:
            return initials

    # vowel-drop core
    core = tok[1:-1]
    core_novowels = re.sub(r'[aeiouAEIOU]', '', core)
    candidate = (tok[0] + core_novowels + tok[-1])[:max_len]
    if len(candidate) < 3 and len(tok) >= 3:
        candidate = tok[:max_len]
    return candidate


def shorten_from_right(tokens: list[str], max_length: int, separator: str = ' ') -> str:
    """
    Shorten a list of tokens to fit within max_length.
    Only shortens when necessary, applying strategies from right to left.
    
    Strategy order (applied right-to-left):
    1. Remove stopwords from the right
    2. Abbreviate long tokens (>10 chars) from the right
    3. Remove tokens from the right (keeping at least the first token)
    4. Truncate if still too long
    
    Args:
        tokens: List of token strings
        max_length: Maximum allowed length for the joined result
        separator: String to join tokens (default: ' ')
    
    Returns:
        Shortened string that fits within max_length
    """
    # First, check if we even need to shorten
    current = separator.join(tokens)
    if len(current) <= max_length:
        return current
    
    # Make a working copy
    working_tokens = tokens.copy()
    
    # Strategy 1: Remove stopwords from right to left
    for i in range(len(working_tokens) - 1, -1, -1):
        if not is_informative(working_tokens[i]):
            working_tokens.pop(i)
            current = separator.join(working_tokens)
            if len(current) <= max_length:
                return current
    
    # Strategy 2: Abbreviate long tokens (>10 chars) from right to left
    for i in range(len(working_tokens) - 1, -1, -1):
        if len(working_tokens[i]) > 10:
            original = working_tokens[i]
            abbreviated = abbreviate_token(original)
            if abbreviated != original and len(abbreviated) < len(original):
                working_tokens[i] = abbreviated
                current = separator.join(working_tokens)
                if len(current) <= max_length:
                    return current
    
    # Strategy 3: Remove tokens from right to left (keep at least first token)
    while len(working_tokens) > 1:
        working_tokens.pop()
        current = separator.join(working_tokens)
        if len(current) <= max_length:
            return current
    
    # Strategy 4: Last resort - truncate
    current = separator.join(working_tokens)
    if len(current) > max_length:
        current = current[:max_length].rstrip(separator + '-_ .')
    
    return current


def sanitize_component(name: str, max_length: int = MAX_COMPONENT, *, allow_spaces: bool = True) -> str:
    """
    Sanitize a single filename component by removing forbidden characters
    and ensuring it doesn't exceed max_length.
    
    Args:
        name: The filename component to sanitize
        max_length: Maximum allowed length (default: 255)
        allow_spaces: Whether to allow spaces (default: True)
    
    Returns:
        Sanitized filename component
    """
    if not name:
        return 'unnamed'

    separator = ' ' if allow_spaces else REPLACEMENT_CHAR
    name = FORBIDDEN_CHARS_PATTERN.sub(REPLACEMENT_CHAR, name)
    name = name.replace(':', REPLACEMENT_CHAR)
    name = name.rstrip(' .')
    name = re.sub(f'{re.escape(REPLACEMENT_CHAR)}+', REPLACEMENT_CHAR, name)

    if allow_spaces:
        name = name.replace(REPLACEMENT_CHAR, separator)
        name = re.sub(r' +', ' ', name)
        name = name.strip()

    base = name.split('.')[0].upper()
    if base in WINDOWS_RESERVED:
        name = separator + name

    if len(name) > max_length:
        if '.' in name:
            stem = name[:name.rfind('.')]
            suffix = name[name.rfind('.'):]
        else:
            stem, suffix = name, ''
        name = stem[:max_length - len(suffix)] + suffix

    return name or 'unnamed'


def get_unique_filename_advanced(title: str, extension: str, existing_files: Set[str], 
                                max_base_len: int = DEFAULT_MAX_BASENAME, 
                                use_spaces: bool = True) -> str:
    """
    Generate a unique, sanitized filename from a title.
    Only shortens the filename if it exceeds max_base_len.
    When shortening is needed, applies strategies from right to left.
    
    Args:
        title: Original title/filename
        extension: File extension (e.g., '.md')
        existing_files: Set of existing filenames (lowercase) to avoid conflicts
        max_base_len: Maximum length for the base filename (default: 150)
        use_spaces: Whether to use spaces in the filename (default: True)
    
    Returns:
        Unique, sanitized filename
    """
    tokens = tokenize_name(title)
    if not tokens:
        base = 'unnamed'
    else:
        separator = ' ' if use_spaces else '-'
        # Use the new shorten_from_right function
        base = shorten_from_right(tokens, max_base_len, separator)

    base = sanitize_component(base, max_length=max_base_len, allow_spaces=use_spaces)
    filename = sanitize_component(base + extension, max_length=MAX_COMPONENT, allow_spaces=use_spaces)

    counter = 2
    original_filename = filename

    while filename.lower() in existing_files:
        if '.' in original_filename:
            name_part = original_filename[:original_filename.rfind('.')]
            ext_part = original_filename[original_filename.rfind('.'):]
        else:
            name_part = original_filename
            ext_part = ''

        version_suffix = f"-v{counter}"
        new_name = name_part + version_suffix

        max_name_len = MAX_COMPONENT - len(ext_part) - len(version_suffix)
        if len(new_name) > max_name_len:
            truncated_base = name_part[:max_name_len].rstrip('-_ .')
            new_name = truncated_base + version_suffix

        filename = new_name + ext_part
        counter += 1

        if counter > 50:
            hash_suffix = f"-x{hashlib.blake2s(title.encode('utf-8'), digest_size=4).hexdigest()[:6]}"
            max_name_len = MAX_COMPONENT - len(ext_part) - len(hash_suffix)
            truncated_base = name_part[:max_name_len].rstrip('-_ .')
            filename = truncated_base + hash_suffix + ext_part
            break

    return filename


class FilenameManager:
    """
    Manager class for handling filename sanitization and uniqueness tracking.
    """
    def __init__(self, use_spaces: bool = True):
        self.use_spaces = use_spaces
        self.existing_files: Set[str] = set()
        self.filename_mappings: Dict[str, str] = {}

    def get_sanitized_filename(self, original_title: str, extension: str, 
                              max_base_len: int = DEFAULT_MAX_BASENAME) -> str:
        """
        Get a sanitized, unique filename for the given title.
        
        Args:
            original_title: Original note/file title
            extension: File extension including the dot (e.g., '.md')
            max_base_len: Maximum length for the base filename (default: 150)
        
        Returns:
            Sanitized, unique filename
        """
        sanitized = get_unique_filename_advanced(
            original_title, extension, self.existing_files, 
            max_base_len, self.use_spaces
        )

        self.existing_files.add(sanitized.lower())
        original_filename = original_title + extension
        self.filename_mappings[original_filename] = sanitized

        return sanitized

    def get_mapping(self, original_filename: str) -> str:
        """Get the sanitized filename for a given original filename."""
        return self.filename_mappings.get(original_filename, original_filename)
