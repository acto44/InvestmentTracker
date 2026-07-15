"""Model → HTML. Print-media styling (light), no template engine — plain
string building plus string.Template for the page skeleton.

REPORT_STYLE_NOTES — what QTextDocument actually renders (verified
empirically; stay inside this subset):
  SAFE: h1–h4, p, b/i/strong/em, hr, br, a name/href, span/p/td inline
        style with color, background-color, font-size, font-weight,
        font-family, text-align; table with border/cellpadding/
        cellspacing/width attributes and bgcolor on tr/td/th; img src
        (resolved via document resources or data URIs in browsers).
  UNRELIABLE in QTextDocument: external CSS, <style> classes beyond
        simple element selectors, margin/padding shorthand on divs,
        position/float, data: URIs for images (browsers fine, QTextDocument
        not — hence the named-placeholder image scheme resolved by each
        exporter its own way).
All template text is Python constants — no bundled asset files, nothing
new for the PyInstaller build (CLAUDE.md: PYINSTALLER RESOURCES).
"""

from __future__ import annotations

import html as _html
from string import Template

INK = '#1E293B'
MUTED = '#64748B'
BORDER_C = '#CBD5E1'
ACCENT = '#2563EB'
GREEN = '#15803D'
RED = '#B91C1C'
BG_HEAD = '#F1F5F9'

ALL_SECTIONS = ('position', 'valuations', 'rounds', 'ledger', 'ownership',
                'thesis', 'documents', 'appendix')


def esc(s) -> str:
    return _html.escape(str(s if s is not None else ''))


_PAGE = Template("""
<html><body style="font-family:'Segoe UI',sans-serif; color:$ink;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td><h1 style="color:$ink;">$company</h1></td>
<td align="right"><span style="color:$muted; font-size:9pt;">
$app<br>Report date: $report_date<br>Figures as of: $as_of</span></td></tr>
</table>
<p style="color:$muted; font-size:10pt;">$subtitle</p>
<p style="color:$red; font-size:8pt;"><b>CONFIDENTIAL</b> — contains
private financial information. Do not distribute.</p>
<hr>
$body
<hr>
<p style="color:$muted; font-size:8pt;">$app · generated $report_date ·
figures as of $as_of · CONFIDENTIAL</p>
</body></html>
""")


def _h2(anchor, text):
    return (f'<a name="{anchor}"></a>'
            f'<h2 style="color:{INK};">{esc(text)}</h2>')


def _table(headers, rows, aligns=None):
    """rows = list of lists of already-escaped cell HTML strings."""
    aligns = aligns or ['left'] * len(headers)
    out = [f'<table width="100%" border="0.5" cellpadding="4" '
           f'cellspacing="0" style="font-size:9pt;">',
           '<tr bgcolor="' + BG_HEAD + '">']
    for h, a in zip(headers, aligns):
        out.append(f'<th align="{a}" style="color:{INK};">{esc(h)}</th>')
    out.append('</tr>')
    for r in rows:
        out.append('<tr>')
        for cell, a in zip(r, aligns):
            out.append(f'<td align="{a}">{cell}</td>')
        out.append('</tr>')
    out.append('</table>')
    return ''.join(out)


def _fn(n):
    """Footnote marker pointing at the appendix."""
    return (f'<span style="color:{MUTED}; font-size:7pt;"> '
            f'<a href="#appendix">[{n}]</a></span>')


def _section_position(m):
    p = m['position']
    est = (f' <span style="color:{MUTED}; font-size:8pt;">(estimated)'
           '</span>' if p['is_estimate'] else '')
    src = ''
    if p['val_as_of']:
        src = (f'<p style="color:{MUTED}; font-size:8pt;">Current value '
               f'based on the valuation of {esc(p["val_as_of"])} '
               f'({esc(p["val_source"])}).</p>')
    rows = [[
        esc(p['invested']['fmt']) + _fn(2),
        esc(p['realized']['fmt']) + _fn(3),
        esc(p['current_value']['fmt']) + est + _fn(1),
        esc(p['moic']['fmt']) + _fn(4),
        esc(p['dpi']['fmt']) + _fn(5),
        esc(p['tvpi']['fmt']) + _fn(7),
        esc(p['irr']['fmt']) + _fn(8),
    ]]
    return (_h2('position', 'Position summary')
            + _table(['Invested', 'Realized', 'Current value', 'MOIC',
                      'DPI', 'TVPI', 'IRR'], rows,
                     aligns=['right'] * 7)
            + src)


def _section_valuations(m, images):
    v = m['valuations']
    if not v['rows']:
        return ''
    chart = ''
    if v['chart'] in images:
        chart = f'<p><img src="{v["chart"]}" width="640"></p>'
    rows = [[esc(r['date']),
             esc(r['value']['fmt']),
             esc(r['source']),
             esc(r['note']),
             (f'<span style="color:'
              f'{GREEN if (r["delta_pct"]["raw"] or 0) >= 0 else RED};">'
              f'{esc(r["delta_pct"]["fmt"])}</span>')]
            for r in v['rows']]
    return (_h2('valuations', 'Valuation development')
            + chart
            + _table(['As of', 'Company valuation', 'Source', 'Note',
                      'Δ% vs previous'], rows,
                     aligns=['left', 'right', 'left', 'left', 'right']))


