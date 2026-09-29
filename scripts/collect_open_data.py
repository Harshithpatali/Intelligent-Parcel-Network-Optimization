import argparse,json,os
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'/'open'; OUT.mkdir(parents=True,exist_ok=True)
def ibge_municipalities():
 r=requests.get('https://servicodados.ibge.gov.br/api/v1/localidades/municipios',timeout=60); r.raise_for_status(); (OUT/'ibge_municipalities.json').write_text(json.dumps(r.json(),ensure_ascii=False)); print('IBGE municipalities:',len(r.json()))
def holidays(year):
 key=os.getenv('FERIADOS_API_KEY')
 if not key: print('Skipping holidays: set FERIADOS_API_KEY'); return
 r=requests.get(f'https://api.feriados.dev/v1/holidays/year/{year}',headers={'X-API-Key':key},timeout=30); r.raise_for_status(); (OUT/f'holidays_{year}.json').write_text(json.dumps(r.json(),ensure_ascii=False))
def source_manifest():
 m={'osm_brazil_pbf':'https://download.geofabrik.de/south-america/brazil-latest.osm.pbf','osm_sudeste_pbf':'https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf','osm_sul_pbf':'https://download.geofabrik.de/south-america/brazil/sul-latest.osm.pbf','inmet_bdmeP':'https://bdmep.inmet.gov.br/','osrm':'https://router.project-osrm.org/','ibge':'https://servicodados.ibge.gov.br/api/v1/localidades/municipios','feriados':'https://api.feriados.dev/'}; (OUT/'source_manifest.json').write_text(json.dumps(m,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--year',type=int,default=2018); p.add_argument('--ibge',action='store_true'); p.add_argument('--holidays',action='store_true'); p.add_argument('--manifest',action='store_true'); a=p.parse_args(); ibge_municipalities() if a.ibge else None; holidays(a.year) if a.holidays else None; source_manifest()
