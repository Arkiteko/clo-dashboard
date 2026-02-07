"""
Guidance & documentation tab for CLO Dashboard.

Provides in-app reference for all metrics, formulas, stress testing
methodology, alert rules, compliance limits, and navigation.
"""
import streamlit as st


# ══════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

def render_guidance_tab():
    """Render the full Guidance tab content."""
    st.header("Guidance & Documentation")
    st.markdown(
        "Welcome to the CLO Warehouse Platform reference guide. "
        "Use the sections below to understand the metrics, methodologies, "
        "and features available throughout the dashboard."
    )

    _section_overview()
    st.divider()
    _section_metrics()
    st.divider()
    _section_compliance()
    st.divider()
    _section_stress_testing()
    st.divider()
    _section_alerts()
    st.divider()
    _section_data_pipeline()
    st.divider()
    _section_admin()


# ══════════════════════════════════════════════════════════════════════
# SECTION 1: DASHBOARD OVERVIEW
# ══════════════════════════════════════════════════════════════════════

def _section_overview():
    st.subheader("1. Dashboard Overview")
    st.markdown("""
This platform monitors **CLO warehouse facilities** during the ramp-up
phase before securitization. It tracks portfolio composition, compliance
with warehouse covenants, and risk exposures across multiple warehouses.
""")

    with st.expander("Tab Navigation Guide", expanded=True):
        st.markdown("""
| Tab | Purpose |
|-----|---------|
| **Global Portfolio** | Cross-warehouse view of total AUM, risk metrics, compliance status, and portfolio composition. Start here for the big picture. |
| **Warehouse Analytics** | Deep-dive into a single warehouse: asset quality, historical trends, concentration analysis, ramp tracking, and trade blotter. |
| **Stress Testing** | Run 5 stress scenarios (price shock, default, spread widening, downgrade migration, concentration) against any warehouse. Compare preset and custom scenarios. |
| **Tape Ingestion** | Upload new portfolio tapes (Excel files). The system validates, maps columns, and publishes to the data store. |
| **Watchlist & Alerts** | Monitor active alerts across all warehouses and review flagged assets that require attention. |
| **Admin Settings** | Configure facility limits, compliance triggers, sublimits, alert thresholds, ramp schedules, and stress test parameters per warehouse. |
| **Guidance** | You are here. Reference guide for all metrics, methodologies, and features. |
""")

    with st.expander("Sidebar"):
        st.markdown("""
The left sidebar provides an always-visible summary:

- **Portfolio Snapshot** \u2014 Total AUM, active warehouse count, WARF,
  Diversity Score, and portfolio duration at a glance.
- **Alert Summary** \u2014 Count of Critical (\U0001F534), Warning (\U0001F7E0),
  and Info (\U0001F535) alerts across all warehouses.
- **Data Freshness** \u2014 Shows how recent each warehouse's latest tape is.
  Stale data (>7 days) is flagged with a warning.
""")


# ══════════════════════════════════════════════════════════════════════
# SECTION 2: KEY METRICS REFERENCE
# ══════════════════════════════════════════════════════════════════════

