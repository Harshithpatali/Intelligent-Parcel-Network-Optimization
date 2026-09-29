import os,pandas as pd
TABLES=['olist_orders','olist_order_items','olist_customers','olist_products','olist_sellers','olist_geolocation']
def _request(table,offset,limit):
 import requests
 url=os.getenv('SUPABASE_URL','').rstrip('/'); key=os.getenv('SUPABASE_SERVICE_ROLE_KEY','')
 if not url or not key: raise RuntimeError('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required')
 r=requests.get(f'{url}/rest/v1/{table}',headers={'apikey':key,'Authorization':f'Bearer {key}'},params={'select':'*','offset':offset,'limit':limit},timeout=30); r.raise_for_status(); return r.json()
def fetch_table(table,limit=None,page_size=1000):
 rows=[]; offset=0
 while True:
  n=min(page_size,max(0,limit-len(rows))) if limit is not None else page_size
  if n==0: break
  batch=_request(table,offset,n); rows.extend(batch)
  if not batch or len(batch)<page_size or (limit is not None and len(rows)>=limit): break
  offset+=page_size
 return pd.DataFrame(rows)
def build_logistics_fact(orders,items,customers,sellers,geo):
 o=orders.copy(); i=items.copy(); c=customers.copy(); s=sellers.copy(); g=geo.drop_duplicates('geolocation_zip_code_prefix').copy()
 for df,col in [(o,'order_purchase_timestamp'),(o,'order_delivered_customer_date'),(o,'order_estimated_delivery_date'),(i,'shipping_limit_date')]:
  if col in df: df[col]=pd.to_datetime(df[col],errors='coerce')
 x=i.merge(o[['order_id','customer_id','order_status','order_purchase_timestamp','order_delivered_customer_date','order_estimated_delivery_date']],on='order_id',how='left').merge(c[['customer_id','customer_zip_code_prefix','customer_city','customer_state']],on='customer_id',how='left').merge(s[['seller_id','seller_zip_code_prefix','seller_city','seller_state']],on='seller_id',how='left')
 x=x.merge(g.rename(columns={'geolocation_zip_code_prefix':'customer_zip_code_prefix','geolocation_lat':'customer_lat','geolocation_lng':'customer_lng'})[['customer_zip_code_prefix','customer_lat','customer_lng']],on='customer_zip_code_prefix',how='left')
 x=x.merge(g.rename(columns={'geolocation_zip_code_prefix':'seller_zip_code_prefix','geolocation_lat':'seller_lat','geolocation_lng':'seller_lng'})[['seller_zip_code_prefix','seller_lat','seller_lng']],on='seller_zip_code_prefix',how='left')
 x['purchase_date']=x.order_purchase_timestamp.dt.floor('D'); x['delivery_delay_days']=(x.order_delivered_customer_date-x.order_estimated_delivery_date).dt.total_seconds()/86400; return x
