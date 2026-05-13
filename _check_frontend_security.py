from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def require(errors: list[str], rel: str, needle: str, message: str) -> None:
    if needle not in read(rel):
        errors.append(f"{rel}: {message}")


def forbid(errors: list[str], rel: str, needle: str, message: str) -> None:
    if needle in read(rel):
        errors.append(f"{rel}: {message}")


def main() -> int:
    errors: list[str] = []

    require(errors, "blog/pagefind-search.js", "function escapeHtml(value)", "Pagefind search results should escape text before template insertion")
    require(errors, "blog/pagefind-search.js", "function safeResultUrl(value)", "Pagefind search result URLs should be restricted to same-site paths")
    require(errors, "blog/pagefind-search.js", "function sanitizeExcerpt(value)", "Pagefind excerpts should be sanitized before innerHTML insertion")
    require(errors, "blog/pagefind-search.js", "${escapeHtml(safeResultUrl(d.url))}", "Pagefind result hrefs should use safe same-site URLs")
    require(errors, "blog/pagefind-search.js", "${escapeHtml(d.meta && d.meta.title || '(無標題)')}", "Pagefind result titles should be escaped")
    require(errors, "blog/pagefind-search.js", "${sanitizeExcerpt(d.excerpt)}", "Pagefind result excerpts should be sanitized")
    forbid(errors, "blog/pagefind-search.js", "+ e.message +", "Pagefind search errors should not echo exception messages into innerHTML")
    forbid(errors, "blog/pagefind-search.js", 'href="${d.url}"', "Pagefind result hrefs should not interpolate raw URLs")
    forbid(errors, "blog/pagefind-search.js", "${d.excerpt || ''}", "Pagefind excerpts should not be inserted unsanitized")

    require(errors, "blog/blog-hub.js", "dn-spotlight-card-css", "Spotlight card hover/focus styles should live in CSS")
    require(errors, "blog/blog-hub.js", 'class="dn-spotlight-card"', "Spotlight cards should use a class for interaction styling")
    require(errors, "blog/blog-hub.js", "function escapeHtml(value)", "Spotlight card text should be escaped before template insertion")
    require(errors, "blog/blog-hub.js", "function safeSlug(value)", "Spotlight card links should validate article slugs before template insertion")
    require(errors, "blog/blog-hub.js", "var slug = safeSlug(a.slug);", "Spotlight cards should derive hrefs from validated slugs")
    require(errors, "blog/blog-hub.js", "var title = escapeHtml(a.title || a.slug);", "Spotlight card titles should be escaped")
    require(errors, "blog/blog-hub.js", "var tagEn = escapeHtml(a.tag_en || a.tag || '');", "Spotlight card tags should be escaped")
    forbid(errors, "blog/blog-hub.js", "onmouseover=", "Spotlight cards should not inject inline event attributes")
    forbid(errors, "blog/blog-hub.js", "onmouseout=", "Spotlight cards should not inject inline event attributes")
    forbid(errors, "blog/blog-hub.js", 'href="/blog/\' + a.slug', "Spotlight card hrefs should not interpolate raw slugs")

    require(errors, "blog/blog-shared.js", "dn-bmc-header-css", "Header support link hover/focus styles should live in CSS")
    require(errors, "blog/blog-shared.js", "a.className = 'dn-bmc-header-link';", "Header support link should use a class for interaction styling")
    require(errors, "blog/blog-shared.js", "function escapeHtml(value)", "Command palette result text should be escaped before template insertion")
    require(errors, "blog/blog-shared.js", "function safeSiteUrl(value)", "Command palette result URLs should be restricted to same-site paths")
    require(errors, "blog/blog-shared.js", "function safeSlug(value)", "Command palette article links should validate slugs before indexing")
    require(errors, "blog/blog-shared.js", "var slug = safeSlug(a.slug);", "Command palette should build article URLs from validated slugs")
    require(errors, "blog/blog-shared.js", "escapeHtml(safeSiteUrl(m.url))", "Command palette hrefs should use safe same-site URLs")
    require(errors, "blog/blog-shared.js", "escapeHtml(m.title)", "Command palette titles should be escaped")
    require(errors, "blog/blog-shared.js", "location.href = safeSiteUrl(m.url)", "Command palette Enter navigation should use safe same-site URLs")
    require(errors, "blog/blog-shared.js", "const guideline = String(DN.TDA_GUIDELINE[slug] || '')", "TDA guideline labels should be escaped before template insertion")
    require(errors, "blog/blog-shared.js", "' + guideline + '", "TDA guideline block should insert the escaped label")
    forbid(errors, "blog/blog-shared.js", ".onmouseover", "Runtime code should not assign mouseover handlers via DOM properties")
    forbid(errors, "blog/blog-shared.js", ".onmouseout", "Runtime code should not assign mouseout handlers via DOM properties")
    forbid(errors, "blog/blog-shared.js", 'href="\' + m.url', "Command palette hrefs should not interpolate raw URLs")
    forbid(errors, "blog/blog-shared.js", "'<span class=\"t\">' + m.title", "Command palette titles should not be inserted raw")
    forbid(errors, "blog/blog-shared.js", "' + DN.TDA_GUIDELINE[slug] + '", "TDA guideline block should not insert raw mapping values")

    require(errors, "blog/blog-article-visuals.js", "box.setAttribute('role', 'dialog');", "Image lightbox should expose dialog semantics")
    require(errors, "blog/blog-article-visuals.js", "box.setAttribute('aria-modal', 'true');", "Image lightbox should declare modal behavior to assistive tech")
    require(errors, "blog/blog-article-visuals.js", "box.tabIndex = -1;", "Image lightbox should be programmatically focusable")
    require(errors, "blog/blog-article-visuals.js", "bigImg.setAttribute('decoding', 'async');", "Lightbox image should decode asynchronously")
    require(errors, "blog/blog-article-visuals.js", "box.focus();", "Image lightbox should move focus into the opened dialog")

    require(errors, "admin/admin-extras.js", "message.textContent = m.message ||", "Admin spellcheck should render LanguageTool messages as text")
    require(errors, "admin/admin-extras.js", "context.textContent = `“…${ctx}…” → `;", "Admin spellcheck should render LanguageTool context as text")
    require(errors, "admin/admin-extras.js", "row.append(term, document.createTextNode(' — ' + v));", "Admin dictionary list should render terms as DOM text")
    require(errors, "admin/admin-extras.js", "msgEl.textContent = msg;", "Admin version history should render commit messages as text")
    require(errors, "admin/admin-extras.js", "span.textContent = slug;", "Admin popular picks should render slugs as text")
    forbid(errors, "admin/admin-extras.js", "issue.innerHTML =", "Admin spellcheck should not insert external LanguageTool text with innerHTML")
    forbid(errors, "admin/admin-extras.js", "div.innerHTML = Object.entries(MEDICAL_DICT)", "Admin dictionary list should not be assembled with innerHTML")
    forbid(errors, "admin/admin-extras.js", "div.innerHTML = `<div class=\"ax-v-msg\">", "Admin version history should not insert commit messages with innerHTML")
    forbid(errors, "admin/admin-extras.js", "li.innerHTML = `<span style=\"flex:1\">", "Admin popular picks should not insert slugs with innerHTML")
    forbid(errors, "admin/admin-extras.js", "+ e.message", "Admin UI should not display raw exception messages")
    forbid(errors, "admin/admin-extras.js", "j.message ||", "Admin UI should not display raw provider error messages")
    forbid(errors, "admin/admin-extras.js", "j.error ||", "Admin UI should not display raw API error messages")

    require(errors, "admin.html", "elFileList.textContent = '';", "Admin file list should clear with textContent")
    require(errors, "admin.html", "labelSpan.appendChild(document.createTextNode(f.name));", "Admin file list should render file names as text")
    require(errors, "admin.html", "caption.textContent = f.name;", "Admin image library captions should render file names as text")
    require(errors, "admin.html", "msgEl.textContent = msg;", "Admin history commit messages should render as text")
    require(errors, "admin.html", "const currentFileLabel = escapeHtml(CURRENT_FILE);", "Admin modals should escape current file labels before template insertion")
    require(errors, "admin.html", "msgEl.textContent = msg;", "Admin toast messages should render as text")
    require(errors, "admin.html", "li.appendChild(doc.createTextNode(c.authors + '. ' + c.title + ' '));", "Admin PubMed citations should render citation text as DOM text")
    require(errors, "admin.html", "sourceLink.textContent = '「來源」';", "Admin PubMed source link should render as DOM text")
    require(errors, "admin.html", "const message = escapeHtml(m.message || '');", "Admin spellcheck result messages should be escaped before template insertion")
    require(errors, "admin.html", "escapeHtml(r.value||'')", "Admin spellcheck replacement values should be escaped before template insertion")
    require(errors, "admin.html", 'value="${escapeHtml(title)}"', "Admin metadata modal should escape title values before insertion")
    require(errors, "admin.html", "${escapeHtml(desc)}</textarea>", "Admin metadata modal should escape description values before insertion")
    require(errors, "admin.html", "content=\"'+escapeHtml(val)+'\"", "Admin metadata updates should escape meta content attributes")
    require(errors, "admin.html", "'<title>'+escapeHtml(nt)+'</title>'", "Admin metadata updates should escape title text")
    require(errors, "admin.html", "${escapeHtml(i.zh)}", "Admin bilingual report should escape zh snippets")
    require(errors, "admin.html", "${escapeHtml(i.en)}", "Admin bilingual report should escape en snippets")
    require(errors, "admin.html", "const slugLabel = escapeHtml(slug);", "Admin schedule modal should escape derived slug labels")
    forbid(errors, "admin.html", "d.innerHTML = '<span class=\"ico\">' + ico", "Admin file names should not be inserted with innerHTML")
    forbid(errors, "admin.html", "card.innerHTML = `<img src=\"/${safePath}\"", "Admin image library cards should not insert file names with innerHTML")
    forbid(errors, "admin.html", "item.innerHTML = '<div style=\"font-weight:600;color:#0c5159\">' + msg", "Admin history commit messages should not be inserted with innerHTML")
    forbid(errors, "admin.html", "el.innerHTML = '<span class=\"cd-toast-icon\">' + icon", "Admin toast messages should not be inserted with innerHTML")
    forbid(errors, "admin.html", "li.innerHTML = c.citation", "Admin PubMed citations should not insert citation HTML directly")
    forbid(errors, "admin.html", "m.message.replace(/</g", "Admin spellcheck messages should use shared HTML escaping")
    forbid(errors, "admin.html", "(r.value||'').replace(/</g", "Admin spellcheck replacements should use shared HTML escaping")
    forbid(errors, "admin.html", "value=\"${title.replace", "Admin metadata modal should not use partial quote-only escaping")
    forbid(errors, "admin.html", "content=\"'+val.replace", "Admin metadata updates should not use partial quote-only escaping")
    forbid(errors, "admin.html", "ZH: ${i.zh}", "Admin bilingual report should not insert raw zh snippets")
    forbid(errors, "admin.html", "EN: ${i.en}", "Admin bilingual report should not insert raw en snippets")
    forbid(errors, "admin.html", "drafts/' + slug + '</code>", "Admin schedule modal should not insert raw slug labels")
    forbid(errors, "admin.html", "+ e.message", "Admin UI should not display raw exception messages")

    require(errors, "reset-sw.html", "function setResult(id, className, text)", "Reset tool should render status messages through DOM text")
    require(errors, "reset-sw.html", "span.textContent = text;", "Reset tool status messages should render as text")
    forbid(errors, "reset-sw.html", ".innerHTML = `<span", "Reset tool should not insert status markup with innerHTML")
    forbid(errors, "reset-sw.html", "${e.message}", "Reset tool should not display raw exception messages")

    require(errors, "dashboard.html", "function dnDashEscapeHtml(value)", "Dashboard dynamic chart labels should have HTML escaping")
    require(errors, "dashboard.html", "function dnDashSafeSlug(value)", "Dashboard dynamic article links should validate slugs")
    require(errors, "dashboard.html", "var slug = dnDashSafeSlug(a.slug);", "Dashboard reading map should derive node links from validated slugs")
    require(errors, "dashboard.html", "var label = dnDashEscapeHtml(a.title || '');", "Dashboard reading map SVG titles should escape article titles")
    require(errors, "dashboard.html", "dnDashEscapeHtml(catLabels[c]||c)", "Dashboard pie legend labels should be escaped before insertion")
    forbid(errors, "dashboard.html", "data-href=\"/blog/' + a.slug", "Dashboard reading map should not interpolate raw article slugs")
    forbid(errors, "dashboard.html", "var label = (a.title || '').replace(/[<>&\"']/g, '');", "Dashboard reading map should use shared HTML escaping for article titles")
    forbid(errors, "dashboard.html", "<strong>' + (catLabels[c]||c)", "Dashboard pie legend should not insert raw category labels")

    if errors:
        print("[FAIL] Frontend security audit found issues:")
        for error in errors:
            print(" - " + error)
        return 1
    print("[OK] Frontend security audit passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
