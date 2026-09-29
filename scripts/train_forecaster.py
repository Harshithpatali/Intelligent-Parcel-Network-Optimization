from pathlib import Path
import sys,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.models.forecast import fit_forecaster
root=Path(__file__).resolve().parents[1]; result=fit_forecaster(pd.read_csv(root/'data/demo_demand.csv'),root/'data/artifacts/forecast_metrics.json',root/'data/artifacts/forecast_model.joblib'); print(result)