def _section_metrics():
    st.subheader("2. Key Metrics Reference")
    st.markdown("Click any metric below for its definition, formula, and interpretation.")

    with st.expander("WARF \u2014 Weighted Average Rating Factor"):
        st.markdown("""
**What it measures:** The credit quality of the portfolio expressed as
a single number using Moody's rating factor scale.

**Formula:**
""")
        st.latex(r"\text{WARF} = \frac{\sum_{i} \text{Par}_i \times \text{RF}_i}{\sum_{i} \text{Par}_i}")
        st.markdown("""
Where RF is the Moody's Rating Factor for each asset's rating:

| Rating | Factor | Rating | Factor | Rating | Factor |
|--------|--------|--------|--------|--------|--------|
| Aaa | 1 | Baa1 | 260 | B3 | 3,490 |
| Aa1 | 10 | Baa2 | 360 | Caa1 | 4,770 |
| Aa2 | 20 | Baa3 | 610 | Caa2 | 6,500 |
| Aa3 | 40 | Ba1 | 940 | Caa3 | 8,070 |
| A1 | 70 | Ba2 | 1,350 | Ca | 10,000 |
| A2 | 120 | Ba3 | 1,766 | C | 10,000 |
| A3 | 180 | B1 | 2,220 | | |
| | | B2 | 2,720 | | |

**Interpretation:**
- **< 2,200** \u2014 Strong credit quality (skewed toward BB)
- **2,200 \u2013 2,800** \u2014 Typical BSL CLO range
- **2,800 \u2013 3,200** \u2014 Higher risk, approaching covenant levels
- **> 3,200** \u2014 Elevated risk, potential covenant issue
""")

    with st.expander("Diversity Score"):
        st.markdown("""
**What it measures:** How well-diversified the portfolio is across
industries and issuers, using a simplified Moody's methodology.

**How it works:**
1. Group assets by industry sector
2. For each industry, count the number of unique issuers
3. Map issuer count to "diversity units" via a lookup table
   (diminishing returns: 1 issuer = 1.0 unit, 10 issuers = 4.0 units)
4. Sum diversity units across all industries

**Interpretation:**
- **< 30** \u2014 Low diversification, concentrated portfolio
- **40 \u2013 60** \u2014 Moderate, typical for mid-size warehouses
- **60 \u2013 80** \u2014 Well-diversified, typical CLO target
- **> 80** \u2014 Highly diversified
""")

    with st.expander("HHI \u2014 Herfindahl-Hirschman Index"):
        st.markdown("""
**What it measures:** Concentration of exposure among issuers or
industries. Used for both issuer-level and industry-level analysis.

**Formula:**
""")
        st.latex(r"\text{HHI} = \sum_{i} s_i^2 \quad \text{where } s_i = \frac{\text{Par}_i}{\text{Total Par}}")
        st.markdown("""
**Interpretation:**
- **< 0.01** \u2014 Highly diversified (many small exposures)
- **0.01 \u2013 0.025** \u2014 Moderate concentration
- **> 0.025** \u2014 High concentration (dominated by few names)

*Example: 50 equal positions = HHI of 0.02. 10 equal positions = 0.10.*
""")

    with st.expander("DV01 \u2014 Dollar Value of One Basis Point"):
        st.markdown("""
**What it measures:** The dollar change in portfolio market value for
a 1 basis point (0.01%) move in interest rates.

**Formula:**
""")
        st.latex(r"\text{DV01} = \text{Market Value} \times \text{Modified Duration} \times 0.0001")
        st.markdown("""
For floating-rate loans, modified duration is approximated as:
""")
        st.latex(r"\text{Duration} \approx \text{WAL} \times 0.9")
        st.markdown("""
The 0.9 factor accounts for the floating-rate reset mechanism
(duration reflects only the time to the next coupon reset, not
full maturity, but WAL provides a reasonable proxy for floating-rate
assets that reprice periodically).

**Interpretation:** Higher DV01 means greater sensitivity to rate
changes. Useful for hedging decisions and risk budgeting.
""")

    with st.expander("OC Ratio \u2014 Overcollateralization Ratio"):
        st.markdown("""
**What it measures:** The ratio of collateral value to outstanding debt,
indicating the cushion protecting the lender.

**Formula:**
""")
        st.latex(r"\text{OC Ratio} = \frac{\text{Total Par} + \text{Cash}}{\text{Debt Outstanding}}")
        st.markdown("""
*Note: When debt outstanding is not manually entered, it is estimated as:*
""")
        st.latex(r"\text{Est. Debt} = \text{Par} \times \frac{\text{W.Avg Price}}{100} \times \text{Advance Rate}")
        st.markdown("""
**Interpretation:**
- **> Trigger (e.g. 125%)** \u2014 \u2705 In compliance
- **Near Trigger** \u2014 \U0001F7E0 Proximity warning
- **< Trigger** \u2014 \U0001F534 Breach \u2014 may require action (sell assets, post cash)

A typical warehouse OC trigger is **125%**, meaning for every $1 of
debt, at least $1.25 of collateral par is required.
""")

    with st.expander("WAS \u2014 Weighted Average Spread"):
        st.markdown("""
**What it measures:** The par-weighted average credit spread of the
portfolio, expressed in basis points (bps).

**Formula:**
""")
        st.latex(r"\text{WAS} = \frac{\sum_{i} \text{Par}_i \times \text{Spread}_i}{\sum_{i} \text{Par}_i}")
        st.markdown("""
**Interpretation:** Higher WAS means more yield (income) but typically
corresponds to higher credit risk. BSL portfolios usually have lower
WAS than middle-market portfolios.
""")

    with st.expander("WAL \u2014 Weighted Average Life"):
        st.markdown("""
**What it measures:** The par-weighted average time to maturity of the
portfolio, expressed in years.

**Formula:**
""")
        st.latex(r"\text{WAL} = \frac{\sum_{i} \text{Par}_i \times \text{Years to Maturity}_i}{\sum_{i} \text{Par}_i}")
        st.markdown("""
**Interpretation:**
- **3 \u2013 5 years** \u2014 Typical for CLO warehouse portfolios
- Shorter WAL = lower duration risk, sooner principal return
- Longer WAL = more spread income but higher reinvestment/duration risk
""")

    with st.expander("CCC Bucket %"):
        st.markdown("""
**What it measures:** The percentage of portfolio par invested in
assets rated Caa1 or below on the Moody's scale (CCC+ or below on S&P).

**Formula:**
""")
        st.latex(r"\text{CCC\%} = \frac{\text{Par in Caa1/Caa2/Caa3/Ca/C}}{\text{Total Par}}")
        st.markdown("""
**Why it matters:** CCC-rated assets have significantly higher default
probability. CLO indentures and warehouse agreements typically cap
CCC exposure at **7.5%**. Excess CCC par above this threshold is
often haircut in the OC test (valued at market price rather than par).

**Interpretation:**
- **< 5%** \u2014 Conservative
- **5 \u2013 7.5%** \u2014 Normal range, approaching limit
- **> 7.5%** \u2014 Breach, requires attention
""")

    with st.expander("Single-Name Concentration"):
        st.markdown("""
**What it measures:** The largest exposure to any single issuer as a
percentage of total portfolio par.

**Why it matters:** Excessive concentration in one name creates
idiosyncratic default risk. Warehouse covenants typically cap
single-name exposure at **2%** of total par.

The dashboard shows the top 10 obligors by exposure in the
Warehouse Analytics > Concentration tab.
""")


