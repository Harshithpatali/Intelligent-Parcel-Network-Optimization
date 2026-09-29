import os,sys
from pathlib import Path
import requests,pandas as pd
from dotenv import load_dotenv
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data.olist import TABLES,fetch_table,build_logistics_fact
load_dotenv()
out=Path('data/olist'); out.mkdir(parents=True,exist_ok=True)
for table in TABLES:
    df=fetch_table(table); df.to_parquet(out/f'{table}.parquet',index=False); print(f'{table}: {len(df):,}')
orders= pd.read_parquet(out/'olist_orders.parquet'); items=pd.read_parquet(out/'olist_order_items.parquet'); customers=pd.read_parquet(out/'olist_customers.parquet'); sellers=pd.read_parquet(out/'olist_sellers.parquet'); geo=pd.read_parquet(out/'olist_geolocation.parquet')
products=pd.read_parquet(out/'olist_products.parquet')
fact=build_logistics_fact(orders,items,customers,sellers,geo)
fact=fact.merge(products[['product_id','product_category_name','product_weight_g','product_length_cm','product_height_cm','product_width_cm']],on='product_id',how='left',suffixes=('','_p')) if 'product_category_name' not in fact.columns else fact
fact.to_parquet(out/'logistics_fact_orders.parquet',index=False)
print(f'logistics_fact_orders: {len(fact):,} rows')
print(f'geolocation coverage: {fact.has_geolocation.mean()*100:.2f}%')
print(f'orders: {fact.order_id.nunique():,}')
