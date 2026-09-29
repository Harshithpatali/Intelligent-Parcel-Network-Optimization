import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.data.demo import write_demo
if __name__=='__main__': write_demo(Path(__file__).resolve().parents[1]); print('Demo data written to data/')