# ══════════════════════════════════════════════════════════════════════
# SECTION 3: COMPLIANCE & LIMITS
# ══════════════════════════════════════════════════════════════════════

def _section_compliance():
    st.subheader("3. Compliance & Limits")
    st.markdown("""
The Compliance Status table uses traffic-light indicators to show
whether each warehouse is within its covenant limits.
""")

    with st.expander("Status Icons", expanded=True):
        st.markdown("""
| Icon | Meaning |
|------|---------|
| \u2705 | **Pass** \u2014 Well within the limit (< 85% of threshold) |
| \U0001F7E0 | **Approaching** \u2014 Within 85\u2013100% of the limit |
| \U0001F534 | **Breach** \u2014 Limit exceeded, action required |
""")

    with st.expander("Compliance Tests"):
        st.markdown("""
| Test | What It Checks | Typical Limit |
|------|----------------|---------------|
| **OC Ratio** | Collateral adequacy vs. debt | > 125% |
| **CCC %** | Exposure to Caa1 and below | < 7.5% |
| **Max Industry** | Largest single-industry exposure | < 15% |
| **Max Issuer (SN)** | Largest single-name exposure | < 2% |
| **Second Lien (2L)** | Total 2nd lien par allocation | < 10% |
| **Unsecured** | Total unsecured par allocation | < 5% |
| **WARF** | Portfolio credit quality factor | < 3,000 |

*Limits are configurable per warehouse in Admin Settings.*
""")

    with st.expander("Lien Type Classification"):
        st.markdown("""
Assets are classified by their priority in the capital structure:

- **First Lien (1L)** \u2014 Senior secured, highest recovery in default
  (typical recovery: ~65%). Includes "Senior Secured", "1st Lien".
- **Second Lien (2L)** \u2014 Junior secured, lower recovery (~35%).
  Includes "2nd Lien", "Second Lien".
- **Unsecured** \u2014 No collateral claim, lowest recovery (~15%).
  Includes "Subordinated", "Mezzanine".

Warehouse agreements impose sublimits on 2L and Unsecured exposure
to maintain portfolio quality.
""")


