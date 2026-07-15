"""Report export dialog. Output folder defaults to the user's
Documents/<AppName> Reports — NEVER inside the repo or app directory
(reports contain real data; CLAUDE.md: PRIVACY). Remembered in QSettings."""

from __future__ import annotations

import os
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QDialogButtonBox, QDateEdit,
    QCheckBox, QRadioButton,
)
from PyQt6.QtCore import QDate, QSettings, QStandardPaths, QUrl
from PyQt6.QtGui import QDesktopServices

import models
from version import APP_NAME
from ui.styles import MUTED

SECTIONS = [
    ('position', 'Position summary', True),
    ('valuations', 'Valuation development', True),
    ('rounds', 'Round history', True),
    ('ledger', 'Cash-flow ledger', True),
    ('ownership', 'Ownership & shares', True),
    ('thesis', 'Thesis & journal', True),
    ('documents', 'Documents on file', True),
    ('appendix', 'Methodology & assumptions', True),
]


def default_reports_dir() -> str:
    docs = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation)
    return os.path.join(docs, f'{APP_NAME} Reports')


def _inside_app_or_repo(path: str) -> bool:
    app_dir = os.path.normcase(os.path.abspath(models._base()))
    p = os.path.normcase(os.path.abspath(path))
    return p.startswith(app_dir)


class ReportDialog(QDialog):
    def __init__(self, parent=None, company_id=None):
        super().__init__(parent)
        self._cid = company_id
        c = models.get_company(company_id)
        self._company_name = c['name'] if c else '?'
        self.setWindowTitle(f"Report — {self._company_name}")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.as_of_edit = QDateEdit(QDate.currentDate())
        self.as_of_edit.setDisplayFormat("yyyy-MM-dd")
        self.as_of_edit.setCalendarPopup(True)
        form.addRow("Figures as of", self.as_of_edit)

        self._section_boxes = {}
        for key, label, default in SECTIONS:
            cb = QCheckBox(label)
            cb.setChecked(default)
            self._section_boxes[key] = cb
            form.addRow("Sections" if key == 'position' else "", cb)

        fmt_row = QHBoxLayout()
        self.rb_html = QRadioButton("HTML")
        self.rb_pdf = QRadioButton("PDF")
        self.rb_both = QRadioButton("Both")
        self.rb_both.setChecked(True)
        for rb in (self.rb_html, self.rb_pdf, self.rb_both):
            fmt_row.addWidget(rb)
        fmt_row.addStretch()
        form.addRow("Format", fmt_row)

        settings = QSettings()
        folder = settings.value('reports/folder', '') or default_reports_dir()
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
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Create report")
        btns.accepted.connect(self._create)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "Choose output folder", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

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
        formats = (('html', 'pdf') if self.rb_both.isChecked()
                   else ('pdf',) if self.rb_pdf.isChecked()
                   else ('html',))
        sections = {k for k, cb in self._section_boxes.items()
                    if cb.isChecked()}
        qd = self.as_of_edit.date()
        as_of = date(qd.year(), qd.month(), qd.day())

        from reporting.export import generate_company_report
        try:
            written = generate_company_report(
                self._cid, as_of=as_of, sections=sections,
                formats=formats, out_dir=out_dir)
        except Exception as e:
            QMessageBox.critical(self, "Report failed", str(e))
            return

        QSettings().setValue('reports/folder', out_dir)
        box = QMessageBox(self)
        box.setWindowTitle("Report created")
        box.setText("Created:\n" + "\n".join(
            os.path.basename(p) for p in written))
        open_file = box.addButton("Open file",
                                  QMessageBox.ButtonRole.AcceptRole)
        open_folder = box.addButton("Open folder",
                                    QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() == open_file and written:
            QDesktopServices.openUrl(QUrl.fromLocalFile(written[0]))
        elif box.clickedButton() == open_folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(out_dir))
        self.accept()
