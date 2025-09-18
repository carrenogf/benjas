import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore as admin_fs
import pandas as pd
import plotly.express as px
from datetime import datetime
import io
from calendar import monthrange
from utils import get_dashboard_data, initialize_firebase

# --- Inicialización Firebase ---
db = initialize_firebase()

def to_excel(df_ing, df_gas):
    """Convierte los dataframes de ingresos y gastos a un archivo Excel en memoria."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if not df_ing.empty:
            df_ing.to_excel(writer, sheet_name='Ingresos', index=False)
        if not df_gas.empty:
            df_gas.to_excel(writer, sheet_name='Gastos', index=False)
    processed_data = output.getvalue()
    return processed_data


def dashboard_ui():
    st.subheader("📊 Dashboard Financiero")

    # --- Filtros de fecha (mes y año) ---
    today = datetime.today()
    # Crear una lista de años, desde 2023 hasta el año actual
    years = list(range(2023, today.year + 1))
    # Crear un diccionario de meses para mostrar nombres en lugar de números
    month_names = {1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}
    
    col1, col2 = st.columns(2)
    selected_year = col1.selectbox("Año", options=years, index=len(years) - 1)
    selected_month = col2.selectbox("Mes", options=list(month_names.keys()), format_func=lambda x: month_names[x], index=today.month - 1)

    st.divider()

    # Título dinámico
    st.header(f"Resumen de {month_names[selected_month]} {selected_year}")

    # --- Obtener datos de forma optimizada ---
    df_ing, df_gas = get_dashboard_data(selected_year, selected_month)

    # --- Mensaje si no hay datos para el período seleccionado ---
    if df_ing.empty and df_gas.empty:
        st.info(f"No se encontraron datos para {month_names[selected_month]} de {selected_year}.")
        # Limpiar la caché si se cambia de mes y no hay datos, para forzar recarga si se vuelve al mes anterior.
        get_dashboard_data.clear()
        st.info(f"No se encontraron datos para {month_names[selected_month]} de {selected_year}.")
        return

    # --- Botón de descarga ---
    # Preparar dataframes para la descarga
    df_ing_download = df_ing.copy()
    df_gas_download = df_gas.copy()

    if not df_ing_download.empty:
        # Convertir la lista de items a un string legible
        df_ing_download['items'] = df_ing_download['items'].apply(lambda items: ', '.join([item.get('nombre', '') for item in items]) if isinstance(items, list) and items else 'N/A')
        # Quitar la información de zona horaria para compatibilidad con Excel
        df_ing_download['fecha'] = df_ing_download['fecha'].dt.tz_localize(None)
        # Seleccionar y renombrar columnas
        df_ing_download = df_ing_download[['fecha', 'cliente', 'operador', 'metodo_pago', 'monto_total', 'items', 'consumicion']]
        df_ing_download.columns = ['Fecha', 'Cliente', 'Operador', 'Método de Pago', 'Monto (ARS)', 'Productos/Servicios', 'Consumición']

    if not df_gas_download.empty:
        # Quitar la información de zona horaria para compatibilidad con Excel
        df_gas_download['fecha'] = df_gas_download['fecha'].dt.tz_localize(None)
        # Seleccionar y renombrar columnas
        df_gas_download = df_gas_download[['fecha', 'concepto', 'proveedor', 'metodo_pago', 'monto', 'descripcion']]
        df_gas_download.columns = ['Fecha', 'Concepto', 'Proveedor', 'Método de Pago', 'Monto (ARS)', 'Descripción']

    excel_data = to_excel(df_ing_download, df_gas_download)
    st.download_button(
        label="📥 Descargar Reporte en Excel",
        data=excel_data,
        file_name=f"Reporte_{month_names[selected_month]}_{selected_year}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- KPIs principales ---
    col1, col2, col3 = st.columns(3)
    total_ingresos = df_ing["monto_total"].sum() if not df_ing.empty else 0
    total_gastos = df_gas["monto"].sum() if not df_gas.empty else 0
    utilidad = total_ingresos - total_gastos
    
    # Formatear los valores para las métricas
    ingresos_str = f"${total_ingresos:,.2f}"
    gastos_str = f"${total_gastos:,.2f}"

    col1.metric("💵 Total Ingresos", f"${total_ingresos:,.2f}")
    col2.metric("📉 Total Gastos", f"${total_gastos:,.2f}")
    col3.metric("📈 Utilidad Neta", f"${utilidad:,.2f}")

    st.divider()

    # --- Evolución temporal ingresos vs gastos ---
    if not df_ing.empty or not df_gas.empty:
        df_all = pd.DataFrame()
        if not df_ing.empty:
            df_ing_plot = df_ing.groupby(df_ing["fecha"].dt.date)["monto_total"].sum().reset_index()
            df_ing_plot["tipo"] = "Ingresos"
            df_ing_plot.rename(columns={"monto_total": "monto"}, inplace=True)
            df_all = pd.concat([df_all, df_ing_plot])

        if not df_gas.empty:
            df_gas_plot = df_gas.groupby(df_gas["fecha"].dt.date)["monto"].sum().reset_index()
            df_gas_plot["tipo"] = "Gastos"
            df_all = pd.concat([df_all, df_gas_plot])

        # Se vuelve a un gráfico de línea, pero con marcadores (markers=True).
        # Esto soluciona el problema de visualización cuando hay datos de un solo día, mostrando un punto.
        fig_evolucion = px.line(
            df_all, x="fecha", y="monto", color="tipo",
            title="Evolución diaria de Ingresos vs Gastos", 
            markers=True,
            color_discrete_map={'Ingresos': 'green', 'Gastos': 'red'}
        )
        st.plotly_chart(fig_evolucion, use_container_width=True)

    st.divider()

    # --- Gráficos en columnas ---
    col_graf_1, col_graf_2 = st.columns(2)

    with col_graf_1:
        # --- Distribución de ingresos por método de pago ---
        if not df_ing.empty:
            fig_pago = px.pie(df_ing, names="metodo_pago", values="monto_total",
                              title="Ingresos por método de pago", hole=0.4)
            fig_pago.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pago, use_container_width=True)
        else:
            st.info("No hay datos de ingresos para mostrar este gráfico.")

    with col_graf_2:
        # --- Gastos por concepto ---
        if not df_gas.empty:
            df_gas_grouped = df_gas.groupby("concepto")["monto"].sum().reset_index().sort_values("monto", ascending=False)
            fig_gas = px.bar(df_gas_grouped,
                             x="concepto", y="monto",
                             title="Gastos por concepto")
            st.plotly_chart(fig_gas, use_container_width=True)
        else:
            st.info("No hay datos de gastos para mostrar este gráfico.")

    st.divider()

    # --- NUEVO: Top Productos/Servicios vendidos ---
    if not df_ing.empty and 'items' in df_ing.columns:
        # 'Explota' la lista de items para tener una fila por cada item vendido
        df_items = df_ing.explode('items').dropna(subset=['items'])
        if not df_items.empty:
            df_items['nombre_producto'] = df_items['items'].apply(lambda x: x.get('nombre', 'Desconocido'))
            top_productos = df_items['nombre_producto'].value_counts().reset_index()
            top_productos.columns = ['producto', 'cantidad']
            
            fig_top_prod = px.bar(top_productos.head(10), x='producto', y='cantidad', title='Top 10 Productos/Servicios más vendidos')
            st.plotly_chart(fig_top_prod, use_container_width=True)

    # --- Top operadores (ventas) ---
    if not df_ing.empty:
        fig_op = px.bar(df_ing.groupby("operador")["monto_total"].sum().reset_index(),
                        x="operador", y="monto_total",
                        title="Ingresos por operador/barbero")
        st.plotly_chart(fig_op, use_container_width=True)

dashboard_ui()