# ══════════════════════════════════════════════════════════════════════
# SECTION 4: STRESS TESTING
# ══════════════════════════════════════════════════════════════════════

def _section_stress_testing():
    st.subheader("4. Stress Testing Methodology")
    st.markdown("""
The stress engine runs **5 independent scenarios** against a warehouse's
portfolio and aggregates the results to compute a stressed OC ratio
and determine whether the portfolio would breach covenants under
adverse conditions.
""")

    with st.expander("Scenario 1: Price Shock (Market Risk)"):
        st.markdown("""
**Simulates:** A sudden drop in market prices across the portfolio.

Applies rating-tiered haircuts to market prices:

| Tier | Default Haircut | Moderate | Severe |
|------|----------------|----------|--------|
| IG   | 1 pt           | 2 pts    | 4 pts  |
| BB   | 3 pts          | 5 pts    | 10 pts |
| B    | 5 pts          | 8 pts    | 15 pts |
| CCC  | 15 pts         | 20 pts   | 30 pts |

**Loss** = Sum of (Base MV \u2013 Stressed MV) across all assets.
""")

    with st.expander("Scenario 2: Default Stress (Credit Risk)"):
        st.markdown("""
**Simulates:** Defaults across the portfolio at rating-specific rates.

Each asset has a **Conditional Default Rate (CDR)** based on its rating
tier, and a **Recovery Rate** based on its lien type:

| Tier | Default CDR | | Lien | Recovery |
|------|------------|--|------|----------|
| IG   | 0.5%       | | 1st Lien | 65% |
| BB   | 2%         | | 2nd Lien | 35% |
| B    | 5%         | | Unsecured | 15% |
| CCC  | 15%        | | | |

**Loss** = Par \u00d7 CDR \u00d7 (1 \u2013 Recovery Rate)
""")

    with st.expander("Scenario 3: Spread Widening"):
        st.markdown("""
**Simulates:** Credit spread widening with duration-based MV impact.

Applies spread shocks by tier (in basis points):

| Tier | Default | Moderate | Severe |
|------|---------|----------|--------|
| IG   | 50 bps  | 75 bps   | 150 bps |
| BB   | 100 bps | 150 bps  | 300 bps |
| B    | 200 bps | 300 bps  | 500 bps |
| CCC  | 500 bps | 700 bps  | 1,000 bps |

**Loss** = MV \u00d7 Duration \u00d7 Spread Shock / 10,000
""")

    with st.expander("Scenario 4: Downgrade Migration"):
        st.markdown("""
**Simulates:** A wave of rating downgrades across the portfolio.

A configurable percentage (default 10%) of assets in each rating tier
are downgraded by one notch. The price impact is the incremental
haircut between the old and new tier.

This scenario also computes the **Stressed CCC %** \u2014 the post-migration
CCC bucket size \u2014 which determines if the CCC covenant would breach
under stress.
""")

    with st.expander("Scenario 5: Concentration Blow-up"):
        st.markdown("""
**Simulates:** The top N obligors (default N=3) defaulting simultaneously.

The largest obligors by par exposure are assumed to default entirely.
Recovery is applied based on lien type. This is a tail-risk scenario
testing worst-case concentration outcomes.
""")

    with st.expander("Loss Aggregation & Stressed OC"):
        st.markdown("""
Scenarios are **not simply added** together. The aggregation logic is:
""")
        st.latex(r"\text{Total Loss} = \max(\text{Price Shock}, \text{Spread Widening}) + \text{Default Stress}")
        st.markdown("""
*The rationale: Price shock and spread widening are correlated market-risk
scenarios (you wouldn't experience full impact of both simultaneously),
so the worse of the two is used. Default stress is a separate credit
event and is additive.*

**Stressed OC** is then computed as:
""")
        st.latex(r"\text{Stressed OC} = \frac{\text{Par} - \text{Total Loss} + \text{Cash}}{\text{Debt}}")
        st.markdown("""
If Stressed OC < OC Trigger, the portfolio **would breach under stress**.
""")

    with st.expander("Preset Scenarios"):
        st.markdown("""
Four preset stress configurations are available:

| Preset | Description |
|--------|-------------|
| **Base** | Mild stress \u2014 default parameters, low haircuts |
| **Moderate** | Medium stress \u2014 ~2x base haircuts, higher CDRs |
| **Severe** | Extreme stress \u2014 ~3x base, 40% CCC CDR, top 5 concentration |
| **COVID-2020** | Calibrated to March 2020 drawdown, ~2.5x base |

You can also customize individual parameters in the Stress Testing tab
or adjust defaults in Admin Settings.
""")

    with st.expander("Historical Stress Trends"):
        st.markdown("""
The **Historical Stress** section runs the selected scenario against
every historical tape snapshot for a warehouse, producing a time series
of Stressed OC, Total Loss, and Loss %. This shows how the portfolio's
stress resilience has evolved over time.
""")


