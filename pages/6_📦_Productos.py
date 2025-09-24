import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore as admin_fs
from google.cloud import firestore as gcfs

# --- Inicialización Firebase ---
# Reutiliza la misma lógica para evitar re-inicializar la app
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["FIREBASE"]))
    firebase_admin.initialize_app(cred)
db = admin_fs.client()


def productos_ui():
    st.subheader("📦 Gestión de Productos y Servicios")

    # --- Crear nuevo producto ---
    with st.form("nuevo_producto"):
        nombre = st.text_input("Nombre")
        tipo = st.selectbox("Tipo", ["servicio", "producto"])
        precio = st.number_input("Precio (ARS)", min_value=0.0, step=100.0)
        categoria = st.text_input("Categoría (opcional)")
        submitted = st.form_submit_button("➕ Agregar")

        if submitted:
            if nombre and precio > 0:
                doc = {
                    "nombre": nombre,
                    "tipo": tipo,
                    "precio_centavos": int(precio * 100),
                    "categoria": categoria,
                    "activo": True,
                    "created_at": gcfs.SERVER_TIMESTAMP,
                    "updated_at": gcfs.SERVER_TIMESTAMP,
                }
                db.collection("productos").add(doc)
                st.success(f"Producto '{nombre}' agregado ✅")
            else:
                st.error("Complete nombre y precio válido.")

    st.divider()

    # --- Listado de productos ---
    productos = db.collection("productos").stream()
    for p in productos:
        data = p.to_dict()
        is_active = data.get("activo", True)  # Considerar activo si el campo no existe

        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
        col1.write(data["nombre"])
        col2.write(data["tipo"])
        col3.write(f"${data['precio_centavos']/100:,.2f}")

        # Columna para cambiar el estado (Activo/Inactivo)
        if is_active:
            if col4.button("✅ Desactivar", key=f"toggle_{p.id}", help="Marcar como inactivo"):
                db.collection("productos").document(p.id).update({"activo": False})
                st.rerun()
        else:
            if col4.button("❌ Activar", key=f"toggle_{p.id}", help="Marcar como activo"):
                db.collection("productos").document(p.id).update({"activo": True})
                st.rerun()

        if col5.button("🗑️", key=f"delete_{p.id}", help="Eliminar producto permanentemente"):
            db.collection("productos").document(p.id).delete()
            st.warning(f"Producto '{data['nombre']}' eliminado.")
            st.rerun()

productos_ui()