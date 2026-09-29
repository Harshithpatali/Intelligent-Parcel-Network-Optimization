from pathlib import Path
import json,joblib,numpy as np,pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.ensemble import HistGradientBoostingRegressor
FEATURES=['dow','month','lag_1','lag_7','lag_14','rolling_7','rolling_28']; MODEL_NAME='parcel-demand-hgb'; MODEL_VERSION='1.0.0'
def make_features(demand):
 req={'date','origin_hub','destination_hub','parcel_count'}; missing=req-set(demand.columns)
 if missing: raise ValueError(f'Missing demand columns: {sorted(missing)}')
 df=demand.copy(); df.date=pd.to_datetime(df.date,errors='raise'); df.parcel_count=pd.to_numeric(df.parcel_count,errors='raise').clip(lower=0); df=df.sort_values(['origin_hub','destination_hub','date']); g=df.groupby(['origin_hub','destination_hub'],group_keys=False); df['dow']=df.date.dt.dayofweek; df['month']=df.date.dt.month; df['lag_1']=g.parcel_count.shift(1); df['lag_7']=g.parcel_count.shift(7); df['lag_14']=g.parcel_count.shift(14); df['rolling_7']=g.parcel_count.transform(lambda s:s.shift(1).rolling(7).mean()); df['rolling_28']=g.parcel_count.transform(lambda s:s.shift(1).rolling(28).mean()); return df
def fit_forecaster(demand,artifact_path=None,model_path=None):
 f=make_features(demand).dropna(subset=FEATURES+['parcel_count'])
 if len(f)<50:return {'model_name':MODEL_NAME,'model_version':MODEL_VERSION,'model_type':'seasonal_naive','forecast':float(demand.parcel_count.tail(7).mean()),'test_mae':None,'n_train':0,'n_test':0}
 cutoff=f.date.max()-pd.Timedelta(days=max(7,int(max(1,(f.date.max()-f.date.min()).days)*.15))); tr=f[f.date<cutoff]; te=f[f.date>=cutoff]
 if tr.empty or te.empty: raise ValueError('Time-series split produced an empty train/test set')
 model=HistGradientBoostingRegressor(max_iter=250,learning_rate=.07,max_leaf_nodes=15,random_state=42); model.fit(tr[FEATURES],tr.parcel_count); pred=model.predict(te[FEATURES]); mae=mean_absolute_error(te.parcel_count,pred); last=f.sort_values('date').groupby(['origin_hub','destination_hub']).tail(1).copy(); last.date+=pd.Timedelta(days=1); forecast=float(np.maximum(model.predict(last[FEATURES]),0).sum()); result={'model_name':MODEL_NAME,'model_version':MODEL_VERSION,'model_type':'hist_gradient_boosting','features':FEATURES,'test_mae':float(mae),'forecast_total_next_day':forecast,'n_train':len(tr),'n_test':len(te),'train_end':str(tr.date.max().date()),'validation_start':str(te.date.min().date())}
 if artifact_path: Path(artifact_path).write_text(json.dumps(result,indent=2))
 if model_path: Path(model_path).parent.mkdir(parents=True,exist_ok=True); joblib.dump(model,model_path)
 return result