# ══════════════════════════════════════════════════════════════════════
# SECTION 5: ALERTS & WATCHLIST
# ══════════════════════════════════════════════════════════════════════

def _section_alerts():
    st.subheader("5. Alerts & Watchlist")
    st.markdown("""
The alert engine evaluates the portfolio against configurable thresholds
on every page load. Alerts are **stateless** \u2014 they reflect the current
state of the data, not a history of events.
""")

    with st.expander("Alert Severity Levels"):
        st.markdown("""
| Level | Icon | Meaning |
|-------|------|---------|
| **CRITICAL** | \U0001F534 | A covenant or limit has been breached. Immediate action required. |
| **WARNING** | \U0001F7E0 | Approaching a limit or threshold. Proactive monitoring recommended. |
| **INFO** | \U0001F535 | Informational observation. No action needed but worth noting. |
""")

    with st.expander("Alert Rules by Category", expanded=True):
        st.markdown("""
**Compliance Alerts:**
| Rule | Severity | Triggers When |
|------|----------|---------------|
| OC Breach | CRITICAL | OC ratio falls below trigger (e.g. 125%) |
| OC Proximity | WARNING | OC within proximity margin of trigger |
| CCC Breach | CRITICAL | CCC % exceeds limit (e.g. 7.5%) |
| CCC Proximity | WARNING | CCC % approaching limit |
| 2nd Lien Breach | CRITICAL | 2L exposure exceeds sublimit |
| Unsecured Breach | CRITICAL | Unsecured exposure exceeds sublimit |
| High Utilization | WARNING | Facility utilization > warning level (e.g. 90%) |

**Concentration Alerts:**
| Rule | Severity | Triggers When |
|------|----------|---------------|
| Industry Breach | CRITICAL | Any single industry exceeds limit (e.g. 15%) |
| Industry Proximity | WARNING | Industry approaching limit |
| Single-Name Breach | CRITICAL | Largest issuer exceeds limit (e.g. 2%) |
| Single-Name Proximity | WARNING | Largest issuer approaching limit |

**Risk Alerts:**
| Rule | Severity | Triggers When |
|------|----------|---------------|
| WARF Critical | CRITICAL | WARF exceeds critical threshold (e.g. 3500) |
| WARF Warning | WARNING | WARF exceeds warning threshold (e.g. 3000) |
| Low Diversity | WARNING | Diversity score below threshold (e.g. 40) |
| Defaulted Assets | WARNING | Any assets flagged as defaulted |

**Data Quality Alerts:**
| Rule | Severity | Triggers When |
|------|----------|---------------|
| Data Critically Stale | CRITICAL | Latest tape > 14 days old |
| Data Getting Stale | WARNING | Latest tape > 7 days old |
| Distressed Prices | INFO | Assets priced below 70 (possible data error or distress) |
""")

    with st.expander("Proximity Warnings"):
        st.markdown("""
Proximity warnings fire when a metric is within a configurable margin
of its limit, giving you advance notice before a breach occurs.

**Default margin: 10%**

*Example:* With an OC trigger of 125% and 10% proximity margin, a
warning fires when OC drops below 125% \u00d7 1.10 = **137.5%**.

For upper-bound limits (like CCC %), proximity fires when the metric
exceeds limit \u00d7 (1 \u2013 margin). E.g., CCC limit 7.5% with 10% margin
warns at 7.5% \u00d7 0.90 = **6.75%**.

The proximity margin is configurable per warehouse in Admin Settings.
""")

    with st.expander("Asset Watchlist"):
        st.markdown("""
The watchlist automatically flags individual assets that may require
attention. An asset appears on the watchlist if it meets **any** of
these criteria:

| Criteria | Severity | Why It Matters |
|----------|----------|----------------|
| **Defaulted** | CRITICAL | Asset is in default \u2014 recovery process needed |
| **CCC-Rated** (Caa1 or worse) | WARNING | High default risk, may impact CCC covenant |
| **Distressed Price** (< 80) | WARNING | May indicate credit deterioration or data issue |
| **Rating Downgraded** from original | WARNING | Credit migration, may affect WARF and CCC % |
| **Concentrated** (> 1.5% of portfolio) | INFO | Large single-name position relative to portfolio |

Assets can have multiple flags. The watchlist is sortable by severity
and downloadable as CSV.
""")


