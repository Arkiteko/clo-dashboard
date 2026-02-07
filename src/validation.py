from typing import List, Dict, Any
import pandas as pd
from src.models import Asset, ValidationIssue

def check_schema_completeness(df: pd.DataFrame, required_cols: List[str]) -> List[ValidationIssue]:
    issues = []
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        issues.append(ValidationIssue(
            severity="HARD",
            message=f"Missing required columns: {missing}"
        ))
    return issues

def check_integrity(df: pd.DataFrame) -> List[ValidationIssue]:
    issues = []
    # 1. Start Date vs End Date (Maturity vs Trade? No, usually Trade vs Settle)
    # This is better done on the Pydantic model or row-wise
    
    # 2. Duplicate Keys
    if "asset_id" in df.columns:
        dupes = df[df.duplicated(subset=["asset_id"], keep=False)]
        if not dupes.empty:
             issues.append(ValidationIssue(
                severity="HARD",
                message=f"Duplicate asset_ids found: {len(dupes)} duplicates",
                row_id=str(dupes["asset_id"].tolist()[:5])
            ))
            
    return issues

def check_domain_logic(df: pd.DataFrame) -> List[ValidationIssue]:
    issues = []
    
    # Price bounds
    if "market_price" in df.columns:
        # Check for numeric types first
        numeric_prices = pd.to_numeric(df["market_price"], errors='coerce')
        outliers = df[(numeric_prices < 20) | (numeric_prices > 120)]
        if not outliers.empty:
             issues.append(ValidationIssue(
                severity="SOFT",
                message=f"Found {len(outliers)} assets with price < 20 or > 120",
                row_id=str(outliers["asset_id"].tolist()[:5])
            ))
            
    return issues

def run_all_checks(df: pd.DataFrame) -> List[ValidationIssue]:
    all_issues = []
    # Define required columns for canonical layer
    required = ["asset_id", "par_amount", "issuer_name"]
    
    all_issues.extend(check_schema_completeness(df, required))
    all_issues.extend(check_integrity(df))
    all_issues.extend(check_domain_logic(df))
    
    return all_issues
