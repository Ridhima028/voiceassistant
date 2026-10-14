"""
Renders a lecture's generated study material into one self-contained HTML page.

Everything the user generated — notes with Mermaid diagrams, mind map,
glossary, quiz, flashcards, chapters, transcript — is rendered client-side:
  - marked.js   parses the Markdown notes
  - mermaid.js  renders the ```mermaid blocks into actual diagrams
  - MathJax     typesets any LaTeX in the notes

Data is injected as JSON in a <script type="application/json"> block rather
than string-interpolated into HTML, so a stray quote, backtick or </script>
in generated content can't break the page or inject markup.
"""

import json
from html import escape


def _format_timestamp(seconds: float | int | None) -> str:
    if seconds is None:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def render_study_pack_html(lecture) -> str:
    payload = {
        "title": lecture.title or "Untitled Lecture",
        "language": lecture.language,
        "duration": _format_timestamp(lecture.duration_seconds),
        "status": lecture.status,
        "createdAt": lecture.created_at.strftime("%d %b %Y") if lecture.created_at else "",
        "summary": lecture.summary,
        "notes": lecture.notes,
        "mindmap": lecture.mindmap,
        "keyConcepts": lecture.key_concepts or [],
        "quiz": lecture.quiz or [],
        "flashcards": lecture.flashcards or [],
        "chapters": [
            {**c, "stamp": _format_timestamp(c.get("start_seconds"))}
            for c in (lecture.chapters or [])
        ],
        "segments": lecture.processed_segments or lecture.segments or [],
    }

    # </script> inside JSON would terminate the block early — escape it.
    data_json = json.dumps(payload).replace("</", "<\\/")

    return _TEMPLATE.replace("__TITLE__", escape(payload["title"])).replace(
        "__DATA__", data_json
    )


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — VoicePilot Study Pack</title>

<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>
<script>
  window.MathJax = {
    tex: { inlineMath: [['$','$']], displayMath: [['$$','$$']] },
    options: { skipHtmlTags: ['script','noscript','style','textarea','pre','code'] }
  };
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.min.js"></script>