# ══════════════════════════════════════════════════════════════════════
# SECTION 6: DATA PIPELINE
# ══════════════════════════════════════════════════════════════════════

def _section_data_pipeline():
    st.subheader("6. Data Pipeline")

    with st.expander("Tape Ingestion Process"):
        st.markdown("""
The platform uses a 4-stage ETL pipeline to process portfolio tapes:

```
Upload (Excel) \u2192 0_raw \u2192 1_staging \u2192 2_standard \u2192 3_published
```

1. **Raw (0_raw)** \u2014 Original uploaded file, stored as-is for audit trail
2. **Staging (1_staging)** \u2014 Parsed from Excel into a DataFrame
3. **Standard (2_standard)** \u2014 Column names mapped to canonical schema
4. **Published (3_published)** \u2014 Validated and saved as Parquet for
   fast analytics

**Column Mapping:** The ETL automatically maps common column names
(e.g. "Par" \u2192 "par_amount", "Issuer" \u2192 "issuer_name", "Lien" \u2192
"lien_type"). Unmapped columns are passed through unchanged.
""")

    with st.expander("File Naming Convention"):
        st.markdown("""
Published files follow the format:

```
YYYYMMDD_HHMMSS_Warehouse_Name.parquet
```

- **YYYYMMDD** \u2014 The as-of date of the tape data
- **HHMMSS** \u2014 Upload timestamp (for deduplication)
- **Warehouse_Name** \u2014 The warehouse this tape belongs to

When multiple tapes exist for the same warehouse and date, the most
recent upload (by timestamp) is used for analytics.
""")

    with st.expander("Validation Rules"):
        st.markdown("""
The validation engine checks uploaded tapes for data quality:

**Hard Errors** (block publishing):
- Missing required columns (e.g. par_amount, asset_id)
- Invalid data types (text in numeric fields)

**Soft Warnings** (publish but flag):
- Missing optional fields (e.g. spread, maturity_date)
- Negative par amounts
- Prices outside reasonable range (< 0 or > 150)
- Duplicate asset IDs

Files with hard errors will not be published. Files with only soft
warnings are published but the issues are displayed for review.
""")

    with st.expander("Historical Data"):
        st.markdown("""
The platform retains all historical snapshots. Each time a new tape is
uploaded, it adds a new data point to the time series. Historical data
powers:

- **Trend Analysis** \u2014 Track funded exposure, W.Avg price, OC ratio,
  WARF over time (Warehouse Analytics \u2192 Trends tab)
- **Ramp Tracking** \u2014 Compare actual ramp-up against target schedule
- **Trade Blotter** \u2014 Diff two dates to see assets added/removed/modified
- **Historical Stress** \u2014 Run stress tests across all past snapshots
""")


