from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()
ROOT=Path(__file__).resolve().parents[2]
DATA_DIR=ROOT/os.getenv('DATA_DIR','data'); ARTIFACT_DIR=ROOT/os.getenv('ARTIFACT_DIR','data/artifacts'); LOG_DIR=ROOT/os.getenv('LOG_DIR','logs')
for p in (DATA_DIR,ARTIFACT_DIR,LOG_DIR): p.mkdir(parents=True,exist_ok=True)
APP_ENV=os.getenv('APP_ENV','development'); LOG_LEVEL=os.getenv('LOG_LEVEL','INFO'); API_KEY=os.getenv('API_KEY','')
SUPABASE_URL=os.getenv('SUPABASE_URL','').rstrip('/'); SUPABASE_SERVICE_ROLE_KEY=os.getenv('SUPABASE_SERVICE_ROLE_KEY','')
OSRM_BASE_URL=os.getenv('OSRM_BASE_URL','https://router.project-osrm.org').rstrip('/')
MODEL_VERSION=os.getenv('MODEL_VERSION','baseline-1.0.0'); OPTIMIZER_VERSION=os.getenv('OPTIMIZER_VERSION','network-1.0.0'); MAX_REQUEST_ROWS=int(os.getenv('MAX_REQUEST_ROWS','50000')); ALLOWED_ORIGINS=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','*').split(',') if x.strip()]
