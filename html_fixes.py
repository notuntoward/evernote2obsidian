#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# html_fixes.py
# =============
#
# HTML link fixes and resource bundling for evernote2obsidian
# Minimal additions to fix file:// protocol issues

import base64
import mimetypes
import os
import re
import urllib.parse

def make_web_safe_link_path(note_path: str, current_file_path: str = "") -> str:
    """Convert a note path to a web-safe relative link that works with file:// protocol."""
    if not note_path:
        return ""
    
    if not isinstance(note_path, str):
        return str(note_path) # e.g an int froma failed hash lookup
    
    # Normalize path separators
    note_path = note_path.replace('\\', '/')
    current_file_path = current_file_path.replace('\\', '/') if current_file_path else ""

    # Calculate relative path if we have current file context
    if current_file_path:
        try:
            current_dir = os.path.dirname(current_file_path)
            rel_path = os.path.relpath(note_path, current_dir)
            rel_path = rel_path.replace('\\', '/')
        except (ValueError, OSError):
            rel_path = note_path
    else:
        rel_path = note_path

    # URL encode each path component to handle special characters
    parts = rel_path.split('/')
    encoded_parts = [urllib.parse.quote(part, safe='') for part in parts if part]
    web_path = '/'.join(encoded_parts)

    # Ensure proper relative path format for file:// protocol
    if not web_path.startswith('./') and not web_path.startswith('../') and not web_path.startswith('/'):
        web_path = './' + web_path

    return web_path

def embed_resource_as_data_url(resource_path: str, mime_type: str, base_dir: str) -> str:
    """Embed a resource as a data URL for SingleFile-style bundling."""
    try:
        full_path = os.path.join(base_dir, resource_path)
        if not os.path.exists(full_path):
            return None

        with open(full_path, 'rb') as f:
            resource_data = f.read()

        encoded_data = base64.b64encode(resource_data).decode('utf-8')
        data_url = f"data:{mime_type};base64,{encoded_data}"

        return data_url

    except Exception:
        return None

def bundle_html_resources(html_content: str, base_dir: str, bundle_enabled: bool = True) -> str:
    """Bundle resources into HTML for self-contained files."""
    if not bundle_enabled:
        return html_content

    # Embed images as data URLs
    def embed_image(match):
        src_path = match.group(1)
        if src_path.startswith('data:') or src_path.startswith('http'):
            return match.group(0)

        try:
            full_path = os.path.join(base_dir, src_path)
            if os.path.exists(full_path):
                mime_type, _ = mimetypes.guess_type(full_path)
                if mime_type and mime_type.startswith('image/'):
                    data_url = embed_resource_as_data_url(src_path, mime_type, base_dir)
                    if data_url:
                        return match.group(0).replace(f'src="{src_path}"', f'src="{data_url}"')
        except Exception:
            pass

        return match.group(0)

    html_content = re.sub(r'<img[^>]+src="([^"]+)"[^>]*>', embed_image, html_content)

    return html_content
