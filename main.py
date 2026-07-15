import sys
import os

# When running as a PyInstaller .exe, set cwd to the exe's directory so that
# investments.db and the documents/ folder are created next to the executable.
if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPolygonF
import models
from ui.main_window import MainWindow
from ui.styles import QSS


def _make_app_icon() -> QIcon:
    """Draw the app icon in code: blue rounded square with a rising chart line."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = size
        # Rounded-square background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#3B82F6")))
        p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.22, s * 0.22)

        # Rising chart line with an arrowhead
        pen = QPen(QColor("#FFFFFF"))
        pen.setWidthF(max(1.5, s * 0.09))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        pts = [
            QPointF(s * 0.18, s * 0.74),
            QPointF(s * 0.40, s * 0.54),
            QPointF(s * 0.55, s * 0.63),
            QPointF(s * 0.80, s * 0.30),
        ]
        for a, b in zip(pts, pts[1:]):
            p.drawLine(a, b)

        # Arrowhead at the end of the line
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        ah = s * 0.16
        tip = QPointF(s * 0.84, s * 0.25)
        p.drawPolygon(QPolygonF([
            tip,
            QPointF(tip.x() - ah, tip.y() + ah * 0.15),
            QPointF(tip.x() - ah * 0.15, tip.y() + ah),
        ]))
        p.end()
        icon.addPixmap(pm)
    return icon


def main():
    models.init_db()

    # routine safety net: daily backup with rotation (see backups.py);
    # pre-migration backups happen inside init_db's migration runner
    try:
        import backups
        backups.routine_backup_if_due()
    except Exception:
        pass  # a failed backup must never block the app from opening

    # Give the process its own taskbar identity on Windows so the custom
    # icon shows in the taskbar instead of the generic Python icon.
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "FamilyInvestmentTracker.InvestmentTracker")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Investment Tracker")
    app.setOrganizationName("FamilyInvestmentTracker")
    app.setWindowIcon(_make_app_icon())
    app.setStyleSheet(QSS)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
