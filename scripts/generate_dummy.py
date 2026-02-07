import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src to path to import config
sys.path.append(str(Path(__file__).parent.parent))
from src.config import save_warehouse_config, WarehouseConfig, get_warehouse_config
from src.models import AlertConfig

# Setup
# We assume we run this from the project root (c:\Users\Alex\Desktop\CLO Dashboard)
OUTPUT_DIR = Path("data/0_raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def setup_configs():
    """Ensure warehouses have distinct types for demo purposes."""
    # Alpha: BSL
    save_warehouse_config("Warehouse_Alpha", WarehouseConfig(
        max_facility_amount=150_000_000,
        advance_rate=0.85,
        warehouse_type="BSL",
        oc_trigger_pct=1.25,
        target_ramp_amount=150_000_000,
        target_close_date=(datetime.today() + timedelta(days=90)).strftime("%Y-%m-%d"),
    ))
    # Beta: MM (Higher spread, lower AR, lower limit)
    save_warehouse_config("Warehouse_Beta", WarehouseConfig(
        max_facility_amount=75_000_000,
        advance_rate=0.75,
        warehouse_type="Middle Market",
        oc_trigger_pct=1.35,
        min_spread=4.50,
        max_second_lien_pct=0.15,
        max_unsecured_pct=0.08,
    ))
    # Gamma: BSL (Ramp)
    save_warehouse_config("Warehouse_Gamma", WarehouseConfig(
        max_facility_amount=50_000_000,
        advance_rate=0.80,
        warehouse_type="BSL",
        target_ramp_amount=50_000_000,
        target_close_date=(datetime.today() + timedelta(days=60)).strftime("%Y-%m-%d"),
    ))
    print("Configs updated: Alpha (BSL), Beta (MM), Gamma (BSL)")

# Constants
INDUSTRIES = [
    "Software", "Healthcare Providers", "Aerospace & Defense",
    "Diversified Telecommunication", "Oil, Gas & Consumable Fuels",
    "IT Services", "Hotels, Restaurants & Leisure", "Chemicals",
    "Insurance", "Pharmaceuticals", "Media & Entertainment",
    "Food Products", "Specialty Retail", "Building Products",
]

ISSUERS = [f"Company {i}" for i in range(101, 160)]

COUNTRIES = ["US", "US", "US", "US", "US", "US", "US", "UK", "DE", "CA", "FR", "NL"]

LIEN_TYPES_BSL = ["1L", "1L", "1L", "1L", "1L", "1L", "1L", "1L", "2L", "Unsecured"]
LIEN_TYPES_MM = ["1L", "1L", "1L", "1L", "1L", "1L", "2L", "2L", "Unsecured", "Unsecured"]

# S&P equivalents for Moody's ratings
MOODYS_TO_SP = {
    "Aaa": "AAA", "Aa1": "AA+", "Aa2": "AA", "Aa3": "AA-",
    "A1": "A+", "A2": "A", "A3": "A-",
    "Baa1": "BBB+", "Baa2": "BBB", "Baa3": "BBB-",
    "Ba1": "BB+", "Ba2": "BB", "Ba3": "BB-",
    "B1": "B+", "B2": "B", "B3": "B-",
    "Caa1": "CCC+", "Caa2": "CCC", "Caa3": "CCC-",
}


def generate_tape(warehouse_name, num_assets=50, as_of_date=None):
    if as_of_date is None:
        as_of_date = datetime.today()
    data = []
    base_date = as_of_date.date()

    is_mm = "Beta" in warehouse_name
    lien_pool = LIEN_TYPES_MM if is_mm else LIEN_TYPES_BSL

    for _ in range(num_assets):
        par = round(random.uniform(1_000_000, 10_000_000), 2)
        price = round(random.uniform(92.0, 100.5), 2)

        if is_mm:
             # Middle Market Profile
             spread = round(random.uniform(5.5, 9.0), 2)
             price = round(random.uniform(94.0, 99.0), 2)
             coupon = round(5.3 + spread, 2)
        else:
             # BSL Profile
             spread = round(random.uniform(2.5, 4.5), 2)
             price = round(random.uniform(96.0, 100.25), 2)
             coupon = round(5.3 + spread, 2)

        # Floor (most floating rate loans have one)
        floor = round(random.choice([0.0, 0.0, 0.50, 0.75, 1.00, 1.00]), 2)

        # Dates
        orig_days_ago = random.randint(100, 1000)
        orig_date = base_date - timedelta(days=orig_days_ago)
        mat_days_future = random.randint(365*2, 365*7)
        mat_date = base_date + timedelta(days=mat_days_future)

        # Ratings
        ratings_scale = ["Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3", "Baa1", "Baa2", "Baa3", "Ba1", "Ba2", "Ba3", "B1", "B2", "B3", "Caa1", "Caa2", "Caa3"]
        idx = random.choice(range(len(ratings_scale)))
        # Bias towards B/Ba
        if random.random() < 0.7:
             idx = random.choice(range(10, 16))

        curr_rtg = ratings_scale[idx]
        # Simulate migration (mostly same, some downgrade)
        orig_idx = max(0, idx - random.choice([0,0,0,1,2]))
        orig_rtg = ratings_scale[orig_idx]

        # S&P rating (with slight noise - sometimes differ by one notch)
        sp_rtg = MOODYS_TO_SP.get(curr_rtg, "")
        if random.random() < 0.15 and sp_rtg:
            # Shift S&P by one notch sometimes
            sp_list = list(MOODYS_TO_SP.values())
            sp_idx = sp_list.index(sp_rtg) if sp_rtg in sp_list else -1
            if sp_idx >= 0:
                shift = random.choice([-1, 1])
                sp_idx = max(0, min(len(sp_list)-1, sp_idx + shift))
                sp_rtg = sp_list[sp_idx]

        # Lien type
        lien = random.choice(lien_pool)

        # Status
        is_default = "Caa" in curr_rtg and random.random() < 0.2
        if is_default:
            price = round(random.uniform(40, 70), 2)

        # Cov-lite and PIK
        is_cov_lite = random.random() < (0.6 if not is_mm else 0.3)
        is_pik = random.random() < 0.05

        item = {
            "Asset ID": f"ASSET-{random.randint(10000, 99999)}",
            "Issuer": random.choice(ISSUERS),
            "Borrower": "",
            "Par": par,
            "Currency": "USD",
            "Market Price": price,
            "Market Value": par * (price / 100),
            "Spread": spread,
            "Coupon": coupon,
            "Floor": floor,
            "Maturity Date": mat_date,
            "Origination Date": orig_date,
            "Payment Freq": random.choice(["Quarterly", "Monthly"]),
            "Industry": random.choice(INDUSTRIES),
            "Country": random.choice(COUNTRIES),
            "Rating Moodys": curr_rtg,
            "Rating SP": sp_rtg,
            "Original Rating": orig_rtg,
            "Lien": lien,
            "Facility Type": "Term Loan" if lien != "Unsecured" else random.choice(["Term Loan", "Revolver"]),
            "Cov Lite": is_cov_lite,
            "PIK": is_pik,
            "Defaulted": is_default,
            "Warehouse": warehouse_name
        }
        data.append(item)

    df = pd.DataFrame(data)

    # Save
    as_of_str = as_of_date.strftime("%Y%m%d")
    upload_ts = datetime.now().strftime("%H%M%S")

    filename = f"{as_of_str}_{upload_ts}_{warehouse_name}.xlsx"
    df.to_excel(OUTPUT_DIR / filename, index=False)
    print(f"Generated {filename}")

if __name__ == "__main__":
    setup_configs()

    # Generate history for trends
    today = datetime.today()
    dates = [today - timedelta(days=x) for x in range(0, 90, 14)]

    for d in dates:
        # Alpha: BSL, large, stable
        generate_tape("Warehouse_Alpha", 55, as_of_date=d)

        # Beta: MM, higher spread, slightly smaller
        generate_tape("Warehouse_Beta", 65, as_of_date=d)

        # Gamma: Ramp up
        if d > today - timedelta(days=40):
             generate_tape("Warehouse_Gamma", 35, as_of_date=d)
