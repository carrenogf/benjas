import streamlit as st
import firebase_admin
from firebase_admin import credentials
from google.cloud import firestore as gcfs
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
    Obtiene los datos de ingresos, gastos y membresías para un mes y año específicos desde Firebase.
    Es mucho más eficiente que traer todos los datos y filtrarlos en pandas.
    """
    # Calcular el primer y último día del mes
    _, num_days = monthrange(year, month)
    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, num_days, 23, 59, 59)

    # --- Traer ingresos del mes ---
    ingresos_query = db.collection("ingresos").where(filter=gcfs.FieldFilter("fecha", ">=", start_date)).where(filter=gcfs.FieldFilter("fecha", "<=", end_date)).stream()
    ingresos_data = [i.to_dict() for i in ingresos_query]
    df_ing = pd.DataFrame(ingresos_data)
    if not df_ing.empty:
        df_ing["fecha"] = pd.to_datetime(df_ing["fecha"])
        df_ing["monto_total"] = df_ing["monto_total_centavos"] / 100

    # --- Traer gastos del mes ---
    gastos_query = db.collection("gastos").where(filter=gcfs.FieldFilter("fecha", ">=", start_date)).where(filter=gcfs.FieldFilter("fecha", "<=", end_date)).stream()
    gastos_data = [g.to_dict() for g in gastos_query]
    df_gas = pd.DataFrame(gastos_data)
    if not df_gas.empty:
        df_gas["fecha"] = pd.to_datetime(df_gas["fecha"])
        df_gas["monto"] = df_gas["monto_centavos"] / 100

    # --- Traer membresías del mes (por fecha de alta) ---
    membresias_query = db.collection("membresias").where(filter=gcfs.FieldFilter("fecha_alta", ">=", start_date)).where(filter=gcfs.FieldFilter("fecha_alta", "<=", end_date)).stream()
    membresias_data = []
    for m in membresias_query:
        data = m.to_dict()
        # Obtener información del cliente
        if "dni_cliente" in data:
            cliente_doc = db.collection("clientes").document(data["dni_cliente"]).get()
            if cliente_doc.exists:
                cliente_info = cliente_doc.to_dict()
                data["nombre_cliente"] = cliente_info.get("nombre", "Cliente no encontrado")
            else:
                data["nombre_cliente"] = "Cliente no encontrado"
        membresias_data.append(data)
    
    df_membresias = pd.DataFrame(membresias_data)
    if not df_membresias.empty:
        df_membresias["fecha_alta"] = pd.to_datetime(df_membresias["fecha_alta"])
        df_membresias["fecha_vencimiento"] = pd.to_datetime(df_membresias["fecha_vencimiento"])
        df_membresias["precio"] = df_membresias["precio_centavos"] / 100
        
        # Añadir columna de fuente para distinguir en los gráficos
        df_membresias["fuente"] = "Membresías"
        
        # Añadir columna de método de pago formateado para visualización
        if "metodo_pago" in df_membresias.columns:
            df_membresias["metodo_pago_display"] = df_membresias["metodo_pago"].map({
                "efectivo": "Efectivo",
                "transferencia": "Transferencia", 
                "debito_automatico": "Débito Automático"
            }).fillna("Efectivo")  # Default para registros antiguos

    return df_ing, df_gas, df_membresias