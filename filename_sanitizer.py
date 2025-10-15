#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# filename_sanitizer.py
# ====================
#
# Filename sanitization utilities for evernote2obsidian
# Added as minimal enhancement for cross-platform compatibility

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

# NLP-inspired shortening
STOPWORDS = {
    'the','a','an','and','or','but','if','then','else','when','while','for','to','of','in','on','at','by','from',
    'with','about','into','through','during','before','after','above','below','over','under','again','further',
    'is','are','was','were','be','been','being','do','does','did','doing','have','has','had','having',
    'it','its',"it's",'this','that','these','those','as','than','too','very','can','will','just','not','no',
    'you','your','yours','we','our','ours'
}

NOISE_TOKENS = {'index','default','home','page','http','https','www','html','htm'}

def tokenize_name(name: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", name)

def is_informative(tok: str) -> bool:
    t = tok.lower()
    if t in STOPWORDS or t in NOISE_TOKENS:
        return False
    return True

def abbreviate_token(tok: str, max_len: int = 10) -> str:
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

def sanitize_component(name: str, max_length: int = MAX_COMPONENT, *, allow_spaces: bool = True) -> str:
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
    tokens = tokenize_name(title)
    if not tokens:
        base = 'unnamed'
    else:
        informative = [t for t in tokens if is_informative(t)]
        if informative:
            tokens = informative

        separator = ' ' if use_spaces else '-'
        base = separator.join(tokens)
        if len(base) > max_base_len:
            base = base[:max_base_len].rstrip('-_ .')

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
    def __init__(self, use_spaces: bool = True):
        self.use_spaces = use_spaces
        self.existing_files: Set[str] = set()
        self.filename_mappings: Dict[str, str] = {}

    def get_sanitized_filename(self, original_title: str, extension: str, 
                              max_base_len: int = DEFAULT_MAX_BASENAME) -> str:
        sanitized = get_unique_filename_advanced(
            original_title, extension, self.existing_files, 
            max_base_len, self.use_spaces
        )

        self.existing_files.add(sanitized.lower())
        original_filename = original_title + extension
        self.filename_mappings[original_filename] = sanitized

        return sanitized

    def get_mapping(self, original_filename: str) -> str:
        return self.filename_mappings.get(original_filename, original_filename)
