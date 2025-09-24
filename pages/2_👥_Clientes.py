import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore as admin_fs
from google.cloud import firestore as gcfs
import pandas as pd

# --- Inicialización Firebase ---
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["FIREBASE"]))
    firebase_admin.initialize_app(cred)
db = admin_fs.client()


def clientes_ui():
    st.subheader("👥 Gestión de Clientes")

    # --- Crear nuevo cliente ---
    with st.form("nuevo_cliente"):
        st.write("**Agregar Nuevo Cliente**")
        nombre = st.text_input("Nombre completo")
        dni = st.text_input("DNI (será el ID único)")
        telefono = st.text_input("Teléfono (opcional)")
        email = st.text_input("Email (opcional)")
        submitted = st.form_submit_button("➕ Agregar Cliente")

        if submitted:
            if nombre and dni:
                # Verificar si el DNI ya existe
                existing_client = db.collection("clientes").document(dni).get()
                if existing_client.exists:
                    st.error(f"Ya existe un cliente con DNI: {dni}")
                else:
                    doc = {
                        "nombre": nombre,
                        "dni": dni,
                        "telefono": telefono,
                        "email": email,
                        "activo": True,
                        "created_at": gcfs.SERVER_TIMESTAMP,
                        "updated_at": gcfs.SERVER_TIMESTAMP,
                    }
                    db.collection("clientes").document(dni).set(doc)
                    st.success(f"Cliente '{nombre}' agregado ✅")
            else:
                st.error("Complete nombre y DNI.")

    st.divider()

    # --- Listado de clientes ---
    st.write("**Lista de Clientes**")
    clientes = db.collection("clientes").stream()
    
    clientes_data = []
    for c in clientes:
        data = c.to_dict()
        data["id"] = c.id
        clientes_data.append(data)
    
    # Ordenar por nombre en Python
    if clientes_data:
        clientes_data.sort(key=lambda x: x.get("nombre", ""))
        df_clientes = pd.DataFrame(clientes_data)
        
        # Mostrar tabla de clientes
        for _, cliente in df_clientes.iterrows():
            is_active = cliente.get("activo", True)
            
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 1])
            col1.write(cliente["nombre"])
            col2.write(f"DNI: {cliente['dni']}")
            col3.write(cliente.get("telefono", "N/A"))
            
            # Botón para activar/desactivar
            if is_active:
                if col4.button("✅ Desactivar", key=f"toggle_cliente_{cliente['dni']}", help="Desactivar cliente"):
                    db.collection("clientes").document(cliente["dni"]).update({"activo": False})
                    st.rerun()
            else:
                if col4.button("❌ Activar", key=f"toggle_cliente_{cliente['dni']}", help="Activar cliente"):
                    db.collection("clientes").document(cliente["dni"]).update({"activo": True})
                    st.rerun()
            
            # Botón eliminar
            if col5.button("🗑️", key=f"delete_cliente_{cliente['dni']}", help="Eliminar cliente"):
                # Verificar si tiene membresías activas
                membresias_activas = db.collection("membresias").where(filter=gcfs.FieldFilter("dni_cliente", "==", cliente["dni"])).where(filter=gcfs.FieldFilter("activa", "==", True)).get()
                if len(membresias_activas) > 0:
                    st.error("No se puede eliminar el cliente. Tiene membresías activas.")
                else:
                    db.collection("clientes").document(cliente["dni"]).delete()
                    st.success(f"Cliente '{cliente['nombre']}' eliminado.")
                    st.rerun()
    else:
        st.info("No hay clientes registrados.")


def main():
    st.set_page_config(page_title="Clientes - Benjas", page_icon="👥", layout="wide")
    st.title("👥 Gestión de Clientes")
    
    clientes_ui()


if __name__ == "__main__":
    main()
