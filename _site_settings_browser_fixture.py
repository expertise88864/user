"""Read-only public-page fixture using the actual settings compilers.

Hypothetical approved choices are used only in intercepted browser documents;
the source configuration and real generated pages are never written.
"""
import json
from _site_settings_data import ROOT, load_settings
from _site_settings_render import render_theme
from _sync_hub_catalog import HUBS, load_catalog, load_overrides, public_catalog, sync_source


def main():
    _, catalog = load_settings()
    names = [row['slug'] for row in catalog['articles']]
    order = names[-2:] + names[:-2]
    font = {'bodyFont':"Georgia,'Noto Serif TC',serif",'headFont':"'Inter','Noto Sans TC',sans-serif",'bodySize':'18px'}
    articles = public_catalog(load_catalog(), ROOT)
    overrides = load_overrides(load_catalog())
    pages = {}
    for name, element in HUBS.items():
        address = '/' if name == 'index.html' else '/blog'
        pages[address] = sync_source((ROOT / name).read_text(encoding='utf8'), element,
                                     articles, overrides.get(name), order=order)
    pages['/blog/acne-myths'] = (ROOT/'blog/acne-myths.html').read_text(encoding='utf8')
    css = render_theme((ROOT/'assets/dn-below-fold.css').read_text(encoding='utf8'), font)
    print(json.dumps({'pages':pages,'css':css,'order':order,'font':font},ensure_ascii=True))


if __name__=='__main__': main()
