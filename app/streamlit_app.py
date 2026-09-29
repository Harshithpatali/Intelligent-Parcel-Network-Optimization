import os,requests,pandas as pd,streamlit as st,plotly.express as px
API_URL=os.getenv('API_URL','http://127.0.0.1:8000'); st.set_page_config(page_title='Parcel Network Control Tower',layout='wide'); st.title('Intelligent Parcel Network Optimization'); st.caption('Predictive + prescriptive logistics prototype calibrated from Olist/open data; synthetic network layer.')
try: requests.get(f'{API_URL}/health',timeout=2).raise_for_status()
except Exception as e: st.error(f'API unavailable: {e}'); st.stop()
m=requests.get(f'{API_URL}/summary',timeout=5).json(); n=requests.get(f'{API_URL}/network',timeout=5).json(); c1,c2,c3=st.columns(3); c1.metric('Demo parcels',m['orders_demo']); c2.metric('Demand rows',m['demand_rows']); c3.metric('Hubs',m['hubs'])
st.subheader('Network'); hubs=pd.DataFrame(n['hubs']); st.dataframe(hubs,use_container_width=True,hide_index=True); st.plotly_chart(px.scatter(hubs,x='lon',y='lat',size='capacity_parcels',text='hub_id',hover_name='city',title='Candidate logistics hubs'),use_container_width=True)
st.subheader('Optimization'); a,b=st.columns(2); surge=a.slider('Demand multiplier',.5,2.0,1.0,.05); cap=b.slider('Capacity multiplier',.5,1.2,1.0,.05)
if st.button('Run network optimization',type='primary'):
 r=requests.post(f'{API_URL}/optimize',json={'demand_multiplier':surge,'capacity_multiplier':cap},timeout=20); st.dataframe(pd.DataFrame(r.json()['flows']),use_container_width=True,hide_index=True) if r.ok else st.error(r.text)
st.subheader('Disruption simulator'); scenario=st.selectbox('Scenario',['demand_surge','hub_outage','combined'])
if st.button('Run scenario'):
 r=requests.post(f'{API_URL}/scenario',json={'scenario':scenario},timeout=20); st.json(r.json()['metrics']) if r.ok else st.error(r.text)
