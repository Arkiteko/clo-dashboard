import pandas as pd
from pathlib import Path
from src.models import Asset
from src.utils import load_excel_safe
from src.validation import run_all_checks

class ETLPipeline:
    def __init__(self, raw_dir: Path, staging_dir: Path, standard_dir: Path):
        self.raw_dir = raw_dir
        self.staging_dir = staging_dir
        self.standard_dir = standard_dir

    def process_tape(self, file_path: Path):
        """
        Full run: Raw -> Staging -> Standard -> Validation
        """
        # 1. Parse (Layer 1)
        df_staging = load_excel_safe(file_path)
        if df_staging.empty:
            return None, ["Failed to parse Excel file"]

        # 2. Map (Layer 2) - This is where the 'Standard Template' logic applies
        # We assume the user uploads the Standard Template directly for now, 
        # or we map best-effort.
        
        # Simple mapping assuming column names match or are close
        # In a real app, we'd have a config map.
        canonical_map = {
            "Asset ID": "asset_id",
            "Issuer": "issuer_name",
            "Borrower": "borrower_name",
            "Par": "par_amount",
            "Currency": "currency",
            "Market Price": "market_price",
            "Market Value": "market_value",
            "Industry": "industry_gics",
            "Spread": "spread",
            "Coupon": "coupon",
            "Floor": "floor",
            "Maturity Date": "maturity_date",
            "Origination Date": "origination_date",
            "Payment Freq": "payment_frequency",
            "Rating Moodys": "rating_moodys",
            "Rating SP": "rating_sp",
            "Original Rating": "original_rating_moodys",
            "Lien": "lien_type",
            "Facility Type": "facility_type",
            "Country": "country",
            "Cov Lite": "is_cov_lite",
            "PIK": "is_pik",
            "Defaulted": "is_defaulted",
        }
        
        df_std = df_staging.rename(columns=canonical_map)
        
        # 3. Validation (Layer 3)
        issues = run_all_checks(df_std)
        
        if not issues:
             return self.publish(df_std, file_path.stem), issues
        
        # If soft issues only, we might still publish, but let's stick to strict or user-gated for now.
        # For this demo, let's publish if no HARD errors.
        hard_errors = [i for i in issues if i.severity == "HARD"]
        if not hard_errors:
            self.publish(df_std, file_path.stem)
            
        return df_std, issues

    def publish(self, df: pd.DataFrame, source_id: str):
        """
        Save to published layer.
        """
        # Ensure dir exists
        (self.standard_dir / ".." / "3_published").mkdir(parents=True, exist_ok=True)
        
        out_path = self.standard_dir / ".." / "3_published" / f"{source_id}.parquet"
        df.to_parquet(out_path)
        return df

