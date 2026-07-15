"""
Populates investments.db with fictional demo companies for showcase purposes.
Safe to commit — contains no real financial data.
Run:  python seed_demo_data.py          (add --yes to replace existing data)

Current value = ownership_pct × company_valuation (see metrics.py).
Company valuations below represent total company worth, not just our stake.
"""
import models


def add(name, entity, sector, invest_type, valuation, date, description, thesis, notes=''):
    cid = models.add_company(
        name=name, entity=entity, sector=sector, country="",
        first_investment_date=date, current_valuation=valuation,
        description=description, notes=notes,
    )
    models.update_company(cid, investment_type=invest_type, thesis=thesis)
    return cid


def seed(verbose=True, force=False):
    """Populate the CURRENT database (models.get_db_path()) with the
    demo portfolio. Idempotent. Tests point models at a temp database
    via models.set_db_path() first.

    SAFETY GUARD (CLAUDE.md: PRIVACY): this script REPLACES all companies
    and rounds. Against the default database path (i.e. possibly a live
    file) it refuses to run when data exists, unless force=True
    (--yes on the command line)."""
    models.init_db()

    if not force and models.db_path_is_default():
        conn = models.get_conn()
        n = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        conn.close()
        if n:
            raise SystemExit(
                f"seed_demo_data: the database at {models.get_db_path()} "
                f"already contains {n} companies, and this script REPLACES "
                "everything in it. If that is really what you want, run:\n"
                "    python seed_demo_data.py --yes")

    # Clear existing data so the script is idempotent
    conn = models.get_conn()
    conn.execute("DELETE FROM funding_rounds")
    conn.execute("DELETE FROM companies")
    conn.commit()
    conn.close()


    # ── Portfolio A ───────────────────────────────────────────────────────────────
    #
    # NovaTech AI
    #   Rounds: Seed 2,500 + Series A 3,800 = 6,300 invested, latest ownership 7.1%
    #   Company valuation 220,000 → stake = 0.071 × 220,000 = 15,620 → MOIC 2.5×

    nova = add(
        "NovaTech AI", "Portfolio A", "AI / Machine Learning", "Startup",
        220_000, "2021-03-01",
        "B2B platform using LLMs to automate document processing for legal firms.",
        "Strong founding team with prior exit. Unique dataset moat in legal vertical. "
        "Signed LOIs with 3 top-10 law firms before seed close.",
    )
    models.add_round(nova, "Seed", "2021-03-15", 2500,
                     pre_money_valuation=8_000, post_money_valuation=10_500,
                     shares_received=23_809, total_shares_outstanding=100_000, ownership_pct=8.5)
    models.add_round(nova, "Series A", "2023-06-01", 3800,
                     pre_money_valuation=30_000, post_money_valuation=33_800,
                     shares_received=11_242, total_shares_outstanding=120_000, ownership_pct=7.1)

    # GreenFlow Energy
    #   Rounds: Pre-Seed 1,200 + Seed 2,000 = 3,200 invested, latest ownership 5.2%
    #   Company valuation 130,000 → stake = 0.052 × 130,000 = 6,760 → MOIC 2.1×

    greenflow = add(
        "GreenFlow Energy", "Portfolio A", "CleanTech", "Startup",
        130_000, "2020-09-01",
        "Software platform for optimising EV fleet charging to reduce grid costs.",
        "CleanTech tailwinds from EU regulation. Recurring SaaS model on top of hardware "
        "the customer already owns. Low CAC via fleet operator channel.",
    )
    models.add_round(greenflow, "Pre-Seed", "2020-09-10", 1200, ownership_pct=6.0)
    models.add_round(greenflow, "Seed", "2022-02-01", 2000,
                     pre_money_valuation=12_000, post_money_valuation=14_000, ownership_pct=5.2)

    # MediScan — early stage, pending new valuation round, metrics shown as n/a

    mediscan = add(
        "MediScan", "Portfolio A", "Healthtech", "Startup",
        None, "2022-11-01",
        "AI-assisted radiology tool that flags anomalies in CT scans within seconds.",
        "Radiology shortage is structural. FDA 510(k) pathway de-risks regulatory timeline. "
        "Early trial data shows 94% sensitivity vs 87% for unaided radiologist.",
    )
    models.add_round(mediscan, "Seed", "2022-11-15", 1500, ownership_pct=4.8)
    models.add_round(mediscan, "Bridge", "2024-04-01", 800, ownership_pct=4.2)

    # DataPulse
    #   Round: Seed 900, ownership 3.5%
    #   Company valuation 95,000 → stake = 0.035 × 95,000 = 3,325 → MOIC 3.7×

    datapulse = add(
        "DataPulse", "Portfolio A", "SaaS / Analytics", "Startup",
        95_000, "2021-07-01",
        "Real-time customer data platform for mid-market e-commerce brands.",
        "Shopify ecosystem play. Zero engineering lift for the customer. "
        "NRR above 130% in cohorts tracked.",
    )
    models.add_round(datapulse, "Seed", "2021-07-20", 900, ownership_pct=3.5)

    # Wintex Payments — EXITED in 2024 via acquisition
    #   Rounds: Seed 3,000 + Series A 4,500 = 7,500 invested, latest ownership 5.1%
    #   Acquisition valued company at 520,000 → stake = 0.051 × 520,000 = 26,520 → MOIC 3.5×

    wintex = add(
        "Wintex Payments", "Portfolio A", "Fintech", "Startup",
        520_000, "2020-05-01",
        "Instant cross-border payment rails for SMEs. Acquired by a Nordic bank in 2024.",
        "Strong unit economics from day one. Regulatory moat via PSD2 licence. "
        "Strategic acquirer interest signalled early.",
        notes="Status: Exited\nExit year: 2024\nTarget multiple: 4×",
    )
    models.add_round(wintex, "Seed", "2020-05-01", 3000, ownership_pct=6.0)
    models.add_round(wintex, "Series A", "2022-01-15", 4500,
                     pre_money_valuation=20_000, post_money_valuation=24_500, ownership_pct=5.1)

    # ── Portfolio B ───────────────────────────────────────────────────────────────

    # BioVance
    #   Rounds: Series A 5,000 + Series B 4,000 = 9,000 invested, latest ownership 3.2%
    #   Company valuation 680,000 → stake = 0.032 × 680,000 = 21,760 → MOIC 2.4×

    biovance = add(
        "BioVance", "Portfolio B", "Biotech", "Startup",
        680_000, "2021-01-01",
        "Precision oncology company developing targeted therapies for rare tumour types.",
        "Phase II data is compelling. Lead programme has orphan drug designation "
        "which shortens approval path and grants market exclusivity.",
    )
    models.add_round(biovance, "Series A", "2021-01-20", 5000,
                     pre_money_valuation=18_000, post_money_valuation=23_000,
                     shares_received=21_739, total_shares_outstanding=200_000, ownership_pct=3.8)
    models.add_round(biovance, "Series B", "2023-08-01", 4000,
                     pre_money_valuation=28_000, post_money_valuation=32_000, ownership_pct=3.2)

    # UrbanMobility — early stage, no current valuation yet

    urban = add(
        "UrbanMobility", "Portfolio B", "Transport / Logistics", "Startup",
        None, "2022-04-01",
        "Micro-logistics platform connecting last-mile couriers to retail stores.",
        "Same-day delivery demand is structural post-COVID. Asset-light marketplace "
        "model scales without capex. Two city exclusivity contracts signed.",
    )
    models.add_round(urban, "Pre-Seed", "2022-04-15", 600, ownership_pct=5.0)
    models.add_round(urban, "Seed", "2023-10-01", 1200, ownership_pct=4.1)

    # Nordic Growth Fund II — ViFi Fund
    #   For fund investments ownership_pct=100 so current_value = NAV directly.
    #   Invested 10,000, NAV 16,000 → MOIC 1.6×

    # DataPulse pays dividends — demo for income flows
    models.add_cashflow(datapulse, '2023-03-01', 'dividend', 120,
                        note='FY22 dividend', origin='app')
    models.add_cashflow(datapulse, '2024-03-01', 'dividend', 150,
                        note='FY23 dividend', origin='app')

    # BioVance partial sale — demo for share sales & ownership reduction
    models.add_cashflow(biovance, '2024-09-01', 'partial_sale', 1600,
                        shares_delta=-5000,
                        note='secondary sale to co-investor', origin='app')

    # Wintex full exit — demo for realized proceeds (status already Exited)
    models.add_cashflow(wintex, '2024-06-30', 'exit_proceeds', 26520,
                        note='acquisition by Nordic bank', origin='app')

    # Journal entries — demo for the dated qualitative side
    models.add_company_update(
        nova, '2025-04-05', period_label='2025-Q1',
        title='Strong quarter, enterprise pipeline building',
        text='ARR grew ~20% QoQ. Two of the three LOI law firms converted '
             'to paid pilots. Burn stable; runway ~18 months. Watching '
             'competitor consolidation in legal AI.')
    models.add_company_update(
        nova, '2025-07-08', period_label='2025-Q2',
        title='Series B conversations started',
        text='Management opened Series B talks with two funds. Pilot '
             'conversion strong, but sales cycle to big law remains slow.')
    models.add_company_update(
        datapulse, '2025-06-30', period_label='2025-Q2',
        title='Dividend policy continues',
        text='Second consecutive annual dividend paid. NRR holding above '
             '130%; founder considering a strategic sale in 2026.')

    nordic_vc = add(
        "Nordic Growth Fund II", "Portfolio B", "Fund", "ViFi Fund",
        16_000, "2020-01-01",
        "Diversified VC fund investing in Nordic B2B software companies at Series A.",
        "Access to deal flow we wouldn't see directly. Strong GP track record — "
        "Fund I returned 3.1× net. Vintage timing post-correction.",
    )
    models.add_round(nordic_vc, "Fund commitment", "2020-01-15", 8000, ownership_pct=100)
    models.add_round(nordic_vc, "Follow-on",       "2022-06-01", 2000, ownership_pct=100)

    # SolarGrid Capital — Private Equity Fund
    #   NAV-based: invested 10,000, NAV 14,500 → MOIC 1.45×

    solargrid = add(
        "SolarGrid Capital", "Portfolio B", "Energy / Infrastructure", "Private Equity Fund",
        14_500, "2021-06-01",
        "Private equity fund acquiring and optimising utility-scale solar assets.",
        "Stable cash-yielding asset class with inflation-linked revenues. "
        "Diversification away from equity risk in the rest of the portfolio.",
    )
    models.add_round(solargrid, "Fund commitment", "2021-06-20", 10_000, ownership_pct=100)

    # Cloudburst Storage — written off / bankrupt (realistic risk showcase)
    #   One bad investment in the portfolio demonstrates the app handles write-offs

    cloudburst = add(
        "Cloudburst Storage", "Portfolio B", "Infrastructure", "Startup",
        0, "2020-08-01",
        "Distributed object-storage startup that competed with AWS S3. "
        "Lost key enterprise contracts to hyperscalers and ran out of runway.",
        "Cost arbitrage for EU data-residency customers. "
        "Underestimated AWS pricing aggression in 2022.",
        notes="Status: Bankrupt (written off)\nBankrupt June 2023",
    )
    models.add_round(cloudburst, "Seed",   "2020-08-15", 1500, ownership_pct=7.0)
    models.add_round(cloudburst, "Bridge", "2022-03-01",  700, ownership_pct=6.5)

    if not verbose:
        return

    # ── Summary ───────────────────────────────────────────────────────────────────

    import metrics as m

    print("Demo data loaded successfully.\n")
    companies = models.get_all_companies()
    print(f"  {len(companies)} companies across {len(set(c['entity'] for c in companies))} portfolios\n")

    all_invested = 0.0
    valued_invested = 0.0
    valued_current = 0.0

    for c in companies:
        rounds   = models.get_rounds(c['id'])
        met      = m.company_metrics_for(c, rounds,
                                         models.get_cashflows(c['id']))
        invested = met['total_invested']
        cv       = met['current_value']
        moic_val = met['moic']
        all_invested += invested
        if cv is not None:
            valued_invested += invested
            valued_current  += cv
        moic_str = f"{moic_val:.2f}×" if moic_val is not None else "n/a"
        cv_str   = f"{cv:>10,.0f}" if cv is not None else "       n/a"
        print(f"  [{c['entity']:12s}] {c['name']:<28} invested {invested:>7,.0f}  value {cv_str}  MOIC {moic_str}")

    portfolio_moic = valued_current / valued_invested if valued_invested else 0
    print(f"\n  Portfolio MOIC (companies with valuation): {portfolio_moic:.2f}×")
    print(f"  Total invested (all companies):            {all_invested:,.0f}")
    print(f"  Total current value (valued companies):    {valued_current:,.0f}")


if __name__ == "__main__":
    import sys
    seed(force='--yes' in sys.argv)
