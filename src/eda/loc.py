import pandas as pd
import os



geolocation = pd.read_csv('./Dados/Brazilian Logistic/olist_geolocation_dataset.csv')
sellers = pd.read_csv('./Dados/Brazilian Logistic/olist_sellers_dataset.csv')

# Somente 220 pedidos não tem a coordenada do vendedor, então dá pra dropar sem usar API de cep.
sellers_ceps = sellers[['seller_zip_code_prefix', 'seller_id']]
geolocation_ceps = geolocation[['geolocation_zip_code_prefix', 'geolocation_lat', 'geolocation_lng']].groupby('geolocation_zip_code_prefix', as_index=False)[['geolocation_lat', 'geolocation_lng']].first()
geolocation_ceps['seller_zip_code_prefix'] = geolocation_ceps['geolocation_zip_code_prefix'].copy()
merge = sellers_ceps.merge(geolocation_ceps, on="seller_zip_code_prefix", how="left")
print(merge[merge["seller_zip_code_prefix"].notna() & merge["geolocation_zip_code_prefix"].isna()])


