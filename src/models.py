from datetime import date, datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"

class Asset(BaseModel):
    """
    Canonical representation of a single loan/asset.
    """
    # Keys
    asset_id: str = Field(..., description="Unique immutable identifier for the asset")
    
    # Issuer / Description
    issuer_name: str
    borrower_name: Optional[str] = None
    
    # Financials
    par_amount: float
    currency: Currency = Currency.USD
    fx_rate: float = Field(default=1.0, description="Exchange rate to base currency")
    market_price: Optional[float] = Field(None, description="Price as percentage of par (e.g. 98.5)")
    market_value: Optional[float] = None
    
    # Rates
    spread: Optional[float] = None
    coupon: Optional[float] = None
    floor: Optional[float] = 0.0
    index: Optional[str] = "SOFR"
    maturity_date: Optional[date] = None
    
    # Classification
    industry_gics: Optional[str] = None
    industry_internal: Optional[str] = None
    country: Optional[str] = "US"
    lien_type: Optional[str] = Field(None, description="1L, 2L, Unsecured")
    facility_type: Optional[str] = Field(None, description="Term Loan, Revolver")
    
    # Life / Amortization
    origination_date: Optional[date] = None
    payment_frequency: str = "Quarterly" # Monthly, Quarterly, Semi-Annual
    
    # Flags
    is_cov_lite: bool = False
    is_pik: bool = False
    is_defaulted: bool = False
    
    # Ratings (Current)
    rating_moodys: Optional[str] = None
    rating_sp: Optional[str] = None
    rating_fitch: Optional[str] = None
    
    # Ratings (Original - for migration)
    original_rating_moodys: Optional[str] = None

    # Extension
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Extension bag for extra fields")

    @field_validator('currency', mode='before')
    def unknown_currency_to_usd(cls, v):
        if not v:
            return "USD"
        return v.upper()

class WarehousePosition(BaseModel):
    """
    Link between an Asset and a Warehouse Facility.
    """
    warehouse_id: str
    asset_id: str
    position_id: Optional[str] = None
    
    funded_amount: float = 0.0
    unfunded_commitment: float = 0.0
    
    advance_rate: Optional[float] = None
    borrowing_base_eligible: bool = True
    
    trade_date: Optional[date] = None
    settle_date: Optional[date] = None

class WarehouseFacility(BaseModel):
    """
    Warehouse facility metadata and limits.
    """
    warehouse_id: str
    counterparty: str
    
    max_commitment: float
    current_outstanding: float
    
    cash_balance: float = 0.0
    equity_nav: Optional[float] = None
    
    # Limits
    bsl_sublimit: Optional[float] = None
    mm_sublimit: Optional[float] = None
    
    # Compliance
    oc_ratio: Optional[float] = None
    min_oc_requirement: Optional[float] = None
    
    as_of_date: date

class ValidationIssue(BaseModel):
    severity: str # "HARD", "SOFT"
    message: str
    row_id: Optional[str] = None
    column: Optional[str] = None
    value: Any = None


# ── Alert System Models ───────────────────────────────────────────────

class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class AlertConfig(BaseModel):
    """Configurable alert thresholds per warehouse."""
    # Proximity warning margin (fraction of limit value)
    proximity_margin: float = 0.10  # 10%

    # Data staleness thresholds (days)
    stale_warning_days: int = 7
    stale_critical_days: int = 14

    # Risk metric thresholds
    warf_warning: float = 3000.0
    warf_critical: float = 3500.0
    diversity_warning: float = 40.0

    # Utilization
    utilization_warning: float = 0.90

    # Disabled rules (list of rule_id strings)
    disabled_rules: List[str] = Field(default_factory=list)


class Alert(BaseModel):
    """A single alert instance."""
    alert_id: str
    warehouse: str
    severity: AlertSeverity
    category: str  # "Compliance", "Concentration", "Data Quality", "Threshold Proximity", "Risk"
    title: str
    detail: str
    metric_name: str
    current_value: float
    threshold_value: float
    timestamp: datetime = Field(default_factory=datetime.now)
