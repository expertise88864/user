"""Translate residual CJK strings in the two newest bilingual articles."""
import re
import pathlib

FILES = [
    'blog/severe-scabies-treatment.html',
    'blog/dermatologic-oral-examination.html',
]

TR = {
    "提醒：": "Disclaimer:",
    "皮膚刮片顯微鏡（gold standard）": "Skin scraping microscopy (gold standard)",
    "皮膚鏡（dermoscopy）": "Dermoscopy",
    "臨床診斷（IACS 2020 國際共識準則）": "Clinical diagnosis (IACS 2020 consensus criteria)",
    "結論：高劑量沒有比較好。": "Take-away: higher dose was not better.",
    "劑量": "Dose",
    "時程": "Schedule",
    "怎麼吃": "How to take",
    "禁忌與注意": "Contraindications & cautions",
    "塗抹範圍": "Application area",
    "停留時間": "Duration on skin",
    "用量": "Amount",
    "結痂型加強": "For crusted scabies",
    "關鍵原則：": "Key principle:",
    "需要一起治療的人": "People who need co-treatment",
    "同治療策略": "Co-treatment strategy",
    "通報": "Report",
    "個案診斷": "Case diagnosis",
    "同步治療": "Synchronous treatment",
    "隔離結痂型": "Isolate crusted cases",
    "環境清潔": "Environmental cleaning",
    "監測 6 週": "6-week monitoring",
    "5% permethrin 乳膏": "5% permethrin cream",
    "口服 ivermectin": "Oral ivermectin",
    "請以衛福部食藥署藥品許可證資料庫與健保署藥品給付規定為準": "Refer to the Taiwan FDA drug license database and NHI reimbursement rules for current details",
    "benzyl benzoate 10-25% 乳劑": "Benzyl benzoate 10–25% emulsion",
    "1% lindane 乳膏": "1% lindane cream",
    "合併治療": "Combination therapy",
    "輕度（grade 1）": "Mild (grade 1)",
    "中度（grade 2）": "Moderate (grade 2)",
    "重度（grade 3）": "Severe (grade 3)",
    "台灣特殊族群提醒": "Taiwan-specific note",
    "延伸閱讀：": "Related reading:",
    "陳翊嘉 醫師": "Dr. Yi-Jia Chen",
    "陳翊嘉醫師 · 皮膚科衛教筆記": "Dr. Yi-Jia Chen · Dermatology Notes",
    "外用類固醇完整指南": "Complete topical steroid guide",
    "皮膚切片完整衛教": "Skin biopsy complete guide",
    "皮膚科 25 個最常見問題": "25 most common dermatology questions",
    "關鍵訊息：": "Key message:",
    "需要盡快就醫的紅旗：": "Red flags requiring prompt medical care:",
    "口底（floor of mouth）": "Floor of mouth",
    "軟顎後段": "Posterior soft palate",
    "腮腺管開口（Stensen's papilla, 上頷第二大臼齒對側）": "Parotid (Stensen's) papilla, opposite the second maxillary molar",
    "覆蓋牙根的牙齦": "Gingiva overlying tooth roots",
    "第一塊樣本": "Specimen 1",
    "第二塊樣本": "Specimen 2",
    "器官移植 / 免疫抑制者": "Transplant / immunosuppressed",
    "抗凝血藥 / 抗血小板藥": "Anticoagulants / antiplatelets",
    "放射治療後": "Post-radiation",
    "孕婦": "Pregnancy",
    "皮膚切片與腫瘤切除手術完整衛教": "Skin biopsy & tumor excision complete guide",
    "日光性角化症 AK + 鱗狀細胞癌 SCC": "Actinic keratosis & squamous cell carcinoma",
    "口周皮膚炎完整衛教": "Perioral dermatitis complete guide",
}


def patch(html: str) -> tuple[str, int]:
    count = 0
    # Iterate each interesting tag.
    for tag in ['h1', 'h2', 'h3', 'h4', 'p', 'li', 'strong', 'em',
                'figcaption', 'summary', 'span', 'small', 'div', 'a']:
        pat = re.compile(r'<' + tag + r'\b([^>]*)>([^<]*[一-鿿][^<]*)</' + tag + r'>')

        def repl(m: re.Match) -> str:
            nonlocal count
            attrs, content = m.group(1), m.group(2)
            if 'data-en=' in attrs or 'data-zh=' in attrs:
                return m.group(0)
            stripped = content.strip()
            en = TR.get(stripped)
            if not en:
                return m.group(0)
            zh_esc = stripped.replace('"', '&quot;')
            count += 1
            return f'<{tag}{attrs} data-zh="{zh_esc}" data-en="{en}">{content}</{tag}>'

        html = pat.sub(repl, html)
    return html, count


def main() -> None:
    root = pathlib.Path(__file__).parent
    for rel in FILES:
        p = root / rel
        before = p.read_text(encoding='utf-8')
        after, n = patch(before)
        if n:
            p.write_text(after, encoding='utf-8')
            print(f'{rel}: patched {n} elements')
        else:
            print(f'{rel}: no changes')


if __name__ == '__main__':
    main()
