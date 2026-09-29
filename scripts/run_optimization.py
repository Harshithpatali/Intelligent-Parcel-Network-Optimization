import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data.demo import generate_demo
from src.optimization.network import solve_network
D,_,H=generate_demo(); d=D[D.date==D.date.max()].groupby(['origin_hub','destination_hub'],as_index=False).parcel_count.sum(); flows,m=solve_network(d,H); print(m); Path('data/artifacts').mkdir(parents=True,exist_ok=True); flows.to_csv('data/artifacts/optimized_flows.csv',index=False)
