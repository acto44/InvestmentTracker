"""Guided-tour tests: step resolvers find their targets on demo data,
the full walkthrough runs headless, the first-run flag is honored, and
the AI stop respects the master switch (points at Settings while off,
at Ask AI while on). TourOverlay.instant=True disables animations so
everything is synchronous. QSettings is isolated per test session
(conftest), so 'tour_seen' never touches the real registry."""

import pytest
from PyQt6.QtCore import QSettings, Qt


@pytest.fixture
def window(qtbot, demo_db):
    from ui.main_window import MainWindow
    from ui.tour import TourOverlay
    TourOverlay.instant = True
    w = MainWindow()
    qtbot.addWidget(w)
    w.resize(1500, 860)
    w.show()
    yield w
    TourOverlay.instant = False


def _fresh_settings():
    s = QSettings("FamilyInvestmentTracker", "InvestmentTracker")
    s.remove('tour_seen')
    return s


def test_all_steps_resolve_on_demo_data(window):
    """Every configured stop must find a live target widget on a
    populated dashboard (AI off: the AI stop falls back to Settings)."""
    from ui import tour

    window.tabs.setCurrentIndex(0)
    for step in tour.TOUR_STEPS:
        if 'content' in step:
            target, title, text = step['content'](window)
        else:
            target = step['resolve'](window)
            title, text = step['title'], step['text']
        assert target, f"step {step['key']} found no target"
        assert title and text, f"step {step['key']} has empty copy"


def test_full_walkthrough_and_first_run_flag(window, qtbot):
    from ui import tour

    _fresh_settings()
    overlay = tour.maybe_start_tour(window)
    assert overlay is not None and overlay.isVisible()
    assert overlay._idx == -1, 'starts on the welcome bubble'
    assert overlay._bubble.isVisible()

    overlay.start_steps()
    seen = [tour.TOUR_STEPS[overlay._idx]['key']]
    for _ in range(len(tour.TOUR_STEPS) + 2):     # bounded loop
        if overlay._closing:
            break
        assert overlay._spot is not None, 'each stop spotlights a target'
        assert overlay._bubble.isVisible()
        overlay.next()
        if not overlay._closing:
            seen.append(tour.TOUR_STEPS[overlay._idx]['key'])
    assert overlay._closing, 'tour finished'
    assert seen[0] == 'nav' and seen[-1] == 'ai'
    assert len(seen) == len(tour.TOUR_STEPS), 'no stop was skipped'

    # completing the tour set the flag: no auto-start ever again
    assert tour.maybe_start_tour(window) is None


def test_back_and_escape(window, qtbot):
    from ui import tour

    _fresh_settings()
    overlay = tour.start_tour(window)
    overlay.start_steps()
    overlay.next()
    assert overlay._idx == 1
    overlay.back()
    assert overlay._idx == 0
    overlay.back()                                # first stop: no-op
    assert overlay._idx == 0
    qtbot.keyClick(overlay, Qt.Key.Key_Escape)
    assert overlay._closing, 'Esc exits the tour'
    # even a skipped tour counts as seen
    assert QSettings("FamilyInvestmentTracker",
                     "InvestmentTracker").value('tour_seen')


def test_ai_stop_follows_master_switch(window):
    import ai
    from ui.tour import _ai_step_content

    assert not ai.is_ai_enabled(), 'AI must default to OFF'
    target, title, text = _ai_step_content(window)
    assert target is window._settings_btn
    assert 'off' in title.lower()
    assert 'Settings' in text

    ai.set_ai_enabled(True)
    try:
        window._refresh_ai_affordances()
        target, title, text = _ai_step_content(window)
        assert target is window._ai_rail_btn
        assert 'approval' in text, 'consent promise stays in the copy'
    finally:
        ai.set_ai_enabled(False)
        window._refresh_ai_affordances()


def test_replay_does_not_stack_overlays(window):
    from ui import tour

    _fresh_settings()
    first = tour.start_tour(window)
    again = tour.start_tour(window)
    assert first is again, 'replay while running reuses the overlay'