def _section_rounds(m):
    rows = m['rounds']['rows']
    if not rows:
        return ''
    body = [[esc(r['name']), esc(r['date']), esc(r['amount']['fmt']),
             esc(r['pre_money']['fmt']), esc(r['post_money']['fmt']),
             esc(r['shares']['fmt']), esc(r['pps']['fmt']),
             esc(r['ownership_pct']['fmt'])] for r in rows]
    return (_h2('rounds', 'Round history')
            + _table(['Round', 'Date', 'Amount', 'Pre-money', 'Post-money',
                      'Shares', 'Price/share', 'Ownership'], body,
                     aligns=['left', 'left'] + ['right'] * 6))


def _section_ledger(m):
    rows = m['ledger']['rows']
    if not rows:
        return ''
    body = []
    for r in rows:
        color = GREEN if (r['signed']['raw'] or 0) >= 0 else RED
        body.append([
            esc(r['date']), esc(r['type']),
            f'<span style="color:{color};">{esc(r["signed"]["fmt"])}</span>',
            esc(r['run_invested']['fmt']), esc(r['run_realized']['fmt']),
            esc(r['note'])])
    totals = (f'<p style="font-size:9pt;"><b>Invested total:</b> '
              f'{esc(m["ledger"]["invested_total"]["fmt"])} &nbsp;·&nbsp; '
              f'<b>Realized total:</b> '
              f'{esc(m["ledger"]["realized_total"]["fmt"])}</p>')
    return (_h2('ledger', 'Cash-flow ledger')
            + _table(['Date', 'Type', 'Amount', 'Invested →', 'Realized →',
                      'Note'], body,
                     aligns=['left', 'left', 'right', 'right', 'right',
                             'left'])
            + totals)


def _section_ownership(m):
    o = m['ownership']
    if o['ownership_pct']['raw'] is None and not o['shares_held']['raw']:
        return ''
    return (_h2('ownership', 'Ownership & shares')
            + f'<p style="font-size:9.5pt;">Shares held: '
              f'<b>{esc(o["shares_held"]["fmt"])}</b> &nbsp;·&nbsp; '
              f'Ownership: <b>{esc(o["ownership_pct"]["fmt"])}</b><br>'
              f'<span style="color:{MUTED}; font-size:8.5pt;">Basis: '
              f'{esc(o["basis"])}</span></p>')


def _section_thesis(m):
    t = m['thesis']
    parts = []
    if t['text']:
        parts.append(f'<p style="font-size:9.5pt;">{esc(t["text"])}</p>')
    for u in t['journal']:
        head = esc(u['date'])
        if u.get('period_label'):
            head += f' · {esc(u["period_label"])}'
        if u.get('title'):
            head += f' — <b>{esc(u["title"])}</b>'
        parts.append(f'<p style="font-size:9pt;"><span style="color:'
                     f'{ACCENT};">{head}</span><br>{esc(u["text"])}</p>')
    if not parts:
        return ''
    # named slot for the session-8 AI narrative — renders nothing today
    ai_anchor = f'<a name="{t["ai_slot"]}"></a>'
    return (_h2('thesis', 'Thesis & status')
            + parts[0] + ai_anchor + ''.join(parts[1:]))


def _section_documents(m):
    rows = m['documents']['rows']
    if not rows:
        return ''
    body = [[esc(r['filename']), esc(r['doc_type']), esc(r['added'])]
            for r in rows]
    return (_h2('documents', 'Documents on file')
            + _table(['Filename', 'Type', 'Added'], body))


def _section_appendix(m):
    a = m['appendix']
    items = ''.join(
        f'<p style="font-size:8.5pt; color:{MUTED};">[{i}] {esc(fn)}</p>'
        for i, fn in enumerate(a['footnotes'], 1))
    extra = (f'<p style="font-size:8.5pt; color:{MUTED};">'
             f'{esc(a["currency_note"])}</p>')
    return (_h2('appendix', 'Methodology & assumptions')
            + items + extra)


_SECTION_FUNCS = {
    'position': lambda m, imgs: _section_position(m),
    'valuations': _section_valuations,
    'rounds': lambda m, imgs: _section_rounds(m),
    'ledger': lambda m, imgs: _section_ledger(m),
    'ownership': lambda m, imgs: _section_ownership(m),
    'thesis': lambda m, imgs: _section_thesis(m),
    'documents': lambda m, imgs: _section_documents(m),
    'appendix': lambda m, imgs: _section_appendix(m),
}


def render_report_html(model: dict, images: dict | None = None,
                       sections=None) -> str:
    """HTML string with named image placeholders (see module docstring)."""
    images = images or {}
    chosen = [s for s in ALL_SECTIONS
              if sections is None or s in sections]
    body = ''.join(_SECTION_FUNCS[s](model, images) for s in chosen)
    meta = model['meta']
    subtitle = ' · '.join(x for x in (meta['sector'], meta['country'],
                                      meta['entity']) if x)
    return _PAGE.substitute(
        ink=INK, muted=MUTED, red=RED,
        company=esc(meta['company_name']),
        subtitle=esc(subtitle or meta.get('description', '')[:120]),
        app=esc(meta['app']),
        report_date=esc(meta['report_date']),
        as_of=esc(meta['as_of']),
        body=body,
    )