<style>
  :root {
    --bg: #0f1117; --panel: #171a23; --panel-2: #1e222d; --border: #2a2f3d;
    --text: #e6e8ee; --muted: #9aa3b5; --accent: #6ea8fe; --accent-2: #7ee3b0;
    --warn: #ffc857; --danger: #ff6b6b; --radius: 12px;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #f6f7fb; --panel: #ffffff; --panel-2: #f0f2f7; --border: #dfe3ec;
      --text: #1a1d26; --muted: #5d6478; --accent: #2563eb; --accent-2: #0f9d6b;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.65 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  .wrap { max-width: 920px; margin: 0 auto; padding: 28px 20px 80px; }

  header.hero {
    background: linear-gradient(135deg, var(--panel) 0%, var(--panel-2) 100%);
    border: 1px solid var(--border); border-radius: var(--radius);
    padding: 26px 28px; margin-bottom: 22px;
  }
  .brand { font-size: 12px; letter-spacing: .14em; text-transform: uppercase; color: var(--accent); font-weight: 700; }
  h1 { margin: 8px 0 12px; font-size: 27px; line-height: 1.25; }
  .meta { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip {
    background: var(--panel-2); border: 1px solid var(--border); color: var(--muted);
    padding: 4px 11px; border-radius: 999px; font-size: 12.5px;
  }

  nav.toc { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }
  nav.toc a {
    background: var(--panel); border: 1px solid var(--border); color: var(--text);
    padding: 7px 14px; border-radius: 999px; font-size: 13px;
    text-decoration: none; transition: .15s;
  }
  nav.toc a:hover { border-color: var(--accent); color: var(--accent); }

  section.card {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 22px 26px; margin-bottom: 20px;
  }
  section.card > h2 {
    margin: 0 0 16px; font-size: 18px; display: flex; align-items: center; gap: 9px;
    padding-bottom: 11px; border-bottom: 1px solid var(--border);
  }
  section.card > h2 .ico { font-size: 17px; }

  .prose h2 { font-size: 17px; margin: 26px 0 10px; color: var(--accent); }
  .prose h3 { font-size: 15px; margin: 18px 0 8px; }
  .prose ul, .prose ol { padding-left: 21px; }
  .prose li { margin: 5px 0; }
  .prose code {
    background: var(--panel-2); border: 1px solid var(--border);
    padding: 1px 6px; border-radius: 5px; font-size: 13px;
  }
  .prose pre { background: var(--panel-2); border: 1px solid var(--border);
    padding: 13px; border-radius: 9px; overflow-x: auto; }
  .prose pre code { background: none; border: none; padding: 0; }
  .prose table { border-collapse: collapse; width: 100%; margin: 14px 0; font-size: 13.5px; }
  .prose th, .prose td { border: 1px solid var(--border); padding: 8px 11px; text-align: left; }
  .prose th { background: var(--panel-2); }
  .prose blockquote {
    border-left: 3px solid var(--accent); margin: 14px 0;
    padding: 6px 15px; color: var(--muted); background: var(--panel-2);
    border-radius: 0 8px 8px 0;
  }

  .mermaid-wrap {
    background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 10px; padding: 18px; margin: 16px 0; overflow-x: auto; text-align: center;
  }

  .concepts { display: grid; gap: 11px; }
  .concept {
    background: var(--panel-2); border: 1px solid var(--border);
    border-left: 3px solid var(--muted); border-radius: 9px; padding: 13px 16px;
  }
  .concept.core { border-left-color: var(--accent); }
  .concept.supporting { border-left-color: var(--accent-2); }
  .concept .term { font-weight: 650; font-size: 14.5px; }
  .concept .badge {
    font-size: 10.5px; text-transform: uppercase; letter-spacing: .07em;
    padding: 2px 8px; border-radius: 999px; margin-left: 9px;
    background: var(--panel); border: 1px solid var(--border); color: var(--muted);
  }
  .concept .def { margin-top: 5px; color: var(--muted); font-size: 13.8px; }
  .concept .rel { margin-top: 7px; font-size: 12.3px; color: var(--muted); }
  .concept .rel span { background: var(--panel); border: 1px solid var(--border);
    padding: 2px 8px; border-radius: 999px; margin-right: 5px; display: inline-block; }

  .q { background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 10px; padding: 15px 17px; margin-bottom: 12px; }
  .q .qhead { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
  .q .qtext { font-weight: 600; }
  .diff { font-size: 10.5px; text-transform: uppercase; letter-spacing: .07em;
    padding: 2px 9px; border-radius: 999px; white-space: nowrap; border: 1px solid var(--border); }
  .diff.easy { color: var(--accent-2); } .diff.medium { color: var(--warn); } .diff.hard { color: var(--danger); }
  .opts { list-style: none; padding: 0; margin: 11px 0 0; }
  .opts li {
    border: 1px solid var(--border); border-radius: 8px; padding: 8px 13px;
    margin: 6px 0; cursor: pointer; transition: .13s; background: var(--panel);
  }
  .opts li:hover { border-color: var(--accent); }
  .opts li.correct { border-color: var(--accent-2); background: color-mix(in srgb, var(--accent-2) 12%, var(--panel)); }
  .opts li.wrong { border-color: var(--danger); background: color-mix(in srgb, var(--danger) 12%, var(--panel)); }
  .expl { margin-top: 11px; padding: 11px 13px; border-radius: 8px;
    background: var(--panel); border: 1px solid var(--border);
    font-size: 13.5px; color: var(--muted); display: none; }
  .expl.show { display: block; }

  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(215px, 1fr)); gap: 12px; }
  .fc { perspective: 1000px; height: 160px; cursor: pointer; }
  .fc-inner { position: relative; width: 100%; height: 100%; transition: transform .5s;
    transform-style: preserve-3d; }
  .fc.flipped .fc-inner { transform: rotateY(180deg); }
  .fc-face {
    position: absolute; inset: 0; backface-visibility: hidden;
    border: 1px solid var(--border); border-radius: 10px; padding: 14px;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
    text-align: center; background: var(--panel-2); font-size: 13.5px; overflow: auto;
  }
  .fc-back { transform: rotateY(180deg); background: var(--panel);
    border-color: var(--accent); color: var(--muted); }
  .fc .topic { position: absolute; top: 8px; left: 10px; font-size: 10px;
    text-transform: uppercase; letter-spacing: .07em; color: var(--accent); }
  .fc .hint { margin-top: 8px; font-size: 11.5px; color: var(--muted); font-style: italic; }

  .chapters { display: grid; gap: 9px; }
  .chapter { display: flex; gap: 13px; align-items: flex-start;
    background: var(--panel-2); border: 1px solid var(--border);
    border-radius: 9px; padding: 11px 14px; }
  .chapter .stamp { font-variant-numeric: tabular-nums; color: var(--accent);
    font-weight: 650; font-size: 13px; min-width: 52px; }
  .chapter .ctitle { font-weight: 600; font-size: 14px; }
  .chapter .csum { color: var(--muted); font-size: 13px; margin-top: 2px; }

  .seg { display: flex; gap: 13px; padding: 8px 0; border-bottom: 1px solid var(--border); }
  .seg:last-child { border-bottom: none; }
  .seg .stamp { color: var(--accent); font-variant-numeric: tabular-nums;
    font-size: 12.5px; min-width: 52px; padding-top: 2px; }
  .transcript-scroll { max-height: 460px; overflow-y: auto; padding-right: 8px; }

  .empty { color: var(--muted); font-size: 13.5px; font-style: italic; }
  footer { text-align: center; color: var(--muted); font-size: 12.5px; margin-top: 34px; }

  @media print {
    body { background: #fff; color: #000; }
    nav.toc, .fc { display: none; }
    section.card { break-inside: avoid; border-color: #ccc; }
    .expl { display: block !important; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <div class="brand">VoicePilot Study Pack</div>
    <h1 id="hTitle"></h1>
    <div class="meta" id="hMeta"></div>
  </header>

  <nav class="toc" id="toc"></nav>
  <main id="main"></main>

  <footer>Generated by VoicePilot · AI-generated study material — verify against your source material.</footer>
</div>

<script type="application/json" id="payload">__DATA__</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById('payload').textContent);

  document.getElementById('hTitle').textContent = D.title;

  var meta = [];
  if (D.duration) meta.push('⏱ ' + D.duration);
  if (D.language) meta.push('🌐 ' + D.language.toUpperCase());
  if (D.createdAt) meta.push('📅 ' + D.createdAt);
  meta.push(D.status === 'completed' ? '✓ Transcribed' : '⚠ ' + D.status);
  document.getElementById('hMeta').innerHTML =
    meta.map(function (m) { return '<span class="chip">' + m + '</span>'; }).join('');

  var main = document.getElementById('main');
  var toc = [];

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c];
    });
  }

  function section(id, icon, title, inner) {
    if (!inner) return;
    toc.push({ id: id, title: title });
    var s = document.createElement('section');
    s.className = 'card';
    s.id = id;
    s.innerHTML = '<h2><span class="ico">' + icon + '</span>' + esc(title) + '</h2>' + inner;
    main.appendChild(s);
  }

  // ---- Summary
  if (D.summary) {
    section('summary', '📌', 'Summary', '<div class="prose">' + marked.parse(D.summary) + '</div>');
  }

  // ---- Chapters
  if (D.chapters && D.chapters.length) {
    section('chapters', '🗂', 'Chapters', '<div class="chapters">' + D.chapters.map(function (c) {
      return '<div class="chapter"><div class="stamp">' + esc(c.stamp) + '</div><div>' +
        '<div class="ctitle">' + esc(c.title) + '</div>' +
        (c.summary ? '<div class="csum">' + esc(c.summary) + '</div>' : '') +
        '</div></div>';
    }).join('') + '</div>');
  }

  // ---- Notes (Markdown + Mermaid). Mermaid blocks are extracted BEFORE
  // marked runs, so it can't mangle the diagram source into <code>.
  if (D.notes) {
    var mermaidBlocks = [];
    var notesSrc = D.notes.replace(/```mermaid\s*\n([\s\S]*?)```/g, function (_, code) {
      mermaidBlocks.push(code.trim());
      return '\n@@MERMAID' + (mermaidBlocks.length - 1) + '@@\n';
    });

    var html = marked.parse(notesSrc);
    html = html.replace(/<p>\s*@@MERMAID(\d+)@@\s*<\/p>|@@MERMAID(\d+)@@/g, function (_, a, b) {
      var i = a !== undefined ? a : b;
      return '<div class="mermaid-wrap"><pre class="mermaid">' + esc(mermaidBlocks[i]) + '</pre></div>';
    });

    section('notes', '📝', 'Notes', '<div class="prose">' + html + '</div>');
  }

  // ---- Mind map
  if (D.mindmap) {
    section('mindmap', '🧠', 'Mind Map',
      '<div class="mermaid-wrap"><pre class="mermaid">' + esc(D.mindmap) + '</pre></div>');
  }

  // ---- Key concepts
  if (D.keyConcepts && D.keyConcepts.length) {
    section('concepts', '🔑', 'Key Concepts', '<div class="concepts">' + D.keyConcepts.map(function (c) {
      var imp = (c.importance || 'supporting').toLowerCase();
      var rel = (c.related_terms || []).length
        ? '<div class="rel">Related: ' + c.related_terms.map(function (r) {
            return '<span>' + esc(r) + '</span>'; }).join('') + '</div>'
        : '';
      return '<div class="concept ' + esc(imp) + '">' +
        '<div><span class="term">' + esc(c.term) + '</span>' +
        '<span class="badge">' + esc(imp) + '</span></div>' +
        '<div class="def">' + esc(c.definition) + '</div>' + rel + '</div>';
    }).join('') + '</div>');
  }

  // ---- Quiz
  if (D.quiz && D.quiz.length) {
    section('quiz', '🎯', 'Quiz (' + D.quiz.length + ' questions)', D.quiz.map(function (q, qi) {
      var diff = (q.difficulty || 'medium').toLowerCase();
      return '<div class="q" data-correct="' + q.correct_index + '">' +
        '<div class="qhead"><div class="qtext">' + (qi + 1) + '. ' + esc(q.question) + '</div>' +
        '<span class="diff ' + esc(diff) + '">' + esc(diff) + '</span></div>' +
        '<ul class="opts">' + (q.options || []).map(function (o, oi) {
          return '<li data-i="' + oi + '">' + esc(o) + '</li>';
        }).join('') + '</ul>' +
        (q.explanation ? '<div class="expl">' + esc(q.explanation) + '</div>' : '') +
        '</div>';
    }).join(''));

    main.querySelectorAll('.q').forEach(function (qEl) {
      var correct = parseInt(qEl.dataset.correct, 10);
      qEl.querySelectorAll('.opts li').forEach(function (li) {
        li.addEventListener('click', function () {
          if (qEl.dataset.answered) return;
          qEl.dataset.answered = '1';
          var picked = parseInt(li.dataset.i, 10);
          qEl.querySelectorAll('.opts li').forEach(function (o) {
            var i = parseInt(o.dataset.i, 10);
            if (i === correct) o.classList.add('correct');
            else if (i === picked) o.classList.add('wrong');
          });
          var ex = qEl.querySelector('.expl');
          if (ex) ex.classList.add('show');
        });
      });
    });
  }

  // ---- Flashcards
  if (D.flashcards && D.flashcards.length) {
    section('flashcards', '🃏', 'Flashcards (' + D.flashcards.length + ')',
      '<p class="empty">Click a card to flip it.</p><div class="cards">' +
      D.flashcards.map(function (f) {
        return '<div class="fc"><div class="fc-inner">' +
          '<div class="fc-face">' +
            (f.topic ? '<div class="topic">' + esc(f.topic) + '</div>' : '') +
            '<div>' + esc(f.front) + '</div>' +
            (f.hint ? '<div class="hint">Hint: ' + esc(f.hint) + '</div>' : '') +
          '</div>' +
          '<div class="fc-face fc-back">' + esc(f.back) + '</div>' +
        '</div></div>';
      }).join('') + '</div>');

    main.querySelectorAll('.fc').forEach(function (c) {
      c.addEventListener('click', function () { c.classList.toggle('flipped'); });
    });
  }

  // ---- Transcript
  if (D.segments && D.segments.length) {
    section('transcript', '📄', 'Transcript', '<div class="transcript-scroll">' +
      D.segments.map(function (s) {
        var t = Math.floor(s.start || 0);
        var stamp = Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0');
        return '<div class="seg"><div class="stamp">' + stamp + '</div><div>' + esc(s.text) + '</div></div>';
      }).join('') + '</div>');
  }

  if (!main.children.length) {
    main.innerHTML = '<section class="card"><p class="empty">' +
      'Nothing generated yet. Run POST /lectures/{id}/study-pack first.</p></section>';
  }

  // ---- TOC
  document.getElementById('toc').innerHTML = toc.map(function (t) {
    return '<a href="#' + t.id + '">' + esc(t.title) + '</a>';
  }).join('');

  // ---- Mermaid
  var dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  mermaid.initialize({
    startOnLoad: false,
    theme: dark ? 'dark' : 'default',
    securityLevel: 'strict',
    flowchart: { useMaxWidth: true, htmlLabels: false }
  });

  // Render each diagram individually so one bad diagram doesn't kill the rest.
  document.querySelectorAll('pre.mermaid').forEach(function (el, i) {
    var src = el.textContent;
    mermaid.render('mmd' + i, src)
      .then(function (r) { el.outerHTML = r.svg; })
      .catch(function () {
        el.outerHTML = '<div class="empty">Diagram could not be rendered.' +
          '<pre class="prose">' + esc(src) + '</pre></div>';
      });
  });
})();
</script>
</body>
</html>
"""
