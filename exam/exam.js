/* Board-exam review pages (/exam/**): quiz/browse mode, timed year papers,
 * wrong-answer notebook and Anki export. Pages are fully rendered as static
 * HTML; this script only adds interaction. Progress lives in localStorage on
 * this device only. All dynamic text is inserted with textContent. */
(function () {
  'use strict';
  var MODE_KEY = 'dnExamMode';
  var WRONG_KEY = 'dnExamWrong';
  // Latest attempt per question: { id: [1 right / 0 wrong, epoch ms, picked key] }.
  // The picked key ('' = handed in blank on a free-credit question) restores
  // the answer when the page is opened again; older records have no third item.
  var PROGRESS_KEY = 'dnExamProgress';
  // The same records kept per chapter page, for answers given on that page
  // only: { 'fitz-53': { id: [ok, epoch ms, key] } }. The hub's chapter table
  // and a chapter page's restored answers read these, so answering a question
  // shared by several chapters (or on a year paper) leaves the other chapters
  // untouched. Answers from before this key existed have no page and are not
  // assigned to any chapter.
  var CHAPTER_PROGRESS_KEY = 'dnExamChapterProgress';
  // Chapters whose textbook chapter has been read: { chapter: epoch ms }.
  var READ_KEY = 'dnExamRead';
  // Last reading place per chapter page: { 'fitz-53': { id, dy, t } } — id of the
  // note section, #qs-h or question card at the top of the window, dy = how
  // many px of it had been scrolled past.
  var POS_KEY = 'dnExamPos';
  // Timed papers not yet handed in: { 'year-105' | 'practice': { start, seen,
  // ids (practice only), sel: { id: key picked, not submitted }, done: { id: key submitted } } }.
  var PAPER_KEY = 'dnExamPaper';
  var body = document.body;

  function store(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch (e) { return false; /* storage disabled */ }
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

  // 'chapter' | 'year' | 'book' | 'practice' | 'review' | 'hub' (set by _gen_exam.py).
  function pageKind() {
    var main = document.querySelector('[data-exam-page]');
    return main ? main.getAttribute('data-exam-page') : '';
  }
  // Storage key of this page: 'fitz-53', 'year-105', 'kantor', 'practice'.
  function pageSlug() {
    var slug = window.location.pathname.replace(/\/+$/, '').split('/').pop() || '';
    return slug.replace(/\.html$/, '');
  }

  function isMap(value) {
    return !!value && typeof value === 'object' && !Array.isArray(value);
  }
  function progressMap() {
    var map = load(PROGRESS_KEY, {});
    return isMap(map) ? map : {};
  }
  function own(map, key) {
    return Object.prototype.hasOwnProperty.call(map, key);
  }
  // Storage key of this chapter page ('fitz-53'), or '' on any other page.
  function chapterSlug() {
    if (pageKind() !== 'chapter') return '';
    var slug = pageSlug();
    return /^fitz-\d+$/.test(slug) ? slug : '';
  }
  function chapterProgressAll() {
    var all = load(CHAPTER_PROGRESS_KEY, {});
    return isMap(all) ? all : {};
  }
  function chapterProgress(slug) {
    var all = chapterProgressAll();
    return own(all, slug) && isMap(all[slug]) ? all[slug] : {};
  }
  // Replace one chapter's records (null removes them), keeping the others.
  function saveChapterProgress(slug, map) {
    var all = chapterProgressAll();
    if (map) all[slug] = map; else delete all[slug];
    return store(CHAPTER_PROGRESS_KEY, all);
  }
  function recordProgress(id, ok, key) {
    if (!id) return;
    var rec = [ok ? 1 : 0, Date.now(), key || ''];
    var map = progressMap();
    map[id] = rec;
    store(PROGRESS_KEY, map);
    // A chapter page also keeps its own copy (same time stamp, so clearing the
    // chapter can tell whether the overall record is still this answer).
    var slug = chapterSlug();
    if (slug) {
      var mine = chapterProgress(slug);
      mine[id] = rec.slice();
      saveChapterProgress(slug, mine);
    }
  }

  // ---------------------------------------------------------- timed papers
  // The paper being worked on in this page (year paper after 開始計時作答, or
  // the generated practice paper), mirrored to storage so a reload resumes it.
  // Each attempt has an id and a revision (rev, raised on every save), so a
  // page open in two tabs never writes a stale copy over a paper the other
  // tab handed in, replaced or saved newer answers to.
  var paper = null;
  var paperKey = null;
  // False when the paper could not be written when it began (storage off or
  // full): it then lives in this page only and is not compared with storage.
  var paperSynced = true;
  var paperBar = null;  // { start, stop } of the page's timer bar
  function paperMap() {
    var map = load(PAPER_KEY, {});
    return isMap(map) ? map : {};
  }
  function normPaper(p) {
    if (!isMap(p) || typeof p.start !== 'number') return null;
    if (!isMap(p.sel)) p.sel = {};
    if (!isMap(p.done)) p.done = {};
    // Saved before attempts had ids: every tab derives the same one.
    if (typeof p.id !== 'string') p.id = 'start-' + p.start;
    if (typeof p.rev !== 'number') p.rev = 0;
    return p;
  }
  function loadPaper(key) {
    return normPaper(paperMap()[key]);
  }
  // Save the paper; edit(p) applies this page's change to the latest saved
  // copy, which replaces this page's copy when another tab saved after it.
  function savePaper(edit) {
    if (!paperKey || !paper) return;
    if (!paperSynced) { if (edit) edit(paper); return; }
    var map = paperMap();
    var cur = normPaper(map[paperKey]);
    if (!cur || cur.id !== paper.id) { lostPaper(); return; }
    var newer = cur.rev > paper.rev;
    var next = newer ? cur : paper;
    if (edit) edit(next);
    next.rev = Math.max(cur.rev, paper.rev) + 1;
    next.seen = Date.now();
    map[paperKey] = next;
    store(PAPER_KEY, map);
    if (newer) adoptPaper(next);
    else paper = next;
  }
  function beginPaper(key, data) {
    data.id = Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
    data.rev = 1;
    data.seen = Date.now();
    paperKey = key;
    paper = data;
    var map = paperMap();
    map[key] = data;
    paperSynced = store(PAPER_KEY, map);
  }
  // Hand-in: remove this attempt only, never a newer one begun in another tab.
  function endPaper() {
    var id = paper && paper.id;
    paper = null;
    if (!paperKey || !paperSynced) return;
    var map = paperMap();
    var cur = normPaper(map[paperKey]);
    if (!cur || cur.id !== id) return;
    delete map[paperKey];
    store(PAPER_KEY, map);
  }
  // Another tab handed this paper in or began a new one: stop timing and
  // saving here, so the old copy cannot bring the record back.
  function lostPaper() {
    paper = null;
    if (paperBar) paperBar.stop('這份試卷已在其他分頁交卷或重新開始，本頁不再計時或保存；請重新整理頁面。');
  }
  // Take over the copy another tab saved: its answers and its start time.
  function adoptPaper(next) {
    var old = paper;
    paper = next;
    if (JSON.stringify([old.sel, old.done]) !== JSON.stringify([next.sel, next.done])) {
      var cards = pageCards();
      cards.forEach(resetQuestion);
      restoreFromPaper(cards);
      if (answerBar) setOnlyTodo(answerBar.only.getAttribute('aria-pressed') === 'true');
      updateAnswerBar();
    }
    if (old.start !== next.start && paperBar) paperBar.start(next.start);
  }
  function syncPaperFromStorage(event) {
    if (!paper || !paperSynced || (event.key !== PAPER_KEY && event.key !== null)) return;
    var cur = loadPaper(paperKey);
    if (!cur || cur.id !== paper.id) lostPaper();
    else if (cur.rev > paper.rev) adoptPaper(cur);
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
    card.classList.remove('ex-hide');
    card.removeAttribute('data-graded');
    card.querySelectorAll('.ex-opt').forEach(function (opt) { opt.classList.remove('ex-picked'); });
    card.querySelectorAll('input[type=radio]').forEach(function (input) { input.checked = false; input.disabled = false; });
    var result = card.querySelector('.ex-result');
    if (result) result.textContent = '';
  }

  function answerLetters(card) {
    return (card.getAttribute('data-answer') || '').split('').join('、');
  }
  function verdict(card, ok) {
    if (card.hasAttribute('data-free')) return '此題官方公告送分，任何選項皆給分';
    return ok ? '答對了' : '答錯了，正確答案是 ' + answerLetters(card);
  }
  // Lock a graded card and show its result (the explanation opens through CSS).
  function showGraded(card, ok, text, silent) {
    var picked = card.querySelector('input[type=radio]:checked');
    card.setAttribute('data-graded', ok ? 'right' : 'wrong');
    card.classList.add('ex-done');
    if (picked) picked.closest('.ex-opt').classList.add('ex-picked');
    card.querySelectorAll('input[type=radio]').forEach(function (input) { input.disabled = true; });
    var result = card.querySelector('.ex-result');
    if (result) {
      // Grading a whole paper at once must not queue 50 screen-reader announcements.
      result.setAttribute('aria-live', silent ? 'off' : 'polite');
      result.textContent = text;
    }
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
    showGraded(card, ok, verdict(card, ok), silent);
    markWrong(card.getAttribute('data-qid'), !ok);
    recordProgress(card.getAttribute('data-qid'), ok, picked ? picked.value : '');
    return ok;
  }

  function radioFor(card, key) {
    var found = null;
    if (typeof key !== 'string' || !key) return null;
    card.querySelectorAll('input[type=radio]').forEach(function (input) {
      if (input.value === key) found = input;
    });
    return found;
  }

  // Show an answer given earlier without recording it again: key is the
  // option picked then (may be missing in records made before keys were
  // kept), rec the stored [ok, time, key] record. Returns the verdict, or
  // null when there is nothing to restore.
  function restoreCard(card, key, rec) {
    var free = card.hasAttribute('data-free');
    var input = radioFor(card, key);
    if (!input && !free && !rec) return null;
    if (input) input.checked = true;
    var ok = free || (input ? (card.getAttribute('data-answer') || '').indexOf(key) !== -1 : !!rec[0]);
    var text = input || free ? verdict(card, ok)
      : (ok ? '上次答對了' : '上次答錯了，正確答案是 ' + answerLetters(card)) + '（舊紀錄未保存所選選項）';
    if (rec && rec[1]) text += '（' + day(rec[1]) + ' 作答）';
    showGraded(card, ok, text, true);
    return ok;
  }

  // Verdict of a stored [ok, time, key] record under the current official
  // answer (the same rule restoreCard shows).
  function recordVerdict(card, rec) {
    if (card.hasAttribute('data-free')) return true;
    var input = radioFor(card, rec[2]);
    return input ? (card.getAttribute('data-answer') || '').indexOf(rec[2]) !== -1 : !!rec[0];
  }
  // A record whose verdict no longer matches the official answer (the key was
  // corrected since) is fixed in place, so the hub statistics agree with what
  // the page shows. syncWrong: the wrong notebook follows the corrected
  // overall record, as it always has. Returns whether map changed.
  function correctRecords(cards, map, syncWrong) {
    var changed = false;
    cards.forEach(function (card) {
      var id = card.getAttribute('data-qid');
      var rec = own(map, id) ? map[id] : null;
      if (!Array.isArray(rec)) return;
      var ok = recordVerdict(card, rec);
      if ((ok ? 1 : 0) !== (rec[0] ? 1 : 0)) {
        rec[0] = ok ? 1 : 0;
        if (syncWrong) markWrong(id, !ok);
        changed = true;
      }
    });
    return changed;
  }
  // Static question pages reopen with each question's latest answer: a
  // chapter page with the answers given on that chapter page, any other page
  // with the latest answer given anywhere.
  function restoreFromProgress(cards) {
    var overall = progressMap();
    if (correctRecords(cards, overall, true)) store(PROGRESS_KEY, overall);
    var slug = chapterSlug();
    var map = overall;
    if (slug) {
      map = chapterProgress(slug);
      if (correctRecords(cards, map, false)) saveChapterProgress(slug, map);
    }
    cards.forEach(function (card) {
      var id = card.getAttribute('data-qid');
      var rec = own(map, id) ? map[id] : null;
      if (Array.isArray(rec)) restoreCard(card, rec[2], rec);
    });
  }

  // A resumed paper: answers submitted during it come back graded, picks not
  // yet submitted come back selected, everything else stays blank.
  function restoreFromPaper(cards) {
    cards.forEach(function (card) {
      var id = card.getAttribute('data-qid');
      if (Object.prototype.hasOwnProperty.call(paper.done, id) &&
          restoreCard(card, paper.done[id], null) !== null) return;
      var input = radioFor(card, paper.sel[id]);
      if (input) input.checked = true;
    });
  }

  function wireQuestion(card) {
    var submit = card.querySelector('.ex-submit');
    var reset = card.querySelector('.ex-reset');
    var id = card.getAttribute('data-qid');
    if (submit) submit.addEventListener('click', function () {
      if (grade(card, false) === null) return;
      if (paper) {
        var picked = card.querySelector('input[type=radio]:checked');
        var key = picked ? picked.value : '';
        savePaper(function (p) { p.done[id] = key; });
      }
      updateAnswerBar();
    });
    if (reset) reset.addEventListener('click', function () {
      resetQuestion(card);
      if (paper) {
        savePaper(function (p) {
          delete p.done[id];
          delete p.sel[id];
        });
      }
      updateAnswerBar();
    });
    card.querySelectorAll('input[type=radio]').forEach(function (input) {
      input.addEventListener('change', function () {
        var result = card.querySelector('.ex-result');
        if (result) result.textContent = '';
        if (paper) {
          savePaper(function (p) { p.sel[id] = input.value; });
        }
      });
    });
  }

  // ---------------------------------------------------------- answer summary
  // 「已作答 x／y 題」 bar above a page's questions (shown in quiz mode only).
  var answerBar = null;
  function pageCards() {
    var list = document.getElementById('ex-practice-list');
    return Array.prototype.slice.call((list || document).querySelectorAll('.ex-q'));
  }
  function isAnswered(card) {
    var graded = card.getAttribute('data-graded');
    return graded === 'right' || graded === 'wrong';
  }
  function updateAnswerBar() {
    if (!answerBar) return;
    var cards = pageCards();
    var done = cards.filter(isAnswered).length;
    var todo = cards.length - done;
    answerBar.count.textContent = '已作答 ' + done + '／' + cards.length + ' 題，未作答 ' + todo + ' 題';
    answerBar.jump.disabled = todo === 0;
    if (answerBar.clear) answerBar.clear.disabled = done === 0;
  }
  function setOnlyTodo(on) {
    if (!answerBar) return;
    answerBar.only.setAttribute('aria-pressed', on ? 'true' : 'false');
    // Cards answered while the filter is on stay visible until it is toggled,
    // so a result and its explanation never vanish on submit.
    pageCards().forEach(function (card) { card.classList.toggle('ex-hide', on && isAnswered(card)); });
  }
  // 清除本章作答: drop this chapter's records, and an overall record only
  // while it is still the answer given here (same time and pick) — one given
  // later on another page stays.
  function clearChapter(slug) {
    var mine = chapterProgress(slug);
    var overall = progressMap();
    var changed = false;
    Object.keys(mine).forEach(function (id) {
      var rec = mine[id];
      var cur = own(overall, id) ? overall[id] : null;
      if (Array.isArray(rec) && Array.isArray(cur) && cur[1] === rec[1] && cur[2] === rec[2]) {
        delete overall[id];
        changed = true;
      }
    });
    if (changed) store(PROGRESS_KEY, overall);
    saveChapterProgress(slug, null);
  }
  function buildAnswerBar(clearLabel, scopeLabel) {
    var bar = el('div', 'ex-answer-bar');
    bar.setAttribute('role', 'group');
    bar.setAttribute('aria-label', '作答紀錄');
    var count = el('span', 'ex-answer-count');
    var only = el('button', 'ex-only-todo', '只看未作答');
    only.setAttribute('aria-pressed', 'false');
    var jump = el('button', 'ex-jump-todo', '跳到第一個未作答');
    bar.appendChild(count);
    bar.appendChild(only);
    bar.appendChild(jump);
    var clear = null;
    if (clearLabel) {
      clear = el('button', 'ex-clear-answers', clearLabel);
      bar.appendChild(clear);
    }
    bar.querySelectorAll('button').forEach(function (b) { b.type = 'button'; });
    answerBar = { node: bar, count: count, only: only, jump: jump, clear: clear };
    only.addEventListener('click', function () {
      setOnlyTodo(only.getAttribute('aria-pressed') !== 'true');
    });
    jump.addEventListener('click', function () {
      var target = pageCards().filter(function (card) { return !isAnswered(card); })[0];
      if (!target) return;
      target.scrollIntoView({ block: 'start' });
      var radio = target.querySelector('input[type=radio]:not(:disabled)');
      if (radio) {
        try { radio.focus({ preventScroll: true }); } catch (e) { radio.focus(); }
      }
    });
    if (clear) {
      clear.addEventListener('click', function () {
        var cards = pageCards();
        var done = cards.filter(isAnswered).length;
        if (!done) return;
        var slug = chapterSlug();
        if (slug) {
          if (!window.confirm('清除本章已作答的 ' + done + ' 題紀錄並重新作答？\n' +
            '本章在專科考試首頁的「已做」、正確率與最後作答日期會歸零。這些題目若最近一次是在本章作答，' +
            '也會從首頁全站「已作答／正確率」移除；之後在其他章節或考卷的作答保留。\n' +
            '其他章節的統計不受影響；錯題本保留，重新答對時才移出。')) return;
          clearChapter(slug);
          cards.forEach(resetQuestion);
        } else {
          if (!window.confirm('清除' + scopeLabel + '已作答的 ' + done + ' 題紀錄並重新作答？\n' +
            '專科考試首頁全站的「已作答／正確率」會一併重算（各章節的統計只計算在章節頁作答的題目，不受影響）；' +
            '錯題本保留，重新答對時才移出。')) return;
          var map = progressMap();
          cards.forEach(function (card) {
            delete map[card.getAttribute('data-qid')];
            resetQuestion(card);
          });
          store(PROGRESS_KEY, map);
        }
        if (paper) {
          savePaper(function (p) {
            p.done = {};
            p.sel = {};
          });
        }
        setOnlyTodo(false);
        updateAnswerBar();
      });
    }
    return bar;
  }

  function wireExamBar(bar) {
    var timerEl = bar.querySelector('.ex-timer');
    var scoreEl = bar.querySelector('.ex-score');
    var startedAt = null;
    var timer = null;
    var lastSeen = 0;
    function tick() {
      var s = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
      var m = Math.floor(s / 60);
      timerEl.textContent = (m < 10 ? '0' : '') + m + ':' + (s % 60 < 10 ? '0' : '') + (s % 60);
      // Note the time now and then, so a paper resumed later does not count
      // the hours the page was closed.
      if (paper && Date.now() - lastSeen > 10000) {
        lastSeen = Date.now();
        savePaper();
      }
    }
    // resumeAt: continue a paper that started at that time (cards keep their
    // restored state); without it, start afresh with every card blank.
    function start(resumeAt) {
      setMode('quiz');
      if (!resumeAt) document.querySelectorAll('.ex-q').forEach(resetQuestion);
      scoreEl.textContent = '';
      startedAt = resumeAt || Date.now();
      if (timer) clearInterval(timer);
      timer = setInterval(tick, 1000);
      tick();
      return startedAt;
    }
    function stop(message) {
      if (timer) { clearInterval(timer); timer = null; }
      scoreEl.textContent = message || '';
    }
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'hidden' && paper) savePaper();
    });
    // A page kept in the back-forward cache comes back without init, so the
    // time spent on other pages is taken off here instead: pause on leaving,
    // and on return continue from the latest saved copy of the paper.
    var leftAt = 0;
    window.addEventListener('pagehide', function () {
      if (!paper || !timer) return;
      savePaper();
      if (timer) { clearInterval(timer); timer = null; }
      leftAt = Date.now();
    });
    window.addEventListener('pageshow', function (event) {
      if (!event.persisted || !leftAt) return;
      var from = leftAt;
      leftAt = 0;
      if (!paper) return;
      if (paperSynced) {
        var cur = loadPaper(paperKey);
        if (!cur || cur.id !== paper.id) { lostPaper(); return; }
        if (typeof cur.seen === 'number') from = cur.seen;
        if (cur.rev > paper.rev) adoptPaper(cur);
      }
      var away = Math.max(0, Date.now() - from);
      savePaper(function (p) { p.start += away; });
      if (paper) start(paper.start);
    });
    var startBtn = bar.querySelector('.ex-start');
    if (startBtn) startBtn.addEventListener('click', function () {
      var at = start();
      if (pageSlug()) beginPaper(pageSlug(), { start: at, sel: {}, done: {} });
      setOnlyTodo(false);
      updateAnswerBar();
    });
    bar.querySelector('.ex-finish').addEventListener('click', function () {
      if (timer) { clearInterval(timer); timer = null; }
      if (paper) endPaper();
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
      updateAnswerBar();
    });
    paperBar = { start: start, stop: stop };
    return paperBar;
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
    var summary = buildAnswerBar(null, '');
    summary.hidden = true;
    list.parentNode.insertBefore(summary, list);
    function show(pool) {
      while (list.firstChild) list.removeChild(list.firstChild);
      pool.forEach(function (q, i) {
        var card = renderCard(q, false);
        var no = card.querySelector('.ex-q-no');
        if (no) no.insertBefore(document.createTextNode((i + 1) + '. '), no.firstChild);
        list.appendChild(card);
      });
      if (bar) bar.hidden = false;
      summary.hidden = false;
    }
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
        // Cards read paper.sel/done when wired, so the paper exists first.
        beginPaper('practice', {
          start: Date.now(), ids: pool.map(function (q) { return q.id; }), sel: {}, done: {}
        });
        show(pool);
        note.textContent = '共 ' + pool.length + ' 題，計時開始';
        barApi.start(paper.start);
        setOnlyTodo(false);
        updateAnswerBar();
        list.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }).catch(function () {
        note.textContent = '題庫載入失敗，請重新整理頁面。';
      });
    });
    // A paper generated earlier and not handed in yet continues where it was.
    var saved = loadPaper('practice');
    if (!saved || !Array.isArray(saved.ids) || !saved.ids.length) return;
    note.textContent = '載入上次未交卷的試卷…';
    examData().then(function (data) {
      if (paper) return;  // a new paper was generated meanwhile
      // Another tab may have handed it in or saved to it while the data loaded.
      saved = loadPaper('practice');
      if (!saved || !Array.isArray(saved.ids) || !saved.ids.length) { note.textContent = ''; return; }
      var byId = {};
      data.questions.forEach(function (q) { byId[q.id] = q; });
      var pool = saved.ids.map(function (id) { return byId[id]; }).filter(Boolean);
      paperKey = 'practice';
      paper = saved;
      if (!pool.length) { endPaper(); note.textContent = ''; return; }
      show(pool);
      restoreFromPaper(pageCards());
      // The timer continues from where the page was left, not from the wall clock.
      var away = typeof saved.seen === 'number' ? Math.max(0, Date.now() - saved.seen) : 0;
      savePaper(function (p) { p.start += away; });
      if (paper) barApi.start(paper.start);
      updateAnswerBar();
      note.textContent = '已接續上次未交卷的試卷（共 ' + pool.length + ' 題）。按「產生試卷並開始計時」會改出一份新的試卷。';
    }).catch(function () {
      note.textContent = '題庫載入失敗，請重新整理頁面。';
    });
  }

  // Hub: per-chapter progress from this browser's storage (static cells show —).
  // Without working storage nothing could be saved, so the placeholders stay
  // and the controls stay disabled rather than accepting edits that vanish.
  function storageWorks() {
    try {
      var probe = '__dnExamProbe';
      localStorage.setItem(probe, '1');
      localStorage.removeItem(probe);
      return true;
    } catch (e) { return false; }
  }
  function saveRead(value) {
    try { localStorage.setItem(READ_KEY, JSON.stringify(value)); return true; } catch (e) { return false; }
  }
  function readMap() {
    var read = load(READ_KEY, {});
    return read && typeof read === 'object' && !Array.isArray(read) ? read : {};
  }
  function day(ms) {
    var d = new Date(ms);
    return d.getFullYear() + '/' + (d.getMonth() + 1) + '/' + d.getDate();
  }
  function progressSummary() {
    var el2 = document.getElementById('ex-progress-summary');
    if (!el2) return;
    var map = progressMap();
    var answered = 0, right = 0;
    Object.keys(map).forEach(function (id) {
      if (Array.isArray(map[id])) { answered += 1; if (map[id][0]) right += 1; }
    });
    var total = document.querySelector('[data-exam-total]');
    var totalCount = total ? Number(total.getAttribute('data-exam-total')) : 0;
    el2.textContent = '已作答 ' + answered + (totalCount ? ' / ' + totalCount : '') + ' 題' +
      (answered ? '，正確率 ' + Math.round(100 * right / answered) + '%' : '') +
      '，課本已讀完 ' + Object.keys(readMap()).length + ' 章';
  }
  // Fill every row from storage; safe to repeat (back-forward cache restores).
  // A row counts only the answers given on that chapter's own page.
  function refreshProgress() {
    var all = chapterProgressAll();
    var read = readMap();
    document.querySelectorAll('.ex-progress tbody tr').forEach(function (row) {
      var ids = (row.getAttribute('data-qids') || '').split(',').filter(Boolean);
      var ch = row.getAttribute('data-ch') || '';
      var slug = 'fitz-' + ch;
      var map = /^\d+$/.test(ch) && own(all, slug) && isMap(all[slug]) ? all[slug] : {};
      var done = 0, ok = 0, last = 0;
      ids.forEach(function (id) {
        var rec = own(map, id) ? map[id] : null;
        if (!Array.isArray(rec)) return;
        done += 1;
        if (rec[0]) ok += 1;
        if (typeof rec[1] === 'number' && rec[1] > last) last = rec[1];
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
      box.disabled = false;
      box.checked = Object.prototype.hasOwnProperty.call(read, row.getAttribute('data-ch'));
    });
    progressSummary();
    var sort = document.querySelector('.ex-progress-sort');
    if (sort && sort.value !== 'order') sortProgress(sort.value);
  }
  function sortProgress(mode) {
    document.querySelectorAll('.ex-progress').forEach(function (table) {
      var tbody = table.querySelector('tbody');
      var rows = Array.prototype.slice.call(tbody.rows);
      rows.sort(function (a, b) {
        var oa = Number(a.getAttribute('data-order')), ob = Number(b.getAttribute('data-order'));
        if (mode === 'todo') {
          var da = Number(a.getAttribute('data-done')), db = Number(b.getAttribute('data-done'));
          return (da === 0) === (db === 0) ? oa - ob : (da === 0 ? -1 : 1);
        }
        if (mode === 'low') {
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
  }
  function initProgress() {
    var summaryEl = document.getElementById('ex-progress-summary');
    if (!storageWorks()) {
      if (summaryEl) summaryEl.textContent = '這個瀏覽器無法儲存資料（例如無痕模式或停用網站資料），讀書進度無法記錄。';
      return;
    }
    document.querySelectorAll('.ex-pg-read').forEach(function (box) {
      box.addEventListener('change', function () {
        var ch = box.getAttribute('data-ch');
        var current = readMap();
        if (box.checked) current[ch] = Date.now(); else delete current[ch];
        if (!saveRead(current)) {
          box.checked = !box.checked;  // the change could not be kept
          if (summaryEl) summaryEl.textContent = '無法儲存「課本已讀完」，請確認瀏覽器允許網站資料。';
          return;
        }
        progressSummary();
      });
    });
    var sort = document.querySelector('.ex-progress-sort');
    if (sort) {
      sort.disabled = false;
      sort.addEventListener('change', function () { sortProgress(sort.value); });
    }
    refreshProgress();
    // A page restored from the back-forward cache skips DOMContentLoaded;
    // answers given on other pages since then must still show up here.
    window.addEventListener('pageshow', function (event) {
      if (event.persisted) refreshProgress();
    });
  }

  // ---------------------------------------------------------- hub search
  // exam/search-index.json (built by _gen_exam.py): chapters {n: title},
  // notes [chapters with notes], entries [chapter, section id ('' = chapter
  // page), section title, names, abbreviations, n primary names, n primary
  // abbreviations]. Primary terms (the section's own heading, the chapter
  // title) rank above terms that only occur inside the section.
  var SEARCH_GROUPS = 12;
  var SEARCH_PER_GROUP = 6;

  function normTerm(text) {
    var s = String(text);
    if (s.normalize) s = s.normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
    return s.toLowerCase().replace(/[\-\u2010-\u2015_\/\u00b7]/g, ' ').replace(/[\u2019']/g, '')
      .replace(/\s+/g, ' ').trim();
  }
  var HAS_CJK = /[\u3400-\u9fff]/;

  function prepareIndex(raw) {
    var notes = {};
    (raw.notes || []).forEach(function (n) { notes[n] = true; });
    var entries = raw.entries.map(function (e, i) {
      var terms = [];
      e[3].forEach(function (t, j) { terms.push({ text: t, key: normTerm(t), abbr: false, primary: j < e[5] }); });
      e[4].forEach(function (t, j) { terms.push({ text: t, key: normTerm(t), abbr: true, primary: j < e[6] }); });
      return { ch: e[0], sid: e[1], title: e[2], terms: terms, order: i };
    });
    return { chapters: raw.chapters, notes: notes, entries: entries };
  }

  // 0 exact abbreviation, 1 exact name, 2 prefix, 3 word start, 4 substring; -1 none.
  function matchTier(term, q, shortAscii, cjk) {
    var k = term.key;
    if (k === q) return term.abbr ? 0 : 1;
    var at = k.indexOf(q);
    if (at === 0) return 2;
    if (at < 0) return -1;
    if (k.indexOf(' ' + q) >= 0 || cjk) return 3;
    return term.abbr || shortAscii ? -1 : 4;
  }

  function searchIndex(index, query) {
    var q = normTerm(query);
    if (!q) return null;
    var cjk = HAS_CJK.test(q);
    // Short Latin queries (HES, BP) look like abbreviations: no mid-word hits.
    var shortAscii = !cjk && q.length <= 3;
    var hits = [];
    index.entries.forEach(function (entry) {
      var best = Infinity;
      var matched = [];
      entry.terms.forEach(function (term) {
        var tier = matchTier(term, q, shortAscii, cjk);
        if (tier < 0) return;
        var score = tier * 2 + (term.primary ? 0 : 1);
        matched.push({ text: term.text, score: score });
        if (score < best) best = score;
      });
      if (!matched.length) return;
      matched.sort(function (a, b) { return a.score - b.score; });
      hits.push({ entry: entry, score: best, matched: matched });
    });
    hits.sort(function (a, b) {
      return a.score - b.score || (a.entry.sid ? 1 : 0) - (b.entry.sid ? 1 : 0) ||
        a.entry.ch - b.entry.ch || a.entry.order - b.entry.order;
    });
    var groups = [];
    var byChapter = {};
    hits.forEach(function (hit) {
      var g = byChapter[hit.entry.ch];
      if (!g) {
        g = byChapter[hit.entry.ch] = { ch: hit.entry.ch, hits: [] };
        groups.push(g);
      }
      g.hits.push(hit);
    });
    return { query: query.trim(), total: hits.length, groups: groups };
  }

  function initSearch(box) {
    var input = box.querySelector('.ex-search-input');
    var list = box.querySelector('.ex-search-results');
    var status = box.querySelector('.ex-search-status');
    var url = box.getAttribute('data-exam-search');
    var index = null;
    var loading = null;
    var timer = null;
    var options = [];
    var active = -1;
    // Query the listed options were found for; typing makes them stale until
    // the debounced search runs again.
    var shownQuery = null;
    box.hidden = false;

    function loadIndex() {
      if (!loading) {
        loading = fetch(url, { credentials: 'same-origin' })
          .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
          .then(function (raw) { index = prepareIndex(raw); return index; });
        loading.catch(function () { loading = null; });
      }
      return loading;
    }
    function setActive(i) {
      if (active >= 0 && options[active]) options[active].setAttribute('aria-selected', 'false');
      active = i;
      if (i >= 0 && options[i]) {
        options[i].setAttribute('aria-selected', 'true');
        input.setAttribute('aria-activedescendant', options[i].id);
        options[i].scrollIntoView({ block: 'nearest' });
      } else {
        input.removeAttribute('aria-activedescendant');
      }
    }
    function close() {
      setActive(-1);
      options = [];
      while (list.firstChild) list.removeChild(list.firstChild);
      list.hidden = true;
      input.setAttribute('aria-expanded', 'false');
    }
    function render(result) {
      close();
      if (!result) { status.textContent = ''; return; }
      if (!result.total) {
        status.textContent = '找不到「' + result.query + '」。可以試試英文全名、縮寫或中文名稱。';
        return;
      }
      var shownGroups = result.groups.slice(0, SEARCH_GROUPS);
      shownGroups.forEach(function (g, gi) {
        var title = index.chapters[g.ch] || '';
        var chLabel = 'Ch.' + g.ch + ' ' + title;
        var group = el('div', 'ex-s-group');
        group.setAttribute('role', 'group');
        var head = el('p', 'ex-s-ch', chLabel);
        head.id = 'ex-s-g' + gi;
        head.setAttribute('aria-hidden', 'true');
        group.setAttribute('aria-labelledby', head.id);
        group.appendChild(head);
        g.hits.slice(0, SEARCH_PER_GROUP).forEach(function (hit) {
          var e = hit.entry;
          var opt = el('a', 'ex-s-opt');
          opt.id = 'ex-s-o' + options.length;
          opt.setAttribute('role', 'option');
          opt.setAttribute('aria-selected', 'false');
          opt.tabIndex = -1;
          opt.href = '/exam/fitz-' + e.ch + (e.sid ? '#' + e.sid : '');
          opt.appendChild(el('span', 'ex-sr', chLabel + ' '));
          opt.appendChild(el('span', 'ex-s-sec', e.sid ? '› ' + e.title
            : (index.notes[e.ch] ? '章節頁（重點整理與考題）' : '章節頁（尚無重點整理，可看考題）')));
          var names = [];
          hit.matched.forEach(function (m) {
            if (names.length < 3 && m.score === hit.matched[0].score && names.indexOf(m.text) < 0) names.push(m.text);
          });
          opt.appendChild(el('span', 'ex-s-hit', '命中：' + names.join('、')));
          opt.addEventListener('mousemove', function () {
            var i = options.indexOf(opt);
            if (i !== active) setActive(i);
          });
          group.appendChild(opt);
          options.push(opt);
        });
        if (g.hits.length > SEARCH_PER_GROUP) {
          group.appendChild(el('p', 'ex-s-more', '本章另有 ' + (g.hits.length - SEARCH_PER_GROUP) + ' 個段落也提到，請輸入更完整的名稱。'));
        }
        list.appendChild(group);
      });
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      status.textContent = '找到 ' + result.total + ' 筆，分布在 ' + result.groups.length + ' 章' +
        (result.groups.length > SEARCH_GROUPS ? '（先列出最相關的 ' + SEARCH_GROUPS + ' 章）' : '') + '。';
    }
    function run() {
      var query = input.value;
      if (!normTerm(query)) { render(null); return; }
      if (!index) status.textContent = '搜尋索引載入中…';
      loadIndex().then(function () {
        if (input.value !== query) return;
        render(searchIndex(index, query));
        shownQuery = query;
      }).catch(function () {
        close();
        status.textContent = '搜尋索引載入失敗，請重新整理頁面。';
      });
    }
    input.addEventListener('focus', function () { loadIndex().catch(function () {}); });
    input.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(run, 150);
    });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        if (!options.length) return;
        event.preventDefault();
        var step = event.key === 'ArrowDown' ? 1 : -1;
        setActive(active < 0 ? (step > 0 ? 0 : options.length - 1)
          : (active + step + options.length) % options.length);
      } else if (event.key === 'Enter') {
        if (event.isComposing) return;  // finishing a 注音／倉頡 composition
        event.preventDefault();
        clearTimeout(timer);
        // Results still listed for an earlier query (or a cleared box): search
        // what is typed now instead of opening one of them; an empty box only
        // clears the list.
        if (!options.length || shownQuery !== input.value || !normTerm(input.value)) { run(); return; }
        var target = options[active >= 0 ? active : 0];
        if (target) window.location.href = target.href;
      } else if (event.key === 'Escape') {
        if (!list.hidden) { event.preventDefault(); close(); }
        else if (input.value) { event.preventDefault(); input.value = ''; render(null); }
      }
    });
  }

  // Hub frequency table: every chapter is in the HTML; show RANK_PAGE rows at
  // a time behind 「載入更多」 (without JS the whole table stays visible).
  function initRank(table) {
    var page = Number(table.getAttribute('data-rank-page')) || 25;
    var rows = table.tBodies[0] ? table.tBodies[0].rows : [];
    var wrap = document.querySelector('.ex-more-wrap');
    var btn = wrap && wrap.querySelector('.ex-more');
    if (!btn || rows.length <= page) return;
    var shown = page;
    for (var i = page; i < rows.length; i++) rows[i].hidden = true;
    function label() {
      btn.textContent = '載入更多（' + (shown + 1) + '–' + Math.min(shown + page, rows.length) + '）';
    }
    label();
    wrap.hidden = false;
    btn.addEventListener('click', function () {
      var first = rows[shown];
      var end = Math.min(shown + page, rows.length);
      for (var j = shown; j < end; j++) rows[j].hidden = false;
      shown = end;
      if (shown >= rows.length) {
        wrap.hidden = true;  // focus would be lost with the button; move it to the new rows
        var link = first.querySelector('a');
        if (link) link.focus();
      } else {
        label();
      }
    });
  }

  // Chapter pages: a link to #section must show it even if it sits in a
  // closed <details>; the :target highlight itself is plain CSS.
  function openDetails(target) {
    var opened = false;
    for (var d = target.closest('details'); d; d = d.parentElement && d.parentElement.closest('details')) {
      if (!d.open) { d.open = true; opened = true; }
    }
    return opened;
  }
  function revealTarget() {
    var id = window.location.hash.slice(1);
    if (!id) return;
    try { id = decodeURIComponent(id); } catch (e) { return; }
    var target = document.getElementById(id);
    if (!target) return;
    if (openDetails(target)) target.scrollIntoView();
  }

  // ---------------------------------------------------------- reading place
  // Chapter pages remember, on this device only, which note section (or which
  // question) was at the top of the window, and reopen there next time —
  // unless the address carries a #section, which always wins.
  var POS_LINE = 96;  // px below the top of the window: under the 64px site header
  var POS_ANCHORS = 'main section.ex-note[id], #qs-h, main .ex-q[id]';
  function posMap() {
    var map = load(POS_KEY, {});
    return isMap(map) ? map : {};
  }
  function anchorTitle(node) {
    if (node.id === 'qs-h') return '考題';
    if (node.classList.contains('ex-q')) {
      var no = node.querySelector('.ex-q-no');
      return '考題 ' + (no ? no.textContent.trim() : '');
    }
    var h = node.querySelector('h2');
    return (h ? h.textContent : node.id).replace(/\s+/g, ' ').trim();
  }
  function initReadingPlace(slug) {
    if (!slug || !storageWorks()) return;
    var settling = false;  // our own jump is not the reader's position
    var pending = null;

    function current() {
      var list = document.querySelectorAll(POS_ANCHORS);
      var best = null;
      var top = 0;
      for (var i = 0; i < list.length; i++) {
        if (!list[i].getClientRects().length) continue;  // hidden (只看未作答)
        var r = list[i].getBoundingClientRect();
        if (r.top > POS_LINE) break;
        best = list[i];
        top = r.top;
      }
      return best ? { id: best.id, dy: Math.round(POS_LINE - top) } : null;
    }
    function save() {
      if (pending) { clearTimeout(pending); pending = null; }
      if (settling) return;
      var pos = current();
      var map = posMap();
      if (pos) map[slug] = { id: pos.id, dy: pos.dy, t: Date.now() };
      else delete map[slug];  // back above the notes: next visit starts at the top
      store(POS_KEY, map);
    }
    function forget() {
      var map = posMap();
      delete map[slug];
      store(POS_KEY, map);
    }
    window.addEventListener('scroll', function () {
      if (settling || pending) return;
      pending = setTimeout(save, 300);
    }, { passive: true });
    window.addEventListener('pagehide', save);

    var rec = posMap()[slug];
    if (!isMap(rec) || typeof rec.id !== 'string') return;
    var target = document.getElementById(rec.id);
    if (!target || !target.matches(POS_ANCHORS)) { forget(); return; }
    if (window.location.hash.length > 1) return;  // a link to a section wins

    function jump() {
      openDetails(target);
      var r = target.getBoundingClientRect();
      var dy = Math.max(0, Math.min(Number(rec.dy) || 0, Math.max(0, r.height - 40)));
      window.scrollTo(0, Math.max(0, window.pageYOffset + r.top - (POS_LINE - dy)));
    }
    function settle() {
      if (!settling) return;
      settling = false;
      ['wheel', 'touchstart', 'keydown', 'mousedown'].forEach(function (type) {
        window.removeEventListener(type, settle, true);
      });
    }
    settling = true;
    // The browser's own reload scroll restoration would fight the jump.
    try { if ('scrollRestoration' in history) history.scrollRestoration = 'manual'; } catch (e) { /* ignore */ }
    jump();
    // Any input from the reader ends the restore; until then, re-apply it
    // once fonts and late layout have settled.
    ['wheel', 'touchstart', 'keydown', 'mousedown'].forEach(function (type) {
      window.addEventListener(type, settle, { capture: true, passive: true });
    });
    function finish() {
      if (!settling) return;
      jump();
      requestAnimationFrame(function () { setTimeout(settle, 100); });
    }
    if (document.readyState === 'complete') setTimeout(finish, 0);
    else window.addEventListener('load', finish);
    setTimeout(finish, 3000);
    showResumeHint(anchorTitle(target), function () {
      settle();
      forget();
      window.scrollTo(0, 0);
    });
  }
  function showResumeHint(title, restart) {
    var box = el('div', 'ex-resume');
    box.setAttribute('role', 'status');
    box.appendChild(el('span', 'ex-resume-text', '已回到上次閱讀位置：〈' + title + '〉'));
    var top = el('button', 'ex-resume-top', '從頭開始');
    var close = el('button', 'ex-resume-close', '×');
    close.setAttribute('aria-label', '關閉提示');
    top.type = close.type = 'button';
    box.appendChild(top);
    box.appendChild(close);
    function dismiss() { box.remove(); }
    top.addEventListener('click', function () { restart(); dismiss(); });
    close.addEventListener('click', dismiss);
    document.body.appendChild(box);
    // Leave quietly after a while unless the reader is using it.
    setTimeout(function () {
      if (!box.contains(document.activeElement) && !box.matches(':hover')) dismiss();
    }, 12000);
  }

  function init() {
    var search = document.querySelector('[data-exam-search]');
    if (search && window.fetch) initSearch(search);
    var rank = document.getElementById('ex-rank');
    if (rank) initRank(rank);
    revealTarget();
    window.addEventListener('hashchange', revealTarget);
    document.querySelectorAll('.ex-mode').forEach(function (btn) {
      btn.addEventListener('click', function () { setMode(btn.getAttribute('data-mode')); });
    });
    setMode(load(MODE_KEY, 'browse') === 'quiz' ? 'quiz' : 'browse');
    document.querySelectorAll('.ex-q').forEach(wireQuestion);
    var bar = document.querySelector('[data-exam-bar]');
    var barApi = bar ? wireExamBar(bar) : null;
    window.addEventListener('storage', syncPaperFromStorage);
    var kind = pageKind();
    var CLEAR_SCOPE = { chapter: '本章', year: '本卷', book: '本頁' };
    var modeBar = document.querySelector('.ex-mode');
    modeBar = modeBar && modeBar.closest('.ex-toolbar');
    if (CLEAR_SCOPE[kind] && modeBar && document.querySelector('.ex-q')) {
      var cards = pageCards();
      var resumed = kind === 'year' && barApi ? loadPaper(pageSlug()) : null;
      if (resumed) {
        // 開始計時作答 was pressed and the paper not handed in: continue it.
        paperKey = pageSlug();
        paper = resumed;
        restoreFromPaper(cards);
        var away = typeof resumed.seen === 'number' ? Math.max(0, Date.now() - resumed.seen) : 0;
        savePaper(function (p) { p.start += away; });
        if (paper) barApi.start(paper.start);
      } else {
        restoreFromProgress(cards);
      }
      var scope = CLEAR_SCOPE[kind];
      modeBar.parentNode.insertBefore(buildAnswerBar('清除' + scope + '作答紀錄', scope), modeBar.nextSibling);
      updateAnswerBar();
    }
    var form = document.querySelector('[data-practice-form]');
    if (form && barApi) initPractice(form, barApi);
    if (kind === 'chapter') initReadingPlace(pageSlug());
    var list = document.getElementById('ex-review-list');
    if (list) renderReview(list);
    if (document.querySelector('.ex-progress')) initProgress();
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
