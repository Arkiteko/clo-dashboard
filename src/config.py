import json
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel

CONFIG_PATH = Path("data/warehouse_config.json")

class WarehouseConfig(BaseModel):
    max_facility_amount: float = 100_000_000.0
    advance_rate: float = 0.80
    oc_trigger_pct: float = 1.25  # 125%
    min_spread: float = 2.50
    concentration_limit_industry: float = 0.15 # 15%
    warehouse_type: str = "BSL" # "BSL" or "Middle Market"

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
