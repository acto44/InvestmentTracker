"""First-run guided tour: the family stork flies between key UI elements
and explains each one in a speech bubble.

Self-contained by design — the rest of the app only mounts it:
main.py calls maybe_start_tour() once after the window shows, and the
? menu's "Show me around" calls start_tour(). Nothing here mutates data.

Steps live in TOUR_STEPS as plain config (title/text/side/resolver) so
copy can be edited and stops reordered without touching the animation
code. Resolvers run lazily every time a step shows, because the
dashboard rebuilds its widgets on every refresh — steps whose target is
missing are skipped gracefully.

Assets: ui/assets/stork/*.png (bundled via the spec's ui/assets datas,
loaded through resource_path). If they are missing the tour refuses to
start, mirroring the _HeroArt renders-nothing rule.

State: QSettings 'tour_seen' — the tour auto-starts exactly once.
Reduced motion: honors the Windows client-area-animation setting
(flights become fades). Tests set TourOverlay.instant = True.
"""
import os

from PyQt6.QtCore import (QEasingCurve, QEvent, QPoint, QPointF, QRect,
                          QRectF, QSettings, QSize, Qt, QTimer,
                          QVariantAnimation)
from PyQt6.QtGui import (QColor, QPainter, QPainterPath, QPixmap,
                         QPolygonF, QTransform)
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QVBoxLayout, QWidget)

from resources import resource_path
from ui.styles import ACCENT, ACCENT_HOVER, CARD, MUTED, TEXT

STORK_W = 120          # on-screen sprite size (source PNGs are 400px)
SPOT_PAD = 8           # spotlight padding around the target
SPOT_RADIUS = 10
FLAP_MS = 150          # wing-frame alternation while flying
BUBBLE_W = 330


# ── Tour stops ────────────────────────────────────────────────────────────
# Each: key, title, text (max two short sentences), preferred stork side,
# resolve(window) -> widget | [widgets] | None, optional tab index.
# 'content' (window -> (widget, title, text)) overrides for dynamic steps.

def _ai_step_content(win):
    """The Ask-AI button exists only while the AI master switch is on
    (CLAUDE.md invariant) — when it is off, the stork points at Settings
    and explains where the switch lives instead."""
    import ai
    btn = getattr(win, '_ai_rail_btn', None)
    if ai.is_ai_enabled() and btn is not None:
        return (btn, "AI assistant",
                "Ask questions about the portfolio, or generate company "
                "summaries and risk flags. Nothing is sent anywhere "
                "without your approval — you always see the exact data "
                "first.")
    return (getattr(win, '_settings_btn', None), "AI assistant (off)",
            "An optional AI helper can summarize companies, flag risks "
            "and answer questions — it is switched off by default. Turn "
            "it on under Settings → AI whenever you like.")


TOUR_STEPS = [
    dict(key='nav', side='right', title="Getting around",
         text="These buttons switch views — Dashboard for the big "
              "picture, Portfolio for every detail, plus Companies and "
              "Transactions.",
         resolve=lambda w: list(getattr(w, '_nav_buttons', {}).values())
         or None),
    dict(key='chart', tab=0, side='below', title="Portfolio value",
         text="The whole portfolio's value over time. The small tabs "
              "switch to gain, money multiple (MOIC) or yearly return "
              "(IRR).",
         resolve=lambda w: w.findChild(QFrame, 'ChartCard')),
    dict(key='kpi', tab=0, side='above', title="The key numbers",
         text="What the family put in, what it is worth today, and what "
              "has already come back. Hover any card for a plain "
              "explanation.",
         resolve=lambda w: w.findChild(QWidget, 'KpiRow')),
    dict(key='top5', tab=0, side='right', title="Biggest holdings",
         text="Your five largest investments at a glance. Click the "
              "arrow on a row to open that company's full page.",
         resolve=lambda w: w.findChild(QFrame, 'Top5Card')),
    dict(key='rail', tab=0, side='left', title="Activity & alerts",
         text="Recent changes are listed here, and companies whose "
              "valuation is getting old are flagged so nothing goes "
              "stale.",
         resolve=lambda w: (w.dashboard.findChildren(QFrame, 'RailCard')
                            or None) if hasattr(w, 'dashboard') else None),
    dict(key='reports', side='right', title="Reports",
         text="Create polished PDF or web reports — for one company, one "
              "family member, or the whole portfolio. Perfect for "
              "sharing.",
         resolve=lambda w: getattr(w, '_reports_btn', None)),
    dict(key='add', side='below', title="Add a company",
         text="A new investment starts here (or press Ctrl+N) — then "
              "record rounds, valuations and cash flows on its page.",
         resolve=lambda w: getattr(w, '_add_btn', None)),
    dict(key='ai', side='right', content=_ai_step_content,
         resolve=lambda w: _ai_step_content(w)[0]),
]

