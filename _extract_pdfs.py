#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extract text from the 5 guideline PDFs the user dropped in Downloads.

Writes to _pdf_extracts/<name>.txt so the agent can ingest them as plain
text without rerunning pdftoppm. Strips repeated page headers/footers
and trims excessive whitespace.
"""
import os, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import fitz  # pymupdf

ROOT = r'C:\Users\User\Downloads'
OUT  = r'C:\Users\User\Desktop\翊嘉\程式\個人網頁\DermNotes\_pdf_extracts'
os.makedirs(OUT, exist_ok=True)

PDFS = [
    'Urticaria BJD.pdf',
    'Vitiligo BJD.pdf',
    'acne NICE.pdf',
    'acitretin BJD.pdf',
    'Acne guideline JAAD.pdf',
]

for fname in PDFS:
    src = os.path.join(ROOT, fname)
    if not os.path.exists(src):
        print(f'MISSING: {src}'); continue
    doc = fitz.open(src)
    chunks = []
    for i, page in enumerate(doc, 1):
        txt = page.get_text('text')
        # Trim trailing blanks
        txt = re.sub(r'[ \t]+\n', '\n', txt)
        txt = re.sub(r'\n{3,}', '\n\n', txt)
        chunks.append(f'\n\n========== PAGE {i} ==========\n\n' + txt)
    out_path = os.path.join(OUT, fname.replace('.pdf','.txt'))
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(''.join(chunks))
    print(f'✓ {fname} → {len(doc)} pages, {os.path.getsize(out_path)/1024:.0f} KB')
    doc.close()
