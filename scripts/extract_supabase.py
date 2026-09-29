import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from src.data.olist import TABLES,fetch_table
load_dotenv(); out=Path('data/olist'); out.mkdir(parents=True,exist_ok=True)
for t in TABLES:
 df=fetch_table(t); df.to_parquet(out/f'{t}.parquet',index=False); print(t,len(df))
