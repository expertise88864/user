"""Compile approved fixed typography choices into the existing public stylesheet.

No article prose, schema, font downloads or author-supplied CSS are generated.
Removing overrides restores the manually maintained stylesheet byte for byte.
"""
from __future__ import annotations
import re
from _site_settings_data import CONTRACT, exact

BEGIN, END = '/* dn-site-settings:begin */', '/* dn-site-settings:end */'
BLOCK = re.compile(r'\r?\n/\* dn-site-settings:begin \*/\r?\n[\s\S]*?/\* dn-site-settings:end \*/\r?\n')


def theme_css(font):
    exact(font, CONTRACT['fonts'])
    if any(not isinstance(font[key], str) or font[key] not in allowed
           for key, allowed in CONTRACT['fonts'].items()):
        raise ValueError('Invalid typography choice')
    rules = []
    if font['bodyFont']:
        rules.append('body{font-family:' + font['bodyFont'] + '!important}')
    if font['headFont']:
        rules.append('h1,h2,h3,h4,.font-display{font-family:' + font['headFont'] + '!important}')
    if font['bodySize']:
        rules.append('article p,article li,article td{font-size:' + font['bodySize'] + '!important}')
    return '\n'.join(rules)


def render_theme(source, font):
    rules = theme_css(font)
    # A broken marker must never cause deletion of unrelated maintained rules.
    starts, ends = source.count(BEGIN), source.count(END)
    matches = list(BLOCK.finditer(source))
    if starts != ends or starts > 1 or len(matches) != starts:
        raise ValueError('Malformed generated typography block')
    base = BLOCK.sub('', source)
    newline = '\r\n' if '\r\n' in base else '\n'
    block = newline + BEGIN + newline + rules.replace('\n', newline) + newline + END + newline
    return base + (block if rules else '')
