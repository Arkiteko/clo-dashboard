import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from src.models import AlertConfig

CONFIG_PATH = Path("data/warehouse_config.json")


class StressConfig(BaseModel):
    """Configurable stress parameters per warehouse."""
    # Price shock haircuts (points off market_price) by rating tier
    price_shock_ig: float = 1.0
    price_shock_bb: float = 3.0
    price_shock_b: float = 5.0
    price_shock_ccc: float = 15.0

    # Conditional default rates by rating tier
    cdr_ig: float = 0.005
    cdr_bb: float = 0.02
    cdr_b: float = 0.05
    cdr_ccc: float = 0.15

    # Recovery rates by lien type
    recovery_1l: float = 0.65
    recovery_2l: float = 0.35
    recovery_unsecured: float = 0.15

    # Spread shocks (bps) by rating tier
    spread_shock_ig: float = 50.0
    spread_shock_bb: float = 100.0
    spread_shock_b: float = 200.0
    spread_shock_ccc: float = 500.0

    # Downgrade migration rate (fraction of assets migrated one notch)
    migration_rate: float = 0.10

    # Concentration: number of top obligors to stress-default
    concentration_top_n: int = 3


class WarehouseConfig(BaseModel):
    max_facility_amount: float = 100_000_000.0
    advance_rate: float = 0.80
    oc_trigger_pct: float = 1.25  # 125%
    min_spread: float = 2.50
    concentration_limit_industry: float = 0.15 # 15%
    warehouse_type: str = "BSL" # "BSL" or "Middle Market"
    stress_config: StressConfig = StressConfig()
    # Compliance sublimits
    max_single_name_pct: float = 0.02       # 2% max single issuer
    max_second_lien_pct: float = 0.10       # 10% max second lien
    max_unsecured_pct: float = 0.05         # 5% max unsecured
    max_ccc_pct: float = 0.075              # 7.5% max CCC bucket
    # Ramp tracker
    target_ramp_amount: Optional[float] = None  # Target total par at close
    target_close_date: Optional[str] = None     # ISO format YYYY-MM-DD
    # Alert configuration
    alert_config: AlertConfig = AlertConfig()

    def to_dict(self):
        return self.model_dump()

def load_config() -> Dict[str, dict]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except:
        return {}

def get_warehouse_config(warehouse_name: str) -> WarehouseConfig:
    data = load_config()
    cfg = data.get(warehouse_name, {})
    return WarehouseConfig(**cfg)

def save_warehouse_config(warehouse_name: str, config: WarehouseConfig):
    data = load_config()
    data[warehouse_name] = config.to_dict()
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)

def list_configured_warehouses():
    return list(load_config().keys())
