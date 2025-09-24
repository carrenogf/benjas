import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore as admin_fs
from google.cloud import firestore as gcfs
from datetime import date, datetime
from utils import get_dashboard_data

# --- Inicialización Firebase ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["FIREBASE"]))
    firebase_admin.initialize_app(cred)
db = admin_fs.client()


def gastos_ui():
    st.subheader("📉 Registro de Gastos")

    with st.form("nuevo_gasto"):
        fecha_gasto = st.date_input("Fecha del Gasto", value=date.today())
        concepto = st.selectbox("Concepto", ["insumos", "alquiler", "servicios", "mantenimiento", "marketing", "otros"])
        proveedor = st.text_input("Proveedor")
        descripcion = st.text_area("Descripción")
        metodo_pago = st.selectbox("Método de pago", ["efectivo", "débito", "crédito", "transferencia", "qr", "mp"])
        monto = st.number_input("Monto (ARS)", min_value=0.0, step=100.0)
        submitted = st.form_submit_button("➕ Registrar")

        if submitted and monto > 0:
            doc = {
                "fecha": datetime.combine(fecha_gasto, datetime.min.time()),
                "concepto": concepto,
                "proveedor": proveedor,
                "descripcion": descripcion,
                "metodo_pago": metodo_pago,
                "monto_centavos": int(monto * 100),
                "created_at": gcfs.SERVER_TIMESTAMP,
                "updated_at": gcfs.SERVER_TIMESTAMP,
            }
            db.collection("gastos").add(doc)
            st.success("Gasto registrado ✅")
            # Limpiar la caché del dashboard para que refleje el nuevo gasto
            get_dashboard_data.clear()

    st.divider()
    st.subheader("Últimos Gastos Registrados")
    gastos = db.collection("gastos").order_by("fecha", direction=admin_fs.Query.DESCENDING).limit(10).stream()

    # Encabezados para la lista
    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
    col1.markdown("**Fecha**")
    col2.markdown("**Concepto**")
    col3.markdown("**Proveedor**")
    col4.markdown("**Monto**")

    for g in gastos:
        d = g.to_dict()
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
        col1.write(d["fecha"].strftime("%Y-%m-%d %H:%M"))
        col2.write(d.get("concepto", "N/A"))
        col3.write(d.get("proveedor", "N/A"))
        col4.write(f"${d['monto_centavos']/100:,.2f}")
        if col5.button("🗑️", key=g.id, help="Eliminar gasto"):
            db.collection("gastos").document(g.id).delete()
            st.warning(f"Gasto de '{d['concepto']}' eliminado.")
            st.rerun()

gastos_ui()