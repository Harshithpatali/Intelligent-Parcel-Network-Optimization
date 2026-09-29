from pathlib import Path
import sys,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data_quality.validate import validate_demand,validate_parcels
root=Path(__file__).resolve().parents[1]; validate_demand(pd.read_csv(root/'data/demo_demand.csv')); validate_parcels(pd.read_csv(root/'data/demo_parcels.csv')); print('Data quality checks passed')