# ══════════════════════════════════════════════════════════════════════
# SECTION 7: ADMIN SETTINGS GUIDE
# ══════════════════════════════════════════════════════════════════════

def _section_admin():
    st.subheader("7. Admin Settings Guide")
    st.markdown("""
All settings are configured **per warehouse** and persist across sessions
in `data/warehouse_config.json`. New fields are automatically populated
with sensible defaults for backward compatibility.
""")

    with st.expander("Facility Limits"):
        st.markdown("""
| Setting | Default | Description |
|---------|---------|-------------|
| **Max Facility Size** | $100M | Maximum borrowing capacity of the warehouse |
| **Advance Rate** | 0.65 (65%) | Percentage of collateral value the lender will advance as debt |

*Example: $100M par at 65% advance rate = $65M debt capacity.*
""")

    with st.expander("Compliance Triggers"):
        st.markdown("""
| Setting | Default | Description |
|---------|---------|-------------|
| **Min OC Ratio Trigger** | 1.25 (125%) | Minimum overcollateralization ratio before breach |
| **Max Industry Concentration** | 0.15 (15%) | Maximum single-industry exposure as % of par |
""")

    with st.expander("Compliance Sublimits"):
        st.markdown("""
| Setting | Default | Description |
|---------|---------|-------------|
| **Max Single Name %** | 0.02 (2%) | Maximum exposure to any single issuer |
| **Max Second Lien %** | 0.10 (10%) | Maximum allocation to second lien assets |
| **Max Unsecured %** | 0.05 (5%) | Maximum allocation to unsecured assets |
| **Max CCC %** | 0.075 (7.5%) | Maximum allocation to CCC-rated assets |
""")

    with st.expander("Alert Settings"):
        st.markdown("""
| Setting | Default | Description |
|---------|---------|-------------|
| **Proximity Warning Margin** | 0.10 (10%) | How close to a limit before a warning fires |
| **Data Stale Warning** | 7 days | Days before data freshness warning |
| **Data Stale Critical** | 14 days | Days before data freshness critical alert |
| **WARF Warning** | 3,000 | WARF threshold for warning alert |
| **WARF Critical** | 3,500 | WARF threshold for critical alert |
| **Diversity Score Warning** | 40 | Diversity score below which a warning fires |
| **Utilization Warning** | 0.90 (90%) | Facility utilization level for warning |
""")

    with st.expander("Ramp Schedule"):
        st.markdown("""
| Setting | Default | Description |
|---------|---------|-------------|
| **Target Ramp Amount** | $0 | Target total par amount at close |
| **Target Close Date** | (none) | Expected securitization closing date |

These power the **Ramp Tracker** chart in Warehouse Analytics \u2192 Trends,
which shows a linear target line from the earliest tape to the close
date compared against actual funded exposure.
""")

    with st.expander("Stress Test Parameters"):
        st.markdown("""
Custom stress parameters allow you to override the preset scenarios:

**Price Shock Haircuts** (points by tier): IG, BB, B, CCC
**Conditional Default Rates** (decimal by tier): IG, BB, B, CCC
**Recovery Rates** (decimal by lien): 1st Lien, 2nd Lien, Unsecured
**Spread Shocks** (bps by tier): IG, BB, B, CCC
**Migration Rate**: Fraction of assets downgraded (e.g. 0.10 = 10%)
**Top N Obligors**: Number of names in concentration blow-up scenario

See **Section 4: Stress Testing** above for details on how each
parameter affects the stress calculations.
""")
