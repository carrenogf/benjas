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


@st.cache_data
def get_productos():
    """Obtiene los productos activos de Firebase y los cachea."""
    # Consulta 1: Productos donde 'activo' es explícitamente True
    productos_activos_ref = db.collection("productos").where("activo", "==", True).stream()
    
    # Consulta 2: Productos donde el campo 'activo' no existe (para compatibilidad con datos antiguos)
    productos_sin_campo_activo_ref = db.collection("productos").where("activo", "==", None).stream()

    productos_dict = {}
    # Usamos un diccionario para evitar duplicados si un producto apareciera en ambas consultas (poco probable)
    
    # Procesar la primera consulta
    for p in productos_activos_ref:
        prod_data = p.to_dict()
        productos_dict[p.id] = prod_data
        productos_dict[p.id]['id'] = p.id

    # La segunda consulta no es necesaria con la lógica actual de creación, pero es una buena práctica para robustez.
    # En este caso, la lógica de creación siempre añade 'activo': True, por lo que la primera consulta es suficiente.
    return list(productos_dict.values())


def ingresos_ui():
    st.subheader("💵 Registro de Ingresos")

    # Limpiar la caché de productos cada vez que se carga la página para asegurar datos frescos.
    get_productos.clear()

    productos = get_productos()
    product_names = ["-- Ingreso Manual --"] + [p['nombre'] for p in productos]
    product_map = {p['nombre']: p for p in productos}

    selected_product_name = st.selectbox(
        "Producto/Servicio (opcional)", 
        options=product_names,
        help="Selecciona un producto para autocompletar el precio. El campo de monto se actualizará automáticamente."
    )

    initial_monto = 0.0
    if selected_product_name != "-- Ingreso Manual --":
        initial_monto = product_map[selected_product_name]['precio_centavos'] / 100.0

    with st.form("nuevo_ingreso"):
        fecha_ingreso = st.date_input("Fecha del Ingreso", value=date.today())

        cliente = st.text_input("Cliente")
        operador = st.text_input("Operador")
        metodo_pago = st.selectbox("Método de pago", ["efectivo", "débito", "crédito", "transferencia", "qr", "mp"])
        monto = st.number_input("Monto total (ARS)", min_value=0.0, step=100.0, value=initial_monto, key="monto_input")
        consumicion = st.text_input("Consumición (opcional)")
        submitted = st.form_submit_button("➕ Registrar")

        if submitted and monto > 0:
            items_list = []
            if selected_product_name != "-- Ingreso Manual --":
                selected_product_obj = product_map[selected_product_name]
                items_list.append({
                    "producto_id": selected_product_obj['id'],
                    "nombre": selected_product_obj['nombre'],
                    "precio_centavos": selected_product_obj['precio_centavos']
                })

            doc = {
                "fecha": datetime.combine(fecha_ingreso, datetime.min.time()),
                "cliente": cliente,
                "operador": operador,
                "metodo_pago": metodo_pago,
                "consumicion": consumicion,
                "items": items_list,
                "monto_total_centavos": int(monto * 100),
                "created_at": gcfs.SERVER_TIMESTAMP,
                "updated_at": gcfs.SERVER_TIMESTAMP,
            }
            db.collection("ingresos").add(doc)
            st.success("Ingreso registrado ✅")
            # Limpiar la caché del dashboard para que refleje el nuevo ingreso
            get_dashboard_data.clear()

    st.divider()
    st.subheader("Últimos Ingresos Registrados")
    ingresos = db.collection("ingresos").order_by("fecha", direction=admin_fs.Query.DESCENDING).limit(10).stream()
    
    # Encabezados para la lista
    col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
    col1.markdown("**Fecha**")
    col2.markdown("**Cliente**")
    col3.markdown("**Operador**")
    col4.markdown("**Monto**")

    for i in ingresos:
        d = i.to_dict()
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
        col1.write(d["fecha"].strftime("%Y-%m-%d %H:%M"))
        col2.write(d.get("cliente", "N/A"))
        col3.write(d.get("operador", "N/A"))
        col4.write(f"${d['monto_total_centavos']/100:,.2f}")
        if col5.button("🗑️", key=i.id, help="Eliminar ingreso"):
            db.collection("ingresos").document(i.id).delete()
            st.warning(f"Ingreso del {d['fecha'].strftime('%Y-%m-%d')} eliminado.")
            st.rerun()

ingresos_ui()