WELCOME_TITLE = "Hi there!"
WELCOME_TEXT = ("I'm the family stork — I look after the nest egg. "
                "Want a quick look around? It takes under a minute.")
FAREWELL_TEXT = ("That's the tour! Replay it anytime from the ? menu "
                 "in the top right.")


# ── Helpers ───────────────────────────────────────────────────────────────

def _load_frames():
    """All poses at sprite size; missing directions are mirrored, as the
    art set only ships right-flight, left-flight, right-climb and
    left-flare."""
    def load(name):
        pm = QPixmap(resource_path(os.path.join('ui', 'assets', 'stork',
                                                name)))
        if pm.isNull():
            return pm
        return pm.scaledToWidth(
            STORK_W, Qt.TransformationMode.SmoothTransformation)

    def mirror(pm):
        if pm.isNull():
            return pm
        return pm.transformed(QTransform().scale(-1, 1),
                              Qt.TransformationMode.SmoothTransformation)

    r_a = load('stork-right-up.png')
    r_b = load('stork-right-down.png')
    r_climb = load('stork-right-climb.png')
    l_a = load('stork-left-up.png')
    l_flare = load('stork-left-flare.png')
    frames = {
        'right_a': r_a, 'right_b': r_b,
        'left_a': l_a, 'left_b': mirror(r_b),
        'right_climb': r_climb, 'left_climb': mirror(r_climb),
        'left_flare': l_flare, 'right_flare': mirror(l_flare),
    }
    if any(pm.isNull() for pm in frames.values()):
        return None
    return frames


def _reduced_motion():
    """Windows equivalent of prefers-reduced-motion: the user disabled
    client-area animations in accessibility settings."""
    try:
        import ctypes
        v = ctypes.c_int(1)
        ctypes.windll.user32.SystemParametersInfoW(  # SPI_GETCLIENTAREAANIMATION
            0x1042, 0, ctypes.byref(v), 0)
        return v.value == 0
    except Exception:
        return False


def _scroll_area_of(widget):
    p = widget.parentWidget()
    while p is not None:
        if isinstance(p, QScrollArea):
            return p
        p = p.parentWidget()
    return None


