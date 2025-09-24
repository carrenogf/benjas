import streamlit as st

# --- Configuración básica de la app ---
st.set_page_config(page_title="Benjas Barber Club", page_icon="💈", layout="wide")

st.title("💈 Benjas Barber Club - Gestión")

st.header("Bienvenido al sistema de gestión")

st.info(
    """
    Utiliza el menú de navegación en la barra lateral izquierda para acceder a las diferentes secciones:

    - **📦 Productos:** Gestiona tus productos y servicios.
    - **💵 Ingresos:** Registra las ventas y servicios realizados.
    - **📉 Gastos:** Lleva un control de todos los gastos del negocio.
    - **📊 Dashboard:** Visualiza los indicadores clave de tu barbería.
    - **👥 Clientes:** Gestiona la base de datos de clientes.
    - **💳 Membresías:** Administra las membresías de los clientes.
    """
)

