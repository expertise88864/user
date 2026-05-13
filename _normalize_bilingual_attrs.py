from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent


ACNE_H1 = '''<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">
<span data-zh="痘痘 8 大迷思" data-en="8 Acne Myths">痘痘 8 大迷思</span><br/>
<span class="teal-text" data-zh="民眾最常誤會的觀念，一次澄清" data-en="The misconceptions patients ask about every week">民眾最常誤會的觀念，一次澄清</span>
</h1>'''

SUNSCREEN_H1 = '''<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]">
<span data-zh="防曬 8 大迷思" data-en="8 Sunscreen Myths">防曬 8 大迷思</span><br/>
<span class="teal-text" data-zh="室內、陰天、SPF、物理化學一次釐清" data-en="Indoors, cloudy days, SPF, physical vs chemical — clarified at once">室內、陰天、SPF、物理化學一次釐清</span>
</h1>'''

ACNE_DISCLAIMER = '''<div class="disclaimer" data-zh="<strong>提醒 ·</strong> 本文僅供衛教參考。若你的痘痘嚴重（囊腫、結節、留疤），請至皮膚科診療，別只靠網路資訊。" data-en="<strong>Reminder ·</strong> This article is for general education only. If your acne is severe (cystic, nodular, scarring), please see a dermatologist — don't rely on online articles alone."><strong data-zh="提醒 ·" data-en="Reminder ·">提醒 ·</strong> 本文僅供衛教參考。若你的痘痘嚴重（囊腫、結節、留疤），請至皮膚科診療，別只靠網路資訊。
</div>'''

SUNSCREEN_DISCLAIMER = '''<div class="disclaimer" data-zh="<strong>提醒 ·</strong> 本文僅供衛教參考。光敏感體質、長期戶外工作、有皮膚癌病史者，請至皮膚科個別評估。" data-en="<strong>Reminder ·</strong> This article is general education only. If you're photosensitive, work outdoors long-term, or have a skin-cancer history, please see a dermatologist for individualized advice."><strong data-zh="提醒 ·" data-en="Reminder ·">提醒 ·</strong> 本文僅供衛教參考。光敏感體質、長期戶外工作、有皮膚癌病史者，請至皮膚科個別評估。
</div>'''

ACNE_KEY_INSIGHT = '''<p style="margin:14px 0 0; font-size:12.5px; color:#7f1d1d; text-align:center; line-height:1.7; font-family:'Noto Sans TC',sans-serif;" data-zh="<strong>關鍵理解</strong>：四個成因環環相扣 — <strong>口服 A 酸是唯一同時擊中所有 4 個的藥</strong>；一般治療多只針對其中 1-2 個。所以中重度痘痘外用治療無效時，要往口服思考。" data-en="<strong>Key insight</strong>: the 4 causes interlock — <strong>oral isotretinoin is the only treatment that hits all 4 at once</strong>; most other treatments hit just 1–2. That's why moderate-to-severe acne unresponsive to topicals deserves a discussion about going oral."><strong data-zh="關鍵理解" data-en="Key insight">關鍵理解</strong>：四個成因環環相扣 — <strong data-zh="口服 A 酸是唯一同時擊中所有 4 個的藥" data-en="oral isotretinoin is the only treatment that hits all 4 at once">口服 A 酸是唯一同時擊中所有 4 個的藥</strong>；一般治療多只針對其中 1-2 個。所以中重度痘痘外用治療無效時，要往口服思考。</p>'''

ISOTRETINOIN_TLDR = '''<p class="mt-6 text-[15.5px] sm:text-[17px] text-ink-700 leading-[1.9] tldr"
data-zh="這是給住院醫師(R1-R3)、皮膚科同仁、和對藥理有興趣的讀者的完整整理。內容涵蓋：13-cis-RA 的藥理與 isomerization、四大機轉(sebocyte apoptosis、comedolysis、antimicrobial、anti-inflammatory)、適應症與 off-label、劑量學（累積劑量證據、低劑量與間歇 protocol）、副作用全光譜（mucocutaneous、MSK、ocular、neuropsych、hepatic、lipid、IBD 爭議、teratogenicity）、藥物交互作用(tetracycline → IIH)、停藥後 laser timing 的最新證據、以及 2024 AAD acne guideline 整理。"
data-en="A study-grade write-up for residents and dermatology clinicians. Covers pharmacology of 13-cis-RA, the four mechanisms (sebocyte apoptosis, comedolysis, antimicrobial, anti-inflammatory), full indication list including off-label, dose science (cumulative-dose evidence, low-dose protocols, intermittent regimens), full AE spectrum, drug interactions, post-iso laser timing, and AAD 2024 acne guideline integration.">
這是給住院醫師(R1-R3)、皮膚科同仁、和對藥理有興趣的讀者的完整整理。內容涵蓋：13-cis-RA 的<strong data-zh="藥理與 isomerization" data-en="Pharmacology and isomerization">藥理與 isomerization</strong>、<strong data-zh="四大機轉" data-en="Four mechanisms">四大機轉</strong>(sebocyte apoptosis、comedolysis、antimicrobial、anti-inflammatory)、<strong data-zh="適應症與 off-label" data-en="Indications and off-label uses">適應症與 off-label</strong>、<strong data-zh="劑量學" data-en="Dosing">劑量學</strong>（累積劑量證據、低劑量與間歇 protocol）、<strong data-zh="副作用全光譜" data-en="Full spectrum of adverse effects">副作用全光譜</strong>（mucocutaneous、MSK、ocular、neuropsych、hepatic、lipid、IBD 爭議、teratogenicity）、<strong data-zh="藥物交互作用" data-en="Drug interactions">藥物交互作用</strong>(tetracycline → IIH)、<strong data-zh="停藥後 laser timing" data-en="Post-discontinuation laser timing">停藥後 laser timing</strong> 的最新證據、以及 <strong>2024 AAD acne guideline</strong> 整理。
</p>'''


