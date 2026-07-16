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


def test_sortable_tables_fill_every_row(qtbot, demo_db):
    """Regression: enabling QTableWidget sorting BEFORE filling makes
    setItem re-sort mid-fill and cells land in the wrong rows (found as
    blank Companies rows in a README screenshot). Every row of the three
    sortable tables must have its name/date AND its numeric cell set."""
    import models
    from ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    n_companies = len(models.get_all_companies())

    window.tabs.setCurrentIndex(2)          # Companies page
    tbl = window.companies_page._tbl
    assert tbl.rowCount() == n_companies
    for ri in range(tbl.rowCount()):
        assert tbl.item(ri, 0) and tbl.item(ri, 0).text(), f'row {ri} name'
        assert tbl.item(ri, 4) and tbl.item(ri, 4).text(), \
            f'row {ri} invested cell empty (mid-fill sort regression)'

    window.tabs.setCurrentIndex(3)          # Transactions page
    tbl = window.transactions_page._tbl
    assert tbl.rowCount() > 0
    for ri in range(tbl.rowCount()):
        assert tbl.item(ri, 0) and tbl.item(ri, 0).text(), f'row {ri} date'
        assert tbl.item(ri, 3) and tbl.item(ri, 3).text(), \
            f'row {ri} amount cell empty (mid-fill sort regression)'

    window.tabs.setCurrentIndex(0)          # Dashboard holdings table
    tbl = window.dashboard._holdings_tbl
    assert tbl.rowCount() == n_companies
    for ri in range(tbl.rowCount()):
        assert tbl.item(ri, 4) and tbl.item(ri, 4).text(), \
            f'row {ri} invested cell empty (mid-fill sort regression)'
