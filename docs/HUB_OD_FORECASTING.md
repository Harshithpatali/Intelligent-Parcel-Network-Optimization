# Hub-to-Hub Demand Forecasting

## Dataset

The real Olist-derived network currently contains:

- 20 candidate hubs
- 264 observed hub-to-hub OD pairs
- 112,077 assigned item rows
- 27,475 observed daily OD rows
- 2016-09-04 through 2018-09-03

The forecasting panel zero-fills each observed OD pair for every calendar day. After a 28-day warm-up for lag features, the feature dataset contains **185,328 rows**.

## Leakage-safe features

For prediction date t, features use only dates < t:

- lag 1 day
- lag 7 days
- lag 14 days
- lag 28 days
- lagged weight and volume
- trailing 7-day mean
- trailing 28-day mean
- trailing 28-day standard deviation
- day of week
- month
- day of month
- day of year
- route distance

The rolling windows explicitly end at t-1.

## Evaluation

The final 28 calendar days are held out chronologically:

- Train: **177,936 rows**
- Test: **7,392 rows**
- Test period: **2018-08-07 through 2018-09-03**

The primary baseline is the 7-day seasonal naive forecast: prediction(t) = demand(t-7).

The main model is XGBoost regression. Metrics are WAPE, MAE, and RMSE.

## Why this matters

This is not a random train/test split. A logistics forecasting system must predict future demand from past demand, so chronological validation prevents future observations from leaking into training.

The forecast output is designed to feed the prescriptive optimization layer:

forecast OD demand -> route/fleet/capacity constraints -> OR-Tools network allocation

Run:

python scripts/train_hub_od_forecaster.py

The script writes predictions and metrics to Supabase and saves a versioned local model artifact under artifacts/hub_od_forecast/.
