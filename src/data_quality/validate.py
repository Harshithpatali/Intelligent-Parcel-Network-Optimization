import pandas as pd
DEMAND_COLUMNS={'date','origin_hub','destination_hub','parcel_count'}
PARCEL_COLUMNS={'parcel_id','origin_hub','destination_hub','weight_kg','volume_m3'}
def validate_frame(df,required,name):
    missing=required-set(df.columns)
    if missing: raise ValueError(f'{name}: missing columns {sorted(missing)}')
    if df.empty: raise ValueError(f'{name}: empty dataset')
    if df.columns.duplicated().any(): raise ValueError(f'{name}: duplicate columns')
    return True
def validate_demand(df):
    validate_frame(df,DEMAND_COLUMNS,'demand')
    if pd.to_numeric(df.parcel_count,errors='coerce').isna().any(): raise ValueError('demand: parcel_count contains non-numeric values')
    if (df.parcel_count<0).any(): raise ValueError('demand: negative parcel_count')
    return True
def validate_parcels(df):
    validate_frame(df,PARCEL_COLUMNS,'parcels')
    for c in ['weight_kg','volume_m3']:
        if pd.to_numeric(df[c],errors='coerce').fillna(-1).lt(0).any(): raise ValueError(f'parcels: invalid {c}')
    return True
