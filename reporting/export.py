"""Exporters: single portable HTML (base64 images) and PDF via
QTextDocument + QPrinter (the HTML subset in render.py is chosen for it).

The named image placeholders from render.py are resolved differently per
target: browsers get data: URIs; QTextDocument gets registered document
resources (data: URIs are unreliable there — see REPORT_STYLE_NOTES)."""

from __future__ import annotations

import base64
import os
import re
from datetime import date

import formatting as F
from reporting.builder import (build_company_report_model,
                               build_portfolio_report_model)
from reporting.charts import (build_company_chart_images,
                              build_portfolio_chart_images)
from reporting.render import (render_portfolio_report_html,
                              render_report_html)


def report_filename(company_name: str, as_of: date, ext: str) -> str:
    return f"{F.sanitize_filename(company_name)}_{as_of.isoformat()}.{ext}"


def _inline_images(html: str, images: dict) -> str:
    for name, png in images.items():
        b64 = base64.b64encode(png).decode('ascii')
        html = html.replace(f'src="{name}"',
                            f'src="data:image/png;base64,{b64}"')
    return html


def write_html(path: str, html: str, images: dict) -> str:
    """One portable file: every image inlined, no external references."""
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(_inline_images(html, images))
    return path


def write_pdf(path: str, html: str, images: dict) -> str:
    """A4 PDF via QTextDocument/QPrinter. Requires a Q(Gui)Application."""
    from PyQt6.QtCore import QUrl, QMarginsF
    from PyQt6.QtGui import QTextDocument, QImage, QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter

    doc = QTextDocument()
    for name, png in images.items():
        img = QImage.fromData(png)
        # display at half the pixel width: charts render at 2× for print
        doc.addResource(QTextDocument.ResourceType.ImageResource,
                        QUrl(name), img)
    doc.setHtml(html)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(path)
    layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                         QPageLayout.Orientation.Portrait,
                         QMarginsF(15, 12, 15, 12),
                         QPageLayout.Unit.Millimeter)
    printer.setPageLayout(layout)
    doc.print(printer)
    return path


def generate_portfolio_report(scope: str | None = None,
                              as_of: date | None = None,
                              compare_to: date | None = None,
                              sections=None, formats=('html',),
                              out_dir: str = '.') -> list:
    """Portfolio (scope=None) or entity (scope='<name>') report."""
    as_of = as_of or date.today()
    model = build_portfolio_report_model(scope, as_of, compare_to)
    images = build_portfolio_chart_images(model)
    html = render_portfolio_report_html(model, images, sections)
    os.makedirs(out_dir, exist_ok=True)
    stem = (f'Entity_{F.sanitize_filename(scope)}' if scope
            else 'Portfolio')
    written = []
    if 'html' in formats:
        p = os.path.join(out_dir, f'{stem}_{as_of.isoformat()}.html')
        written.append(write_html(p, html, images))
    if 'pdf' in formats:
        p = os.path.join(out_dir, f'{stem}_{as_of.isoformat()}.pdf')
        written.append(write_pdf(p, html, images))
    return written


def generate_all_company_reports(as_of=None, formats=('pdf',),
                                 out_dir='.', progress=None) -> list:
    """Batch: one report per company. progress(i, total, name) optional."""
    import models
    companies = models.get_all_companies()
    written = []
    for i, c in enumerate(companies, 1):
        if progress:
            progress(i, len(companies), c['name'])
        written.extend(generate_company_report(
            c['id'], as_of=as_of, formats=formats, out_dir=out_dir))
    return written


def generate_all_entity_reports(as_of=None, compare_to=None,
                                formats=('pdf',), out_dir='.',
                                progress=None) -> list:
    """Batch: one report per holding entity (entities come from the data,
    so a zero-holdings entity cannot occur here; direct calls with a
    stale scope string yield an honest empty report instead)."""
    import models
    entities = models.get_entities()
    written = []
    for i, e in enumerate(entities, 1):
        if progress:
            progress(i, len(entities), e)
        written.extend(generate_portfolio_report(
            scope=e, as_of=as_of, compare_to=compare_to,
            formats=formats, out_dir=out_dir))
    return written


def attach_ai_outputs(model: dict, company_id, include_ai) -> dict:
    """Attach PERSISTED ai_outputs rows (session 8) to a company report
    model. Reading rows is all this does — report export must NEVER
    trigger AI generation (tested with a provider call counter)."""
    import json

    import models
    keys = {'narrative': 'ai_narrative', 'risk_flags': 'ai_risk_flags'}
    for task in include_ai or ():
        row = models.get_ai_output(company_id, task)
        if row:
            model[keys[task]] = {
                'provider': row['provider'],
                'model': row['model'],
                'created_at': row['created_at'],
                'data': json.loads(row['response_json']),
            }
    return model


def generate_company_report(company_id, as_of: date | None = None,
                            sections=None, formats=('html',),
                            out_dir: str = '.', include_ai=()) -> list:
    """End-to-end: build → chart → render → write. Returns written paths.
    This is what the UI calls; sessions 6/8 add siblings, not rework.
    include_ai ⊆ ('narrative','risk_flags') renders the STORED outputs."""
    as_of = as_of or date.today()
    model = build_company_report_model(company_id, as_of)
    attach_ai_outputs(model, company_id, include_ai)
    images = build_company_chart_images(model)
    html = render_report_html(model, images, sections)
    os.makedirs(out_dir, exist_ok=True)
    written = []
    name = model['meta']['company_name']
    if 'html' in formats:
        p = os.path.join(out_dir, report_filename(name, as_of, 'html'))
        written.append(write_html(p, html, images))
    if 'pdf' in formats:
        p = os.path.join(out_dir, report_filename(name, as_of, 'pdf'))
        written.append(write_pdf(p, html, images))
    return written
