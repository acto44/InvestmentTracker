"""UI smoke test: the app boots headless against a populated demo
database. Proves imports, styles, and the main window construction —
nothing more. QT_QPA_PLATFORM=offscreen is set in conftest.py."""


def test_main_window_boots_on_demo_data(qtbot, demo_db):
    from ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.isVisible()
    assert window.windowTitle(), 'window has a title'