def replace_between(src: str, start: str, end: str, replacement: str) -> str:
    i = src.find(start)
    if i < 0:
        return src
    j = src.find(end, i)
    if j < 0:
        return src
    j += len(end)
    return src[:i] + replacement + src[j:]


def normalize_acne(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    before = src
    src = replace_between(src, '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]"', '</h1>', ACNE_H1)
    src = replace_between(src, '<div class="disclaimer" data-zh="<strong data-zh="提醒 ·"', '</div>', ACNE_DISCLAIMER)
    src = replace_between(src, '<p style="margin:14px 0 0; font-size:12.5px; color:#7f1d1d;', '</p>', ACNE_KEY_INSIGHT)
    src = re.sub(
        r'<h2 id="m5-en">Myth 5: Chocolate, fried food, and spicy food directly cause breakouts</h2>[\s\S]*?(?=<h2 id="m6-en">)',
        '',
        src,
        count=1,
    )
    src = src.replace('id="m6-en">Myth 5:', 'id="m5-en">Myth 5:')
    src = src.replace('id="m7-en">Myth 6:', 'id="m6-en">Myth 6:')
    src = src.replace('id="m8-en">Myth 7:', 'id="m7-en">Myth 7:')
    src = src.replace('id="m9-en">Myth 8:', 'id="m8-en">Myth 8:')
    if src != before:
        path.write_text(src, encoding="utf-8")
        return True
    return False


def normalize_sunscreen(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    before = src
    src = replace_between(src, '<h1 class="font-display font-bold leading-[1.18] text-[32px] sm:text-[44px]"', '</h1>', SUNSCREEN_H1)
    src = replace_between(src, '<div class="disclaimer" data-zh="<strong data-zh="提醒 ·"', '</div>', SUNSCREEN_DISCLAIMER)
    if src != before:
        path.write_text(src, encoding="utf-8")
        return True
    return False


def normalize_isotretinoin(path: Path) -> bool:
    src = path.read_text(encoding="utf-8")
    before = src
    src = re.sub(
        r'<p class="mt-6 text-\[15\.5px\] sm:text-\[17px\] text-ink-700 leading-\[1\.9\] tldr"\s+data-zh="這是給住院醫師[\s\S]*?</p>',
        ISOTRETINOIN_TLDR,
        src,
        count=1,
    )
    if src != before:
        path.write_text(src, encoding="utf-8")
        return True
    return False


def normalize_count_labels() -> int:
    changed = 0
    for path in ROOT.rglob("*"):
        if path.is_dir() or any(part in {".git", "node_modules"} for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix.lower() not in {".html", ".js", ".json", ".xml"}:
            continue
        src = path.read_text(encoding="utf-8")
        out = src.replace("痘痘 9 大迷思", "痘痘 8 大迷思")
        out = out.replace("9 Acne Myths", "8 Acne Myths")
        out = out.replace("9 acne myths", "8 acne myths")
        out = out.replace("關於防曬的 9 個迷思", "關於防曬的 8 個迷思")
        out = out.replace("9 Sunscreen Myths", "8 Sunscreen Myths")
        out = out.replace("9 sunscreen myths", "8 sunscreen myths")
        if out != src:
            path.write_text(out, encoding="utf-8")
            changed += 1
    return changed


def main() -> None:
    touched: list[str] = []
    for rel, fn in {
        "blog/acne-myths.html": normalize_acne,
        "blog/sunscreen-myths.html": normalize_sunscreen,
        "blog/isotretinoin-clinical.html": normalize_isotretinoin,
    }.items():
        if fn(ROOT / rel):
            touched.append(rel)
    count_files = normalize_count_labels()
    print(f"Normalized bilingual attrs in {len(touched)} source files; count labels touched in {count_files} files")


if __name__ == "__main__":
    main()
