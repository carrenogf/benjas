import streamlit as st
import firebase_admin
from firebase_admin import credentials
import pandas as pd
from datetime import datetime
from calendar import monthrange

# --- Inicialización Firebase ---
# Esta función asegura que la app de Firebase se inicialice solo una vez.
def initialize_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["FIREBASE"]))
        firebase_admin.initialize_app(cred)
    return firebase_admin.firestore.client()

db = initialize_firebase()

@st.cache_data(ttl=600) # Cache por 10 minutos
def get_dashboard_data(year, month):
    """
    Obtiene los datos de ingresos y gastos para un mes y año específicos desde Firebase.
    Es mucho más eficiente que traer todos los datos y filtrarlos en pandas.
    """
    # Calcular el primer y último día del mes
    _, num_days = monthrange(year, month)
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, num_days, 23, 59, 59)

    # --- Traer ingresos del mes ---
    ingresos_query = db.collection("ingresos").where("fecha", ">=", start_date).where("fecha", "<=", end_date).stream()
    ingresos_data = [i.to_dict() for i in ingresos_query]
    df_ing = pd.DataFrame(ingresos_data)
    if not df_ing.empty:
        df_ing["fecha"] = pd.to_datetime(df_ing["fecha"])
        df_ing["monto_total"] = df_ing["monto_total_centavos"] / 100

    # --- Traer gastos del mes ---
    gastos_query = db.collection("gastos").where("fecha", ">=", start_date).where("fecha", "<=", end_date).stream()
    gastos_data = [g.to_dict() for g in gastos_query]
    df_gas = pd.DataFrame(gastos_data)
    if not df_gas.empty:
        df_gas["fecha"] = pd.to_datetime(df_gas["fecha"])
        df_gas["monto"] = df_gas["monto_centavos"] / 100

    return df_ing, df_gas