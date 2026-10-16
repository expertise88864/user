/* Board-exam review pages (/exam/**): quiz/browse mode, timed year papers,
 * wrong-answer notebook and Anki export. Pages are fully rendered as static
 * HTML; this script only adds interaction. Progress lives in localStorage on
 * this device only. All dynamic text is inserted with textContent. */
(function () {
  'use strict';
  var MODE_KEY = 'dnExamMode';
  var WRONG_KEY = 'dnExamWrong';
  // Latest attempt per question: { id: [1 right / 0 wrong, epoch ms] }.
  var PROGRESS_KEY = 'dnExamProgress';
  // Chapters whose textbook chapter has been read: { chapter: epoch ms }.
  var READ_KEY = 'dnExamRead';
  var body = document.body;

  function store(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* storage disabled */ }
  }
  function load(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) { return fallback; }
  }
  function wrongSet() {
    var list = load(WRONG_KEY, []);
    return Array.isArray(list) ? list : [];
  }
  function markWrong(id, isWrong) {
    var list = wrongSet().filter(function (x) { return x !== id; });
    if (isWrong) list.push(id);
    store(WRONG_KEY, list);
  }

  function progressMap() {
    var map = load(PROGRESS_KEY, {});
    return map && typeof map === 'object' && !Array.isArray(map) ? map : {};
  }
  function recordProgress(id, ok) {
    if (!id) return;
    var map = progressMap();
    map[id] = [ok ? 1 : 0, Date.now()];
    store(PROGRESS_KEY, map);
  }

  function setMode(mode) {
    body.classList.toggle('ex-quiz', mode === 'quiz');
    document.querySelectorAll('.ex-mode').forEach(function (btn) {
      btn.setAttribute('aria-pressed', btn.getAttribute('data-mode') === mode ? 'true' : 'false');
    });
    store(MODE_KEY, mode);
  }

  function resetQuestion(card) {
    card.classList.remove('ex-done');
    card.removeAttribute('data-graded');
    card.querySelectorAll('.ex-opt').forEach(function (opt) { opt.classList.remove('ex-picked'); });
    card.querySelectorAll('input[type=radio]').forEach(function (input) { input.checked = false; input.disabled = false; });
    var result = card.querySelector('.ex-result');
    if (result) result.textContent = '';
  }

  function grade(card, silent) {
    var picked = card.querySelector('input[type=radio]:checked');
    var result = card.querySelector('.ex-result');
    // Free-credit questions (官方公告送分) earn the point whatever is chosen —
    // including nothing at all when a whole paper is handed in.
    var free = card.hasAttribute('data-free');
    if (!picked && !(free && silent)) {
      if (!silent && result) result.textContent = '請先選擇一個選項';
      return null;
    }
    var answer = card.getAttribute('data-answer') || '';
    var ok = free || answer.indexOf(picked.value) !== -1;
    card.setAttribute('data-graded', ok ? 'right' : 'wrong');
    card.classList.add('ex-done');
    if (picked) picked.closest('.ex-opt').classList.add('ex-picked');
    card.querySelectorAll('input[type=radio]').forEach(function (input) { input.disabled = true; });
    if (result) {
      // Grading a whole paper at once must not queue 50 screen-reader announcements.
      result.setAttribute('aria-live', silent ? 'off' : 'polite');
      result.textContent = free ? '此題官方公告送分，任何選項皆給分'
        : ok ? '答對了' : '答錯了，正確答案是 ' + answer.split('').join('、');
    }
    markWrong(card.getAttribute('data-qid'), !ok);
    recordProgress(card.getAttribute('data-qid'), ok);
    return ok;
  }

  function wireQuestion(card) {
    var submit = card.querySelector('.ex-submit');
    var reset = card.querySelector('.ex-reset');
    if (submit) submit.addEventListener('click', function () { grade(card, false); });
    if (reset) reset.addEventListener('click', function () { resetQuestion(card); });
    card.querySelectorAll('input[type=radio]').forEach(function (input) {
      input.addEventListener('change', function () {
        var result = card.querySelector('.ex-result');
        if (result) result.textContent = '';
      });
    });
  }

  function wireExamBar(bar) {
    var timerEl = bar.querySelector('.ex-timer');
    var scoreEl = bar.querySelector('.ex-score');
    var startedAt = null;
    var timer = null;
    function tick() {
      var s = Math.floor((Date.now() - startedAt) / 1000);
      var m = Math.floor(s / 60);
      timerEl.textContent = (m < 10 ? '0' : '') + m + ':' + (s % 60 < 10 ? '0' : '') + (s % 60);
    }
    function start() {
      setMode('quiz');
      document.querySelectorAll('.ex-q').forEach(resetQuestion);
      scoreEl.textContent = '';
      startedAt = Date.now();
      if (timer) clearInterval(timer);
      timer = setInterval(tick, 1000);
      tick();
    }
    var startBtn = bar.querySelector('.ex-start');
    if (startBtn) startBtn.addEventListener('click', start);
    bar.querySelector('.ex-finish').addEventListener('click', function () {
      if (timer) { clearInterval(timer); timer = null; }
      setMode('quiz');
      var cards = document.querySelectorAll('.ex-q');
      var right = 0;
      var blank = 0;
      cards.forEach(function (card) {
        if (card.classList.contains('ex-done')) {
          var graded = card.getAttribute('data-graded');
          if (graded === 'right') right += 1;
          else if (graded === 'blank') blank += 1;
          return;
        }
        var ok = grade(card, true);
        if (ok === null) {
          // Finalize unanswered questions like answered ones: lock the options so a
          // later pick cannot sit there while every hand-in keeps counting it blank.
          blank += 1;
          card.setAttribute('data-graded', 'blank');
          card.classList.add('ex-done');
          card.querySelectorAll('input[type=radio]').forEach(function (input) { input.disabled = true; });
          var result = card.querySelector('.ex-result');
          if (result) {
            result.setAttribute('aria-live', 'off');
            result.textContent = '未作答，正確答案是 ' + (card.getAttribute('data-answer') || '').split('').join('、');
          }
        } else if (ok) {
          right += 1;
        }
      });
      scoreEl.textContent = '得分 ' + right + ' / ' + cards.length + (blank ? '（未作答 ' + blank + ' 題）' : '');
    });
    return { start: start };
  }

  // ---------------------------------------------------------- review page
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // Explanation text marks organism names as [i]Genus species[/i]; render them in italics.
  function richText(tag, cls, text) {
    var node = el(tag, cls);
    String(text).split(/(\[i\].+?\[\/i\])/).forEach(function (part) {
      if (/^\[i\].+\[\/i\]$/.test(part)) node.appendChild(el('em', null, part.slice(3, -4)));
      else if (part) node.appendChild(document.createTextNode(part));
    });
    return node;
  }

  function renderCard(q, removable) {
    var card = el('article', 'ex-q');
    card.id = 'q-' + q.id;
    card.setAttribute('data-qid', q.id);
    card.setAttribute('data-answer', q.answer.join(''));
    if (q.free) card.setAttribute('data-free', '');
    var head = el('header', 'ex-q-head');
    var link = el('a', null, q.year + ' 年第 ' + q.number + ' 題');
    link.href = '/exam/year-' + q.year + '#q-' + q.id;
    var no = el('span', 'ex-q-no');
    no.appendChild(link);
    head.appendChild(no);
    var chips = el('span', 'ex-chips');
    q.fitz.forEach(function (c) {
      var chip = el('a', 'ex-chip', 'Ch.' + c);
      chip.href = '/exam/fitz-' + c + '#q-' + q.id;
      chips.appendChild(chip);
    });
    head.appendChild(chips);
    card.appendChild(head);
    card.appendChild(el('p', 'ex-stem', q.stem));
    if (q.statements) {
      var ul = el('ul', 'ex-stmts');
      q.statements.forEach(function (s) {
        var li = el('li');
        li.appendChild(el('span', 'ex-stmt-id', s.id));
        li.appendChild(document.createTextNode(s.text));
        ul.appendChild(li);
      });
      card.appendChild(ul);
    }
    var fs = el('fieldset', 'ex-opts');
    fs.appendChild(el('legend', 'ex-sr', '選項'));
    Object.keys(q.options).forEach(function (k) {
      var label = el('label', 'ex-opt');
      label.setAttribute('data-key', k);
      if (q.answer.indexOf(k) !== -1) label.setAttribute('data-correct', '');
      var input = el('input');
      input.type = 'radio';
      input.name = 'ans-' + q.id;
      input.value = k;
      var keyEl = el('span', 'ex-opt-key', k);
      var textEl = el('span', 'ex-opt-text', q.options[k]);
      keyEl.id = 'o-' + q.id + '-' + k;
      textEl.id = 't-' + q.id + '-' + k;
      input.setAttribute('aria-labelledby', keyEl.id + ' ' + textEl.id);
      label.appendChild(input);
      label.appendChild(keyEl);
      label.appendChild(textEl);
      fs.appendChild(label);
    });
    card.appendChild(fs);
    var actions = el('div', 'ex-actions');
    actions.appendChild(el('button', 'ex-submit', '送出答案'));
    actions.appendChild(el('button', 'ex-reset', '重新作答'));
    if (removable) {
      var remove = el('button', 'ex-remove', '移出錯題本');
      remove.addEventListener('click', function () {
        markWrong(q.id, false);
        // Re-render so the 「共 N 題錯題」 count and the empty state stay current.
        var list = document.getElementById('ex-review-list');
        if (list) renderReview(list); else card.remove();
      });
      actions.appendChild(remove);
    }
    actions.querySelectorAll('button').forEach(function (b) { b.type = 'button'; });
    actions.appendChild(el('span', 'ex-result'));
    card.appendChild(actions);
    var reveal = el('div', 'ex-reveal');
    var ans = el('p', 'ex-answer', '官方答案：');
    ans.appendChild(el('strong', null, q.answer.join('、')));
    if (q.note) ans.appendChild(el('span', 'ex-flag', q.note));
    reveal.appendChild(ans);
    if (q.expl) {
      reveal.appendChild(richText('p', 'ex-summary', q.expl.summary));
      var items = el('ul', 'ex-items');
      q.expl.items.forEach(function (it) {
        var li = el('li', it.ok ? 'ex-ok' : 'ex-no');
        li.appendChild(el('span', 'ex-item-key', it.key));
        li.appendChild(el('span', 'ex-item-label', it.label));
        li.appendChild(richText('span', 'ex-item-text', it.text));
        li.appendChild(el('span', 'ex-item-refs', it.refs.join('；')));
        items.appendChild(li);
      });
      reveal.appendChild(items);
      (q.expl.flags || []).forEach(function (flag) {
        var note = richText('p', 'ex-flag-note', flag);
        note.insertBefore(el('span', 'ex-flag-tag', '附註'), note.firstChild);
        reveal.appendChild(note);
      });
      if (q.expl.dispute) reveal.appendChild(disputeBlock(q.expl.dispute));
    } else {
      reveal.appendChild(el('p', 'ex-pending', '詳解尚未整理。'));
    }
    card.appendChild(reveal);
    wireQuestion(card);
    return card;
  }

  var DISPUTE_KINDS = {
    old: '舊版觀念', missing: '課本未提及', conflict: '說法矛盾',
    ambiguous: '選項模稜兩可', typo: '題目誤植', figure: '缺圖或缺表'
  };
  // '考試答案：…' keeps its label bold, as on the static pages.
  function labelled(text) {
    var p = el('p');
    var i = String(text).indexOf('：');
    if (i > 0 && i <= 6) {
      p.appendChild(el('strong', null, text.slice(0, i)));
      p.appendChild(document.createTextNode('：'));
      p.appendChild(richText('span', null, text.slice(i + 1)));
    } else {
      p.appendChild(richText('span', null, text));
    }
    return p;
  }
  function disputeBlock(d) {
    var box = el('div', 'ex-dispute');
    box.appendChild(el('p', 'ex-dispute-h', '⚠ 疑義題 · ' + (DISPUTE_KINDS[d.kind] || '疑義')));
    box.appendChild(labelled(d.exam));
    if (d.current) box.appendChild(labelled(d.current));
    if (d.sources && d.sources.length) {
      var ul = el('ul', 'ex-sources');
      d.sources.forEach(function (src) {
        var li = el('li');
        var a = richText('a', null, src.title);
        a.href = src.url;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        li.appendChild(a);
        li.appendChild(document.createTextNode((src.year ? '（' + src.year + '）' : '') + (src.pmid ? ' PMID ' + src.pmid : '')));
        ul.appendChild(li);
      });
      box.appendChild(ul);
    }
    return box;
  }

  var dataPromise = null;
  function examData() {
    if (!dataPromise) {
      var main = document.querySelector('[data-exam-data]');
      var url = (main && main.getAttribute('data-exam-data')) || '/exam/exam-data.json';
      dataPromise = fetch(url, { credentials: 'same-origin' })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
    }
    return dataPromise;
  }

  function renderReview(list) {
    examData().then(function (data) {
      var wrong = wrongSet();
      var byId = {};
      data.questions.forEach(function (q) { byId[q.id] = q; });
      while (list.firstChild) list.removeChild(list.firstChild);
      var rows = wrong.map(function (id) { return byId[id]; }).filter(Boolean);
      if (!rows.length) {
        list.appendChild(el('p', 'ex-pending', '目前沒有錯題。到章節頁或年度考古卷切換「作答模式」作答，答錯的題目會出現在這裡。'));
        return;
      }
      list.appendChild(el('p', 'ex-meta', '共 ' + rows.length + ' 題錯題'));
      rows.forEach(function (q) { list.appendChild(renderCard(q, true)); });
    }).catch(function () {
      list.appendChild(el('p', 'ex-pending', '題庫載入失敗，請重新整理頁面。'));
    });
  }

  function csvCell(text) {
    return '"' + String(text).replace(/"/g, '""') + '"';
  }
  function htmlText(text) {
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\[i\](.+?)\[\/i\]/g, '<i>$1</i>').replace(/\n/g, '<br>');
  }
  function ankiRows(questions) {
    return questions.map(function (q) {
      var front = htmlText(q.stem) + '<br>';
      (q.statements || []).forEach(function (s) { front += htmlText(s.id + ' ' + s.text) + '<br>'; });
      Object.keys(q.options).forEach(function (k) { front += htmlText('(' + k + ') ' + q.options[k]) + '<br>'; });
      front += '<small>' + q.year + ' 年第 ' + q.number + ' 題</small>';
      var back = '答案：' + q.answer.join('、') + (q.note ? htmlText('（' + q.note + '）') : '');
      if (q.expl) {
        back += '<br>' + htmlText(q.expl.summary);
        q.expl.items.forEach(function (it) {
          back += '<br>' + htmlText(it.key + ' ' + it.label + '：' + it.text + '（' + it.refs.join('；') + '）');
        });
        (q.expl.flags || []).forEach(function (flag) { back += '<br>' + htmlText('附註：' + flag); });
        var d = q.expl.dispute;
        if (d) {
          back += '<br>' + htmlText('⚠ 疑義題（' + (DISPUTE_KINDS[d.kind] || '疑義') + '）' + d.exam);
          if (d.current) back += '<br>' + htmlText(d.current);
          (d.sources || []).forEach(function (src) {
            back += '<br>' + htmlText(src.title + (src.year ? '（' + src.year + '）' : '') + ' ' + src.url);
          });
        }
      }
      return csvCell(front) + ',' + csvCell(back);
    }).join('\n');
  }
  function download(name, text) {
    var blob = new Blob(['﻿' + text], { type: 'text/csv;charset=utf-8' });
    var a = el('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
  }

  function shuffle(list) {
    for (var i = list.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = list[i]; list[i] = list[j]; list[j] = tmp;
    }
    return list;
  }

  function initPractice(form, barApi) {
    var list = document.getElementById('ex-practice-list');
    var note = form.querySelector('.ex-build-note');
    var bar = document.querySelector('[data-exam-bar]');
    function setAll(checked) {
      form.querySelectorAll('input[name=ex-year]').forEach(function (box) { box.checked = checked; });
    }
    form.querySelector('.ex-years-all').addEventListener('click', function () { setAll(true); });
    form.querySelector('.ex-years-none').addEventListener('click', function () { setAll(false); });
    form.querySelector('.ex-build').addEventListener('click', function () {
      var years = [];
      form.querySelectorAll('input[name=ex-year]:checked').forEach(function (box) { years.push(Number(box.value)); });
      if (!years.length) { note.textContent = '請至少選一個年份'; return; }
      var count = Number(form.querySelector('select[name=ex-count]').value);
      var order = form.querySelector('input[name=ex-order]:checked').value;
      note.textContent = '題目載入中…';
      examData().then(function (data) {
        var pool = data.questions.filter(function (q) { return years.indexOf(q.year) !== -1; });
        if (order === 'random') shuffle(pool);
        if (count > 0) pool = pool.slice(0, count);
        while (list.firstChild) list.removeChild(list.firstChild);
        pool.forEach(function (q, i) {
          var card = renderCard(q, false);
          var no = card.querySelector('.ex-q-no');
          if (no) no.insertBefore(document.createTextNode((i + 1) + '. '), no.firstChild);
          list.appendChild(card);
        });
        note.textContent = '共 ' + pool.length + ' 題，計時開始';
        if (bar) bar.hidden = false;
        barApi.start();
        list.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }).catch(function () {
        note.textContent = '題庫載入失敗，請重新整理頁面。';
      });
    });
  }

  // Hub: per-chapter progress from this browser's storage (static cells show —).
  function initProgress(tables) {
    var map = progressMap();
    var read = load(READ_KEY, {});
    if (!read || typeof read !== 'object' || Array.isArray(read)) read = {};
    var answered = 0, right = 0, readCount = 0;
    Object.keys(map).forEach(function (id) {
      if (Array.isArray(map[id])) { answered += 1; if (map[id][0]) right += 1; }
    });
    function day(ms) {
      var d = new Date(ms);
      return d.getFullYear() + '/' + (d.getMonth() + 1) + '/' + d.getDate();
    }
    document.querySelectorAll('.ex-progress tbody tr').forEach(function (row) {
      var ids = (row.getAttribute('data-qids') || '').split(',').filter(Boolean);
      var done = 0, ok = 0, last = 0;
      ids.forEach(function (id) {
        var rec = map[id];
        if (!Array.isArray(rec)) return;
        done += 1;
        if (rec[0]) ok += 1;
        if (rec[1] > last) last = rec[1];
      });
      var acc = done ? Math.round(100 * ok / done) : null;
      row.setAttribute('data-done', String(done));
      row.setAttribute('data-acc', acc === null ? '' : String(acc));
      row.querySelector('.ex-pg-done').textContent = ids.length ? done + ' / ' + ids.length : '—';
      var accCell = row.querySelector('.ex-pg-acc');
      accCell.textContent = acc === null ? '—' : acc + '%';
      accCell.classList.toggle('ex-pg-low', acc !== null && acc < 60);
      row.querySelector('.ex-pg-date').textContent = last ? day(last) : '—';
      var box = row.querySelector('.ex-pg-read');
      var ch = row.getAttribute('data-ch');
      box.disabled = false;
      box.checked = Object.prototype.hasOwnProperty.call(read, ch);
      if (box.checked) readCount += 1;
      box.addEventListener('change', function () {
        var current = load(READ_KEY, {});
        if (!current || typeof current !== 'object' || Array.isArray(current)) current = {};
        if (box.checked) current[ch] = Date.now(); else delete current[ch];
        store(READ_KEY, current);
        summary();
      });
    });
    var total = document.querySelector('[data-exam-total]');
    var totalCount = total ? Number(total.getAttribute('data-exam-total')) : 0;
    function summary() {
      var el2 = document.getElementById('ex-progress-summary');
      if (!el2) return;
      var current = load(READ_KEY, {});
      var n = current && typeof current === 'object' ? Object.keys(current).length : 0;
      el2.textContent = '已作答 ' + answered + (totalCount ? ' / ' + totalCount : '') + ' 題' +
        (answered ? '，正確率 ' + Math.round(100 * right / answered) + '%' : '') + '，課本已讀完 ' + n + ' 章';
    }
    summary();
    var sort = document.querySelector('.ex-progress-sort');
    if (sort) {
      sort.disabled = false;
      sort.addEventListener('change', function () {
        tables.forEach(function (table) {
          var tbody = table.querySelector('tbody');
          var rows = Array.prototype.slice.call(tbody.rows);
          rows.sort(function (a, b) {
            var oa = Number(a.getAttribute('data-order')), ob = Number(b.getAttribute('data-order'));
            if (sort.value === 'todo') {
              var da = Number(a.getAttribute('data-done')), db = Number(b.getAttribute('data-done'));
              return (da === 0) === (db === 0) ? oa - ob : (da === 0 ? -1 : 1);
            }
            if (sort.value === 'low') {
              var aa = a.getAttribute('data-acc'), ab = b.getAttribute('data-acc');
              if (aa === '' && ab === '') return oa - ob;
              if (aa === '') return 1;
              if (ab === '') return -1;
              return Number(aa) - Number(ab) || oa - ob;
            }
            return oa - ob;
          });
          rows.forEach(function (row) { tbody.appendChild(row); });
        });
      });
    }
  }

  function init() {
    document.querySelectorAll('.ex-mode').forEach(function (btn) {
      btn.addEventListener('click', function () { setMode(btn.getAttribute('data-mode')); });
    });
    setMode(load(MODE_KEY, 'browse') === 'quiz' ? 'quiz' : 'browse');
    document.querySelectorAll('.ex-q').forEach(wireQuestion);
    var bar = document.querySelector('[data-exam-bar]');
    var barApi = bar ? wireExamBar(bar) : null;
    var form = document.querySelector('[data-practice-form]');
    if (form && barApi) initPractice(form, barApi);
    var list = document.getElementById('ex-review-list');
    if (list) renderReview(list);
    var tables = Array.prototype.slice.call(document.querySelectorAll('.ex-progress'));
    if (tables.length) initProgress(tables);
    document.querySelectorAll('.ex-anki').forEach(function (btn) {
      btn.addEventListener('click', function () {
        examData().then(function (data) {
          var scope = btn.getAttribute('data-scope');
          var wrong = wrongSet();
          var rows = scope === 'wrong'
            ? data.questions.filter(function (q) { return wrong.indexOf(q.id) !== -1; })
            : data.questions;
          download(scope === 'wrong' ? 'derm-board-wrong.csv' : 'derm-board-all.csv', ankiRows(rows));
        });
      });
    });
    var clear = document.querySelector('.ex-clear-wrong');
    if (clear) {
      clear.addEventListener('click', function () {
        store(WRONG_KEY, []);
        if (list) renderReview(list);
      });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
