"""Report Center: every report — single or batch — from one place.
Company / Portfolio / Entity types plus batch modes (all companies /
all entities). Routes through the same reporting.export functions as the
per-company dialog; choices remembered in QSettings. Output folder rules
match ui/report_dialog.py (never default inside the repo/app dir)."""

from __future__ import annotations

import os
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QDialogButtonBox, QDateEdit,
    QCheckBox, QRadioButton, QComboBox, QProgressDialog,
)
from PyQt6.QtCore import QDate, QSettings, Qt, QUrl
from PyQt6.QtGui import QDesktopServices

import metrics
import models
from ui.report_dialog import default_reports_dir, _inside_app_or_repo
from ui.styles import MUTED

TYPES = [
    ('portfolio', 'Portfolio (all holdings)'),
    ('entity', 'Entity (one family member)'),
    ('company', 'Single company'),
    ('all_entities', 'Batch: every entity'),
    ('all_companies', 'Batch: every company'),
]


class ReportCenter(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Report Center")
        self.setMinimumWidth(520)
        s = QSettings()

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.type_edit = QComboBox()
        for key, label in TYPES:
            self.type_edit.addItem(label, key)
        idx = self.type_edit.findData(s.value('reports/center_type',
                                              'portfolio'))
        if idx >= 0:
            self.type_edit.setCurrentIndex(idx)
        self.type_edit.currentIndexChanged.connect(self._type_changed)
        form.addRow("Report type", self.type_edit)

        self.entity_edit = QComboBox()
        for e in models.get_entities():
            self.entity_edit.addItem(e)
        form.addRow("Entity", self.entity_edit)

        self.company_edit = QComboBox()
        for c in models.get_all_companies():
            self.company_edit.addItem(c['name'], c['id'])
        form.addRow("Company", self.company_edit)

        self.as_of_edit = QDateEdit(QDate.currentDate())
        self.as_of_edit.setDisplayFormat("yyyy-MM-dd")
        self.as_of_edit.setCalendarPopup(True)
        form.addRow("Figures as of", self.as_of_edit)

        prev_q = metrics.previous_quarter_end(date.today())
        self.compare_check = QCheckBox(
            f"Compare to previous quarter-end ({prev_q.isoformat()})")
        self.compare_check.setChecked(True)
        form.addRow("", self.compare_check)

        fmt_row = QHBoxLayout()
        self.rb_html = QRadioButton("HTML")
        self.rb_pdf = QRadioButton("PDF")
        self.rb_both = QRadioButton("Both")
        saved_fmt = s.value('reports/center_format', 'pdf')
        {'html': self.rb_html, 'pdf': self.rb_pdf,
         'both': self.rb_both}.get(saved_fmt, self.rb_pdf).setChecked(True)
        for rb in (self.rb_html, self.rb_pdf, self.rb_both):
            fmt_row.addWidget(rb)
        fmt_row.addStretch()
        form.addRow("Format", fmt_row)

        folder = s.value('reports/folder', '') or default_reports_dir()
        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit(folder)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(browse)
        form.addRow("Output folder", dir_row)

        layout.addLayout(form)
        note = QLabel("Reports contain real financial data — keep them "
                      "out of shared or synced project folders.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED}; font-size:9pt;")
        layout.addWidget(note)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Create")
        btns.accepted.connect(self._create)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self._type_changed()

    # ── helpers ───────────────────────────────────────────────────────────

    def _type_changed(self):
        t = self.type_edit.currentData()
        self.entity_edit.setEnabled(t == 'entity')
        self.company_edit.setEnabled(t == 'company')
        self.compare_check.setEnabled(t in ('portfolio', 'entity',
                                            'all_entities'))

    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "Choose output folder", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def _formats(self):
        if self.rb_both.isChecked():
            return ('html', 'pdf')
        if self.rb_html.isChecked():
            return ('html',)
        return ('pdf',)

    # ── run ───────────────────────────────────────────────────────────────

    def _create(self):
        out_dir = self.dir_edit.text().strip() or default_reports_dir()
        if _inside_app_or_repo(out_dir):
            if QMessageBox.warning(
                    self, "Risky folder",
                    "That folder is inside the app/project directory — "
                    "generated reports contain real data and do not "
                    "belong there.\nUse it anyway?",
                    QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                return

        t = self.type_edit.currentData()
        qd = self.as_of_edit.date()
        as_of = date(qd.year(), qd.month(), qd.day())
        compare = (metrics.previous_quarter_end(as_of)
                   if (self.compare_check.isChecked()
                       and self.compare_check.isEnabled()) else None)
        formats = self._formats()

        from reporting import export as rex
        progress = QProgressDialog("Generating reports…", "Cancel", 0,
                                   100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(400)
        cancelled = {'flag': False}

        def tick(i, n, name):
            progress.setMaximum(n)
            progress.setValue(i)
            progress.setLabelText(f"{i}/{n}  {name}")
            if progress.wasCanceled():
                cancelled['flag'] = True
                raise KeyboardInterrupt

        try:
            if t == 'portfolio':
                written = rex.generate_portfolio_report(
                    None, as_of, compare, formats=formats,
                    out_dir=out_dir)
            elif t == 'entity':
                written = rex.generate_portfolio_report(
                    self.entity_edit.currentText(), as_of, compare,
                    formats=formats, out_dir=out_dir)
            elif t == 'company':
                written = rex.generate_company_report(
                    self.company_edit.currentData(), as_of=as_of,
                    formats=formats, out_dir=out_dir)
            elif t == 'all_entities':
                written = rex.generate_all_entity_reports(
                    as_of=as_of, compare_to=compare, formats=formats,
                    out_dir=out_dir, progress=tick)
            else:
                written = rex.generate_all_company_reports(
                    as_of=as_of, formats=formats, out_dir=out_dir,
                    progress=tick)
        except KeyboardInterrupt:
            progress.close()
            QMessageBox.information(self, "Cancelled",
                                    "Report generation was cancelled.")
            return
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Report failed", str(e))
            return
        progress.close()

        s = QSettings()
        s.setValue('reports/folder', out_dir)
        s.setValue('reports/center_type', t)
        s.setValue('reports/center_format',
                   'both' if self.rb_both.isChecked()
                   else 'html' if self.rb_html.isChecked() else 'pdf')

        box = QMessageBox(self)
        box.setWindowTitle("Reports created")
        box.setText(f"{len(written)} file"
                    f"{'s' if len(written) != 1 else ''} written to:\n"
                    f"{out_dir}")
        open_folder = box.addButton("Open folder",
                                    QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() == open_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(out_dir))
        self.accept()
