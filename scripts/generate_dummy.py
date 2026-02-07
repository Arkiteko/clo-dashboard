import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src to path to import config
sys.path.append(str(Path(__file__).parent.parent))
from src.config import save_warehouse_config, WarehouseConfig, get_warehouse_config

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
        oc_trigger_pct=1.25
    ))
    # Beta: MM (Higher spread, lower AR, lower limit)
    save_warehouse_config("Warehouse_Beta", WarehouseConfig(
        max_facility_amount=75_000_000,
        advance_rate=0.75,
        warehouse_type="Middle Market",
        oc_trigger_pct=1.35, # Higher OC req
        min_spread=4.50
    ))
    # Gamma: BSL (Ramp)
    save_warehouse_config("Warehouse_Gamma", WarehouseConfig(
        max_facility_amount=50_000_000,
        advance_rate=0.80,
        warehouse_type="BSL"
    ))
    print("Configs updated: Alpha (BSL), Beta (MM), Gamma (BSL)")

# Constants
INDUSTRIES = [
    "Software", "Healthcare Providers", "Aerospace & Defense", 
    "Diversified Telecommunication", "Oil, Gas & Consumable Fuels",
    "IT Services", "Hotels, Restaurants & Leisure", "Chemicals"
]

ISSUERS = [f"Company {i}" for i in range(101, 150)]

def generate_tape(warehouse_name, num_assets=50, as_of_date=None):
    if as_of_date is None:
        as_of_date = datetime.today()
    data = []
    base_date = as_of_date.date()
    
    for _ in range(num_assets):
        par = round(random.uniform(1_000_000, 10_000_000), 2)
        price = round(random.uniform(92.0, 100.5), 2)
        
        if "Beta" in warehouse_name:
             # Middle Market Profile
             spread = round(random.uniform(5.5, 9.0), 2) # 550-900 bps
             price = round(random.uniform(94.0, 99.0), 2) # Less liquid, slightly lower marks
             coupon = round(5.3 + spread, 2)
        else:
             # BSL Profile
             spread = round(random.uniform(2.5, 4.5), 2) # 250-450 bps
             price = round(random.uniform(96.0, 100.25), 2)
             coupon = round(5.3 + spread, 2)
        
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
             idx = random.choice(range(10, 16)) # Ba2 to B3
             
        curr_rtg = ratings_scale[idx]
        # Simulate migration (mostly same, some downgrade)
        orig_idx = max(0, idx - random.choice([0,0,0,1,2]))
        orig_rtg = ratings_scale[orig_idx]
        
        # Status
        is_default = "Caa" in curr_rtg and random.random() < 0.2
        if is_default:
            price = round(random.uniform(40, 70), 2)

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
            "Floor": 0.0,
            "Maturity Date": mat_date,
            "Origination Date": orig_date,
            "Payment Freq": random.choice(["Quarterly", "Monthly"]),
            "Industry": random.choice(INDUSTRIES),
            "Rating Moodys": curr_rtg,
            "Original Rating": orig_rtg,
            "Lien": "1L",
            "Facility Type": "Term Loan",
            "Warehouse": warehouse_name
        }
        data.append(item)
    
    df = pd.DataFrame(data)
    
    # Save
    # Format: YYYYMMDD(AsOf)_HHMMSS(Upload)_WarehouseName
    as_of_str = as_of_date.strftime("%Y%m%d")
    upload_ts = datetime.now().strftime("%H%M%S") # Fake upload time (now)
    
    filename = f"{as_of_str}_{upload_ts}_{warehouse_name}.xlsx"
    df.to_excel(OUTPUT_DIR / filename, index=False)
    print(f"Generated {filename}")

if __name__ == "__main__":
    setup_configs()
    
    # Generate history for trends
    today = datetime.today()
    dates = [today - timedelta(days=x) for x in range(0, 90, 14)] # 3 months history
    
    for d in dates:
        # Alpha: BSL, large, stable
        generate_tape("Warehouse_Alpha", 55, as_of_date=d)
        
        # Beta: MM, higher spread, slightly smaller
        generate_tape("Warehouse_Beta", 65, as_of_date=d)
        
        # Gamma: Ramp up
        if d > today - timedelta(days=40):
             generate_tape("Warehouse_Gamma", 35, as_of_date=d)

