"""Session 5 tests: builder equals metrics, as-of historical correctness,
render anchors + empty-section skipping, portable HTML, plausible PDF,
filename sanitization."""

import os
from datetime import date

import pytest

import formatting as F
import metrics
import models
from reporting.builder import build_company_report_model
from reporting.charts import build_company_chart_images
from reporting.export import (generate_company_report, report_filename,
                              write_html)
from reporting.render import render_report_html


def _company(name, companies):
    return next(c for c in companies if c['name'] == name)


# ── Builder: figures EQUAL the metrics functions' outputs ─────────────────────

def test_builder_matches_metrics_for_rich_company(demo_db):
    companies = models.get_all_companies()
    nova = _company('NovaTech AI', companies)
    model = build_company_report_model(nova['id'])

    met = metrics.company_metrics_for(nova, models.get_rounds(nova['id']),
                                      models.get_cashflows(nova['id']))
    p = model['position']
    assert p['invested']['raw'] == pytest.approx(met['total_invested'])
    assert p['realized']['raw'] == pytest.approx(met['realized'])
    assert p['current_value']['raw'] == pytest.approx(met['current_value'])
    assert p['moic']['raw'] == pytest.approx(met['moic'])
    assert p['dpi']['raw'] == pytest.approx(met['dpi'])
    assert p['tvpi']['raw'] == pytest.approx(met['tvpi'])
    assert p['irr']['raw'] == pytest.approx(met['irr'], abs=1e-9)
    # formatted values come from the shared formatters
    assert p['moic']['fmt'] == F.fmt_multiple(met['moic'])


def test_builder_as_of_predates_the_exit(demo_db):
    """A report as of 2024-06-29 must show PRE-exit numbers for Wintex."""
    companies = models.get_all_companies()
    wintex = _company('Wintex Payments', companies)

    pre = build_company_report_model(wintex['id'], date(2024, 6, 29))
    post = build_company_report_model(wintex['id'])

    assert pre['position']['realized']['raw'] == pytest.approx(0)
    assert pre['position']['is_estimate'] is True   # no valuation yet then
    assert pre['position']['current_value']['raw'] == pytest.approx(7500)
    assert len(pre['ledger']['rows']) == 2          # the two investments

    assert post['position']['realized']['raw'] == pytest.approx(26520)
    assert post['position']['current_value']['raw'] == pytest.approx(0)
    assert post['position']['dpi']['raw'] == pytest.approx(26520 / 7500)


def test_builder_journal_and_valuation_rows(demo_db):
    companies = models.get_all_companies()
    nova = _company('NovaTech AI', companies)
    model = build_company_report_model(nova['id'])
    assert len(model['thesis']['journal']) == 2
    assert model['valuations']['rows'], 'nova has valuation history'
    assert model['appendix']['footnotes'], 'footnotes come from metrics'
    assert metrics.FOOTNOTE_MOIC in model['appendix']['footnotes']


# ── Render ────────────────────────────────────────────────────────────────────

def test_rendered_html_has_anchors_and_figures(demo_db):
    companies = models.get_all_companies()
    nova = _company('NovaTech AI', companies)
    model = build_company_report_model(nova['id'])
    images = build_company_chart_images(model)
    html = render_report_html(model, images)

    for anchor in ('position', 'valuations', 'rounds', 'ledger',
                   'ownership', 'thesis', 'appendix', 'ai-narrative'):
        assert f'name="{anchor}"' in html, anchor
    assert 'NovaTech AI' in html
    assert 'CONFIDENTIAL' in html
    assert model['position']['moic']['fmt'] in html
    # appendix strings come from metrics.py — single source
    assert metrics.FOOTNOTE_MOIC.split('.')[0] in html
    assert 'All figures in' in html


def test_minimal_company_skips_empty_sections(temp_db):
    cid = models.add_company('Bare Minimum AB')
    models.add_round(cid, 'Seed', '2024-01-01', 500)
    model = build_company_report_model(cid)
    html = render_report_html(model)
    assert 'Valuation development' not in html   # no valuations
    assert 'Documents on file' not in html       # no documents
    assert 'Thesis' not in html                  # no thesis, no journal
    assert 'Round history' in html
    assert '>None<' not in html and 'None</td>' not in html
    assert 'n/a' in html                         # honest, not blank


def test_write_html_is_a_single_portable_file(demo_db, tmp_path):
    companies = models.get_all_companies()
    nova = _company('NovaTech AI', companies)
    model = build_company_report_model(nova['id'])
    images = build_company_chart_images(model)
    html = render_report_html(model, images)
    path = write_html(str(tmp_path / 'r.html'), html, images)
    text = open(path, encoding='utf-8').read()
    assert 'data:image/png;base64,' in text
    assert 'src="chart-valuation"' not in text, 'placeholder resolved'
    assert 'http://' not in text and 'https://' not in text
    assert os.path.getsize(path) > 20_000, 'chart image embedded'


def test_write_pdf_plausible(demo_db, tmp_path, qtbot):
    """Size heuristic (documented): a one-company A4 report with an
    embedded chart is far larger than an empty PDF skeleton (~2 KB);
    we require > 10 KB and the PDF magic header."""
    companies = models.get_all_companies()
    nova = _company('NovaTech AI', companies)
    out = generate_company_report(nova['id'], formats=('pdf',),
                                  out_dir=str(tmp_path))
    assert len(out) == 1 and out[0].endswith('.pdf')
    with open(out[0], 'rb') as f:
        head = f.read(5)
    assert head == b'%PDF-'
    assert os.path.getsize(out[0]) > 10_000


def test_generate_both_formats_and_filenames(demo_db, tmp_path):
    companies = models.get_all_companies()
    dp = _company('DataPulse', companies)
    out = generate_company_report(dp['id'], as_of=date(2026, 1, 2),
                                  formats=('html',),
                                  out_dir=str(tmp_path))
    assert os.path.basename(out[0]) == 'DataPulse_2026-01-02.html'


@pytest.mark.parametrize('name,expected_stem', [
    ('Weird/Co: AB "Ltd"', 'WeirdCo_AB_Ltd'),
    ('  spaces   everywhere  ', 'spaces_everywhere'),
    ('***', 'company'),
    ('Ångström & Söner', 'Ångström_Söner'),
])
def test_filename_sanitization(name, expected_stem):
    assert report_filename(name, date(2026, 1, 2), 'pdf') == \
        f'{expected_stem}_2026-01-02.pdf'