def _scroll_into_view(widgets):
    """Center the targets' union in their scroll area (if any) — for
    multi-widget stops (rail cards) that shows the whole group, not just
    the first card."""
    area = _scroll_area_of(widgets[0])
    if area is None or area.widget() is None:
        return
    contents = area.widget()
    union = None
    for w in widgets:
        r = QRect(w.mapTo(contents, QPoint(0, 0)), w.size())
        union = r if union is None else union.united(r)
    bar = area.verticalScrollBar()
    if bar is not None:
        bar.setValue(union.center().y() - area.viewport().height() // 2)


# ── Speech bubble ─────────────────────────────────────────────────────────

class _Bubble(QFrame):
    """Rounded speech bubble with a pointer toward the stork. Two modes:
    welcome (No thanks / Show me around) and step (Back · n of N · Next,
    with an always-visible Skip)."""

    POINTER = 12

    def __init__(self, overlay):
        super().__init__(overlay)
        self._overlay = overlay
        self._anchor = None          # stork center, overlay coords
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(BUBBLE_W)

        lay = QVBoxLayout(self)
        self._lay = lay
        lay.setContentsMargins(18, 14, 18, 12)
        lay.setSpacing(6)

        self._title = QLabel()
        self._title.setStyleSheet(
            f"color:{TEXT}; font-size:11pt; font-weight:700; "
            f"background:transparent; border:none;")
        lay.addWidget(self._title)

        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setStyleSheet(
            f"color:{MUTED}; font-size:9.5pt; background:transparent; "
            f"border:none;")
        lay.addWidget(self._text)
        lay.addSpacing(4)

        def btn(label, slot, primary=False, subtle=False):
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if primary:
                b.setStyleSheet(
                    f"QPushButton {{ background:{ACCENT}; color:white; "
                    f"border:none; border-radius:7px; padding:6px 14px; "
                    f"font-weight:600; font-size:9pt; }} "
                    f"QPushButton:hover {{ background:{ACCENT_HOVER}; }}")
            elif subtle:
                b.setStyleSheet(
                    f"QPushButton {{ background:transparent; "
                    f"color:{MUTED}; border:none; padding:6px 2px; "
                    f"font-size:8.5pt; text-decoration:underline; }} "
                    f"QPushButton:hover {{ color:{TEXT}; }}")
            else:
                b.setStyleSheet(
                    f"QPushButton {{ background:transparent; "
                    f"color:{TEXT}; border:1px solid "
                    f"rgba(255,255,255,0.18); border-radius:7px; "
                    f"padding:6px 12px; font-size:9pt; }} "
                    f"QPushButton:hover {{ "
                    f"background:rgba(255,255,255,0.06); }}")
            b.clicked.connect(slot)
            return b

        # step controls
        row = QHBoxLayout()
        row.setSpacing(8)
        self._skip = btn("Skip tour", overlay.finish, subtle=True)
        row.addWidget(self._skip)
        row.addStretch()
        self._back = btn("‹ Back", overlay.back)
        row.addWidget(self._back)
        self._dots = QLabel()
        self._dots.setStyleSheet(
            f"color:{MUTED}; font-size:8.5pt; background:transparent; "
            f"border:none;")
        row.addWidget(self._dots)
        self._next = btn("Next ›", overlay.next, primary=True)
        row.addWidget(self._next)
        lay.addLayout(row)

        # welcome controls
        wrow = QHBoxLayout()
        wrow.setSpacing(8)
        wrow.addStretch()
        self._no = btn("No thanks", overlay.finish)
        wrow.addWidget(self._no)
        self._yes = btn("Show me around", overlay.start_steps,
                        primary=True)
        wrow.addWidget(self._yes)
        lay.addLayout(wrow)

    def set_welcome(self):
        self._title.setText(WELCOME_TITLE)
        self._text.setText(WELCOME_TEXT)
        for w in (self._skip, self._back, self._dots, self._next):
            w.hide()
        self._no.show()
        self._yes.show()
        self.adjustSize()

    def set_step(self, title, text, idx, total, last):
        self._title.setText(title)
        self._text.setText(text)
        self._no.hide()
        self._yes.hide()
        for w in (self._skip, self._back, self._dots, self._next):
            w.show()
        self._back.setEnabled(idx > 0)
        self._dots.setText(f"{idx + 1} of {total}")
        self._next.setText("Done ✓" if last else "Next ›")
        self.adjustSize()

    def set_farewell(self):
        self._title.setText("Enjoy!")
        self._text.setText(FAREWELL_TEXT)
        for w in (self._skip, self._back, self._dots, self._next,
                  self._no, self._yes):
            w.hide()
        self.adjustSize()

    def place_near(self, stork_rect, avoid_rect):
        """Beside the stork, off the spotlight, inside the window; the
        pointer is aimed at the stork afterwards."""
        area = self._overlay.rect().adjusted(8, 8, -8, -8)
        self.adjustSize()
        sz = self.size()
        gap = 14
        cands = [
            QPoint(stork_rect.right() + gap,
                   stork_rect.center().y() - sz.height() // 2),
            QPoint(stork_rect.left() - gap - sz.width(),
                   stork_rect.center().y() - sz.height() // 2),
            QPoint(stork_rect.center().x() - sz.width() // 2,
                   stork_rect.bottom() + gap),
            QPoint(stork_rect.center().x() - sz.width() // 2,
                   stork_rect.top() - gap - sz.height()),
        ]
        # prefer the side away from the spotlighted target
        if avoid_rect is not None:
            if avoid_rect.center().x() <= stork_rect.center().x():
                cands[0], cands[1] = cands[0], cands[1]     # right first
            else:
                cands[0], cands[1] = cands[1], cands[0]     # left first
        pos = None
        for c in cands:
            r = QRect(c, sz)
            if area.contains(r) and (avoid_rect is None
                                     or not r.intersects(avoid_rect)):
                pos = c
                break
        if pos is None:                       # fall back: allow overlap
            for c in cands:
                if area.contains(QRect(c, sz)):
                    pos = c
                    break
        if pos is None:                       # last resort: clamp
            pos = QPoint(
                max(area.left(), min(cands[0].x(),
                                     area.right() - sz.width())),
                max(area.top(), min(cands[0].y(),
                                    area.bottom() - sz.height())))
        self.move(pos)
        self._anchor = stork_rect.center()
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(body, 12, 12)
        if self._anchor is not None:
            a = self.mapFromParent(self._anchor)
            c = self.rect().center()
            # pointer sticks out of the edge facing the stork
            if abs(a.x() - c.x()) * self.height() > \
                    abs(a.y() - c.y()) * self.width():
                edge_x = body.left() if a.x() < c.x() else body.right()
                y = max(body.top() + 18,
                        min(float(a.y()), body.bottom() - 18))
                out = -self.POINTER if a.x() < c.x() else self.POINTER
                tri = QPolygonF([QPointF(edge_x, y - 9),
                                 QPointF(edge_x, y + 9),
                                 QPointF(edge_x + out, y)])
            else:
                edge_y = body.top() if a.y() < c.y() else body.bottom()
                x = max(body.left() + 18,
                        min(float(a.x()), body.right() - 18))
                out = -self.POINTER if a.y() < c.y() else self.POINTER
                tri = QPolygonF([QPointF(x - 9, edge_y),
                                 QPointF(x + 9, edge_y),
                                 QPointF(x, edge_y + out)])
            path.addPolygon(tri)
            path = path.simplified()
        p.setPen(QColor(255, 255, 255, 40))
        p.setBrush(QColor(CARD))
        p.drawPath(path)


# ── The overlay ───────────────────────────────────────────────────────────

class TourOverlay(QWidget):
    """Full-window veil with a spotlight hole, the stork sprite and the
    bubble. Blocks stray clicks; Esc exits, Enter/→ advance, ← goes
    back."""

    instant = False        # tests: no animations, no timers

    def __init__(self, window):
        super().__init__(window)
        self._win = window
        self._frames = _load_frames()
        self._steps = []
        self._idx = -1                 # -1 = welcome
        self._spot = None              # QRect, window coords
        self._anim = None
        self._closing = False
        self._reduced = self.instant or _reduced_motion()

        self.setGeometry(window.rect())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._stork = QLabel(self)
        self._stork.setFixedSize(STORK_W, STORK_W)
        self._stork.setStyleSheet("background:transparent; border:none;")
        self._stork.hide()

        self._flap = QTimer(self)
        self._flap.setInterval(FLAP_MS)
        self._flap.timeout.connect(self._on_flap)
        self._flap_frame = 0
        self._dir = 'right'

        self._bubble = _Bubble(self)
        self._bubble.hide()

        window.installEventFilter(self)

    # ── public API ────────────────────────────────────────────────────

    def begin(self):
        """Fly in from off-screen and offer the tour."""
        self._steps = [s for s in TOUR_STEPS if self._resolve(s)[0]]
        if not self._steps or self._frames is None:
            self.deleteLater()
            return
        self.show()
        self.raise_()
        self.setFocus()
        w, h = self.width(), self.height()
        self._stork.move(w + 20, int(h * 0.16))
        self._stork.show()
        end = QPoint(int(w * 0.56), int(h * 0.28))
        self._fly_to(end, pose='climb', then=self._welcome_arrived)

    def start_steps(self):
        self._goto(0)

    def next(self):
        if self._idx + 1 >= len(self._steps):
            self.finish(completed=True)
        else:
            self._goto(self._idx + 1)

    def back(self):
        if self._idx > 0:
            self._goto(self._idx - 1, backward=True)

    def finish(self, completed=False):
        """Mark seen and leave — with a flourish when the tour was
        actually completed, immediately otherwise."""
        if self._closing:
            return
        self._closing = True
        QSettings("FamilyInvestmentTracker",
                  "InvestmentTracker").setValue('tour_seen', 1)
        self._stop_anim()
        self._spot = None
        self.update()
        if completed and not self._reduced:
            self._bubble.set_farewell()
            self._bubble.place_near(self._stork.geometry(), None)
            off = QPoint(self.width() + 40, -STORK_W - 40)
            self._fly_to(off, pose='climb', then=self._close)
        else:
            self._close()

    # ── internals ─────────────────────────────────────────────────────

    def _close(self):
        self._flap.stop()
        self._win.removeEventFilter(self)
        self.hide()
        self.deleteLater()

    def _resolve(self, step):
        """-> (widget-or-list-or-None, title, text)."""
        if 'content' in step:
            target, title, text = step['content'](self._win)
        else:
            target = step['resolve'](self._win)
            title, text = step['title'], step['text']
        if isinstance(target, list) and not target:
            target = None
        return target, title, text

    def _target_rect(self, target):
        widgets = target if isinstance(target, list) else [target]
        rect = None
        for w in widgets:
            r = QRect(w.mapTo(self._win, QPoint(0, 0)), w.size())
            rect = r if rect is None else rect.united(r)
        return rect

    def _goto(self, i, backward=False):
        if self._closing:
            return
        self._stop_anim()
        self._bubble.hide()
        step = None
        target = title = text = None
        while 0 <= i < len(self._steps):
            step = self._steps[i]
            tab = step.get('tab')
            if tab is not None and hasattr(self._win, 'tabs') \
                    and self._win.tabs.currentIndex() != tab:
                self._win.tabs.setCurrentIndex(tab)
            target, title, text = self._resolve(step)
            if target is not None:
                break
            i += -1 if backward else 1        # target gone: skip the stop
        if not (0 <= i < len(self._steps)) or target is None:
            self.finish(completed=not backward)
            return
        self._idx = i
        widgets = target if isinstance(target, list) else [target]
        _scroll_into_view(widgets)
        rect = self._target_rect(target)
        self._spot = self._clip_spot(
            rect.adjusted(-SPOT_PAD, -SPOT_PAD, SPOT_PAD, SPOT_PAD),
            widgets[0])
        self.update()
        self._pending = (title, text)
        self._fly_to(self._landing_point(self._spot, step.get('side')),
                     then=self._arrive)
        self.setFocus()

    def _clip_spot(self, spot, widget):
        """Targets taller than the view (e.g. the stacked right rail):
        spotlight only what is actually visible — the scroll viewport
        when the target scrolls, the window otherwise. Without this the
        hole would punch through the top bar and status bar too."""
        clip = self.rect().adjusted(0, 0, 0, -4)
        area = _scroll_area_of(widget)
        if area is not None:
            vp = area.viewport()
            clip = clip.intersected(
                QRect(vp.mapTo(self._win, QPoint(0, 0)), vp.size()))
        return spot.intersected(clip)

    def _landing_point(self, rect, side):
        s = STORK_W
        gap = 20
        area = self.rect().adjusted(6, 6, -6, -6)
        cands = {
            'right': QPoint(rect.right() + gap,
                            rect.center().y() - s // 2),
            'left': QPoint(rect.left() - gap - s,
                           rect.center().y() - s // 2),
            'above': QPoint(rect.center().x() - s // 2,
                            rect.top() - gap - s),
            'below': QPoint(rect.center().x() - s // 2,
                            rect.bottom() + gap),
        }
        order = [side] if side in cands else []
        order += [k for k in ('right', 'left', 'below', 'above')
                  if k not in order]
        for k in order:
            if area.contains(QRect(cands[k], QSize(s, s))):
                return cands[k]
        c = cands.get(side or 'right', cands['right'])
        return QPoint(max(area.left(), min(c.x(), area.right() - s)),
                      max(area.top(), min(c.y(), area.bottom() - s)))

    def _arrive(self):
        """Landed at a stop: flare briefly, face the target, speak."""
        face = 'right'
        if self._spot is not None and \
                self._spot.center().x() < self._stork.geometry().center().x():
            face = 'left'
        self._set_frame(f'{face}_flare')
        show = self._show_bubble_at_stop
        if self._reduced:
            self._set_frame(f'{face}_a')
            show()
        else:
            def settle():
                if self._closing:
                    return
                self._set_frame(f'{face}_a')
            QTimer.singleShot(360, settle)
            show()

    def _show_bubble_at_stop(self):
        title, text = self._pending
        self._bubble.set_step(title, text, self._idx, len(self._steps),
                              last=self._idx == len(self._steps) - 1)
        self._bubble.place_near(self._stork.geometry(), self._spot)
        self.setFocus()

    def _welcome_arrived(self):
        self._set_frame('left_flare')
        self._bubble.set_welcome()
        self._bubble.place_near(self._stork.geometry(), None)
        self.setFocus()

    # ── flight ────────────────────────────────────────────────────────

    def _fly_to(self, end: QPoint, pose='flap', then=None):
        start = self._stork.pos()
        self._dir = 'right' if end.x() >= start.x() else 'left'
        if self._reduced:
            self._stork.move(end)
            self._set_frame(f'{self._dir}_a')
            if then:
                then()
            return
        if pose == 'climb':
            self._set_frame(f'{self._dir}_climb')
            self._flap.stop()
        else:
            self._flap_frame = 0
            self._set_frame(f'{self._dir}_a')
            self._flap.start()
        p0 = QPointF(start)
        p1 = QPointF(end)
        dist = (p1 - p0).manhattanLength()
        dur = max(400, min(1200, int(dist * 0.7)))
        # gentle arc: control point lifted above the midpoint
        mid = QPointF((p0.x() + p1.x()) / 2,
                      (p0.y() + p1.y()) / 2 - max(50.0, dist * 0.15))
        anim = QVariantAnimation(self)
        anim.setDuration(dur)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        def at(t):
            u = 1.0 - t
            pt = p0 * (u * u) + mid * (2 * u * t) + p1 * (t * t)
            self._stork.move(int(pt.x()), int(pt.y()))

        anim.valueChanged.connect(at)

        def done():
            self._flap.stop()
            if then and not self._closing:
                then()
            elif then and self._closing and then == self._close:
                then()

        anim.finished.connect(done)
        self._anim = anim
        anim.start()

    def _stop_anim(self):
        if self._anim is not None:
            try:
                self._anim.finished.disconnect()
                self._anim.valueChanged.disconnect()
            except TypeError:
                pass
            self._anim.stop()
            self._anim = None
        self._flap.stop()

    def _on_flap(self):
        self._flap_frame ^= 1
        self._set_frame(
            f"{self._dir}_{'b' if self._flap_frame else 'a'}")

    def _set_frame(self, key):
        pm = self._frames.get(key) if self._frames else None
        if pm is not None and not pm.isNull():
            self._stork.setPixmap(pm)

    # ── events ────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        path.addRect(QRectF(self.rect()))
        if self._spot is not None:
            path.addRoundedRect(QRectF(self._spot),
                                SPOT_RADIUS, SPOT_RADIUS)
        p.fillPath(path, QColor(4, 8, 16, 186))

    def mousePressEvent(self, event):
        event.accept()                # the veil blocks stray clicks

    def keyPressEvent(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            self.finish()
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter,
                   Qt.Key.Key_Right, Qt.Key.Key_Space):
            if self._idx < 0:
                self.start_steps()
            else:
                self.next()
        elif k == Qt.Key.Key_Left:
            self.back()
        else:
            event.ignore()

    def eventFilter(self, obj, event):
        if obj is self._win and event.type() == QEvent.Type.Resize:
            self.setGeometry(self._win.rect())
            if self._idx >= 0 and not self._closing:
                self._reposition()
        return False

    def _reposition(self):
        """Window resized mid-tour: recompute everything, no flight."""
        step = self._steps[self._idx]
        target, title, text = self._resolve(step)
        if target is None:
            return
        widgets = target if isinstance(target, list) else [target]
        _scroll_into_view(widgets)
        rect = self._target_rect(target)
        self._spot = self._clip_spot(
            rect.adjusted(-SPOT_PAD, -SPOT_PAD, SPOT_PAD, SPOT_PAD),
            widgets[0])
        self._stop_anim()
        self._stork.move(self._landing_point(self._spot,
                                             step.get('side')))
        if self._bubble.isVisible():
            self._bubble.place_near(self._stork.geometry(), self._spot)
        self.update()


# ── Mounting ──────────────────────────────────────────────────────────────

def start_tour(window):
    """Start (or replay) the tour. Returns the overlay, or None if the
    assets are missing."""
    existing = getattr(window, '_tour_overlay', None)
    if existing is not None:
        try:
            if existing.isVisible():
                return existing
        except RuntimeError:
            pass                      # already deleted
    if _load_frames() is None:
        return None
    overlay = TourOverlay(window)
    window._tour_overlay = overlay
    overlay.begin()
    return overlay


def maybe_start_tour(window):
    """First launch only: auto-start once, then never again."""
    s = QSettings("FamilyInvestmentTracker", "InvestmentTracker")
    if s.value('tour_seen'):
        return None
    return start_tour(window)
