import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore as admin_fs
from google.cloud import firestore as gcfs
from datetime import datetime, timedelta
import pandas as pd

# --- Inicialización Firebase ---
# Reutiliza la misma lógica para evitar re-inicializar la app
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["FIREBASE"]))
    firebase_admin.initialize_app(cred)
db = admin_fs.client()





def membresias_ui():
    st.subheader("💳 Gestión de Membresías")

    # Obtener lista de clientes activos para el selectbox
    clientes_activos = db.collection("clientes").where(filter=gcfs.FieldFilter("activo", "==", True)).stream()
    clientes_options = {}
    clientes_list = []
    
    for c in clientes_activos:
        data = c.to_dict()
        clientes_list.append((data['nombre'], data['dni']))
    
    # Ordenar en Python en lugar de Firebase
    clientes_list.sort(key=lambda x: x[0])  # Ordenar por nombre
    
    for nombre, dni in clientes_list:
        clientes_options[f"{nombre} (DNI: {dni})"] = dni

    if not clientes_options:
        st.warning("No hay clientes activos. Primero debe agregar clientes.")
        return

    # --- Crear nueva membresía ---
    st.write("**Agregar Nueva Membresía**")
    
    # Función para obtener el estado de membresías de un cliente
    def obtener_estado_cliente(dni_cliente):
        """
        Retorna el estado de la ÚLTIMA membresía de un cliente:
        - 'sin_membresia': No tiene membresías
        - 'vigente': Su última membresía está vigente
        - 'vencida': Su última membresía está vencida
        - 'por_vencer': Su última membresía vence en los próximos 7 días
        """
        if not dni_cliente:
            return 'sin_membresia', None
            
        # Obtener la ÚLTIMA membresía del cliente (la más reciente)
        membresias_cliente = db.collection("membresias").where(filter=gcfs.FieldFilter("dni_cliente", "==", dni_cliente)).stream()
        
        # Convertir a lista y ordenar en Python
        membresias_list = []
        for m in membresias_cliente:
            data = m.to_dict()
            data["id"] = m.id
            membresias_list.append(data)
        
        # Ordenar por created_at descendente (más reciente primero) y tomar la primera
        if not membresias_list:
            return 'sin_membresia', "Sin membresías"
            
        # Ordenar por created_at si existe, sino por fecha_alta
        def get_sort_key(m):
            if "created_at" in m and m["created_at"]:
                return m["created_at"]
            elif "fecha_alta" in m and m["fecha_alta"]:
                return m["fecha_alta"]
            else:
                return datetime.min  # Para membresías sin fecha
        
        membresias_list.sort(key=get_sort_key, reverse=True)
        ultima_membresia = membresias_list[0]
        
        # Convertir fechas
        if "fecha_vencimiento" in ultima_membresia:
            ultima_membresia["fecha_vencimiento"] = ultima_membresia["fecha_vencimiento"].date()
        if "fecha_alta" in ultima_membresia:
            ultima_membresia["fecha_alta"] = ultima_membresia["fecha_alta"].date()
        
        if not ultima_membresia:
            return 'sin_membresia', "Sin membresías"
        
        # Verificar si la última membresía está activa
        if not ultima_membresia.get("activa", True):
            return 'sin_membresia', "Última membresía desactivada"
        
        hoy = datetime.now().date()
        fecha_venc = ultima_membresia["fecha_vencimiento"]
        tipo_membresia = ultima_membresia.get("tipo_membresia", "N/A")
        
        if fecha_venc < hoy:
            dias_vencida = (hoy - fecha_venc).days
            return 'vencida', f"Membresía {tipo_membresia} vencida hace {dias_vencida} día(s)"
        elif fecha_venc <= hoy + timedelta(days=7):
            dias_restantes = (fecha_venc - hoy).days
            return 'por_vencer', f"Membresía {tipo_membresia} vence en {dias_restantes} día(s)"
        else:
            dias_restantes = (fecha_venc - hoy).days
            return 'vigente', f"Membresía {tipo_membresia} vigente ({dias_restantes} días restantes)"
    
    # Controles fuera del formulario para mayor interactividad
    col1, col2 = st.columns(2)
    with col1:
        cliente_seleccionado = st.selectbox(
            "Seleccionar Cliente",
            options=list(clientes_options.keys()) if clientes_options else ["No hay clientes activos"],
            disabled=not bool(clientes_options),
            help="Seleccione el cliente para la membresía",
            key="cliente_selector"
        )
        
        # Obtener estado del cliente seleccionado
        dni_cliente_actual = None
        estado_cliente = 'sin_membresia'
        mensaje_estado = ""
        
        if clientes_options and cliente_seleccionado != "No hay clientes activos":
            dni_cliente_actual = clientes_options[cliente_seleccionado]
            estado_cliente, mensaje_estado = obtener_estado_cliente(dni_cliente_actual)
            
        # Mostrar estado del cliente con colores
        if estado_cliente == 'vigente':
            st.success(f"✅ {mensaje_estado}")
        elif estado_cliente == 'por_vencer':
            st.warning(f"⚠️ {mensaje_estado}")
        elif estado_cliente == 'vencida':
            st.error(f"🔴 {mensaje_estado}")
        else:
            st.info(f"ℹ️ {mensaje_estado}")
        
        fecha_alta = st.date_input(
            "Fecha de Alta",
            value=datetime.now().date(),
            help="Fecha de inicio de la membresía",
            key="fecha_alta_input"
        )
    
    with col2:
        tipo_membresia = st.selectbox(
            "Tipo de Membresía",
            ["Mensual", "Trimestral", "Semestral", "Anual"],
            help="Seleccione la duración de la membresía",
            key="tipo_membresia_selector"
        )
        
        # Calcular y mostrar fecha de vencimiento automáticamente
        duracion_dias = {
            "Mensual": 30,
            "Trimestral": 90,
            "Semestral": 180,
            "Anual": 365
        }
        
        fecha_vencimiento_auto = fecha_alta + timedelta(days=duracion_dias[tipo_membresia])
        
        st.markdown("**Fecha de Vencimiento (Automática)**")
        st.info(f"📅 {fecha_vencimiento_auto.strftime('%d/%m/%Y')} ({duracion_dias[tipo_membresia]} días)")

    # Formulario para los campos restantes con color dinámico
    # Definir colores según el estado del cliente
    colores_formulario = {
        'vigente': ('success', '🟢'),
        'por_vencer': ('warning', '🟡'), 
        'vencida': ('error', '🔴'),
        'sin_membresia': ('info', '🆕')
    }
    
    color_tipo, emoji = colores_formulario.get(estado_cliente, ('info', '🆕'))
    
    # Crear contenedor con color de fondo
    if color_tipo == 'success':
        with st.container():
            st.markdown("""
                <div style="padding: 1rem; border-left: 5px solid #28a745; background-color: rgba(40, 167, 69, 0.1); border-radius: 5px; margin: 1rem 0;">
                    <strong>🟢 Cliente con membresía vigente</strong>
                </div>
            """, unsafe_allow_html=True)
    elif color_tipo == 'warning':
        with st.container():
            st.markdown("""
                <div style="padding: 1rem; border-left: 5px solid #ffc107; background-color: rgba(255, 193, 7, 0.1); border-radius: 5px; margin: 1rem 0;">
                    <strong>🟡 Cliente con membresía por vencer</strong>
                </div>
            """, unsafe_allow_html=True)
    elif color_tipo == 'error':
        with st.container():
            st.markdown("""
                <div style="padding: 1rem; border-left: 5px solid #dc3545; background-color: rgba(220, 53, 69, 0.1); border-radius: 5px; margin: 1rem 0;">
                    <strong>🔴 Cliente con membresía vencida</strong>
                </div>
            """, unsafe_allow_html=True)
    else:
        with st.container():
            st.markdown("""
                <div style="padding: 1rem; border-left: 5px solid #17a2b8; background-color: rgba(23, 162, 184, 0.1); border-radius: 5px; margin: 1rem 0;">
                    <strong>🆕 Cliente nuevo - Primera membresía</strong>
                </div>
            """, unsafe_allow_html=True)

    with st.form("nueva_membresia"):
        # Obtener precio sugerido desde la configuración
        precio_sugerido = 5000.0  # Valor por defecto
        try:
            precios_config = db.collection("configuracion").document("precios_membresias").get()
            if precios_config.exists:
                precios = precios_config.to_dict()
                precio_sugerido = precios.get(tipo_membresia, 500000) / 100  # Convertir de centavos
        except:
            pass  # Usar valor por defecto si hay error
        
        col3, col4 = st.columns(2)
        with col3:
            precio = st.number_input(
                "Precio (ARS)",
                min_value=0.0,
                step=500.0,
                value=precio_sugerido,
                help=f"Precio sugerido para {tipo_membresia}: ${precio_sugerido:,.0f}"
            )
            
            metodo_pago = st.selectbox(
                "Método de Pago",
                ["efectivo", "transferencia", "debito_automatico"],
                format_func=lambda x: {
                    "efectivo": "💵 Efectivo",
                    "transferencia": "🏦 Transferencia",
                    "debito_automatico": "💳 Débito Automático"
                }[x],
                help="Seleccione el método de pago utilizado"
            )
        
        with col4:
            # Mostrar resumen con estado del cliente
            st.markdown("**Resumen:**")
            if clientes_options and cliente_seleccionado != "No hay clientes activos":
                cliente_nombre = cliente_seleccionado.split(' (')[0]
                st.write(f"👤 Cliente: {cliente_nombre}")
                st.write(f"💳 Tipo: {tipo_membresia}")
                st.write(f"💰 Precio: ${precio:,.0f}")
                st.write(f"💵 Pago: {metodo_pago.replace('_', ' ').title()}")
                
                # Mostrar estado del cliente en el resumen
                emoji_estado = colores_formulario.get(estado_cliente, ('info', '🆕'))[1]
                if estado_cliente == 'vigente':
                    st.write(f"{emoji_estado} Última: Vigente")
                elif estado_cliente == 'por_vencer':
                    st.write(f"{emoji_estado} Última: Por vencer")
                elif estado_cliente == 'vencida':
                    st.write(f"{emoji_estado} Última: Vencida")
                else:
                    st.write(f"{emoji_estado} Primera membresía")
            else:
                st.write("Seleccione un cliente para ver el resumen")
        
        notas = st.text_area("Notas (opcional)", help="Observaciones adicionales")
        
        submitted = st.form_submit_button("➕ Crear Membresía")

        if submitted:
            if clientes_options and cliente_seleccionado != "No hay clientes activos":
                dni_cliente = clientes_options[cliente_seleccionado]
                
                # Recalcular fecha de vencimiento con los valores actuales
                duracion_dias = {
                    "Mensual": 30,
                    "Trimestral": 90,
                    "Semestral": 180,
                    "Anual": 365
                }
                fecha_vencimiento_final = fecha_alta + timedelta(days=duracion_dias[tipo_membresia])
                
                doc = {
                    "dni_cliente": dni_cliente,
                    "tipo_membresia": tipo_membresia,
                    "fecha_alta": datetime.combine(fecha_alta, datetime.min.time()),
                    "fecha_vencimiento": datetime.combine(fecha_vencimiento_final, datetime.min.time()),
                    "precio_centavos": int(precio * 100),
                    "metodo_pago": metodo_pago,
                    "notas": notas,
                    "activa": True,
                    "created_at": gcfs.SERVER_TIMESTAMP,
                    "updated_at": gcfs.SERVER_TIMESTAMP,
                }
                
                db.collection("membresias").add(doc)
                cliente_nombre = cliente_seleccionado.split(' (')[0]
                metodo_pago_display = metodo_pago.replace('_', ' ').title()
                st.success(f"✅ Membresía {tipo_membresia} creada para **{cliente_nombre}**")
                st.success(f"📅 Vence el: **{fecha_vencimiento_final.strftime('%d/%m/%Y')}**")
                st.success(f"💰 Precio: **${precio:,.0f}** - Pago: **{metodo_pago_display}**")
            else:
                st.error("❌ Debe seleccionar un cliente válido.")

    st.divider()

    # --- Listado de membresías ---
    st.write("**Lista de Membresías (Última por Cliente)**")
    
    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        filtro_estado = st.selectbox("Filtrar por estado", ["Todas", "Activas", "Inactivas"])
    with col2:
        filtro_vencimiento = st.selectbox("Filtrar por vencimiento", ["Todas", "Vigentes", "Vencidas", "Por vencer (7 días)"])
    
    # Obtener todas las membresías y agrupar por cliente para obtener la más reciente
    todas_membresias = db.collection("membresias").stream()
    
    # Convertir a lista y ordenar en Python
    todas_membresias_list = []
    for m in todas_membresias:
        data = m.to_dict()
        data["id"] = m.id
        todas_membresias_list.append(data)
    
    # Ordenar por created_at descendente (más reciente primero)
    def get_sort_key(m):
        if "created_at" in m and m["created_at"]:
            return m["created_at"]
        elif "fecha_alta" in m and m["fecha_alta"]:
            return m["fecha_alta"]
        else:
            return datetime.min
    
    todas_membresias_list.sort(key=get_sort_key, reverse=True)
    
    # Diccionario para almacenar la última membresía de cada cliente
    ultimas_membresias = {}
    hoy = datetime.now().date()
    
    for data in todas_membresias_list:
        dni_cliente = data.get("dni_cliente")
        
        # Solo mantener la primera (más reciente) membresía de cada cliente
        if dni_cliente not in ultimas_membresias:
            # Convertir fechas
            if "fecha_alta" in data:
                data["fecha_alta"] = data["fecha_alta"].date()
            if "fecha_vencimiento" in data:
                data["fecha_vencimiento"] = data["fecha_vencimiento"].date()
                
            # Calcular estado de vencimiento
            if data["fecha_vencimiento"] < hoy:
                data["estado_vencimiento"] = "Vencida"
            elif data["fecha_vencimiento"] <= hoy + timedelta(days=7):
                data["estado_vencimiento"] = "Por vencer"
            else:
                data["estado_vencimiento"] = "Vigente"
            
            # Obtener nombre del cliente
            cliente = db.collection("clientes").document(data["dni_cliente"]).get()
            if cliente.exists:
                data["nombre_cliente"] = cliente.to_dict().get("nombre", "N/A")
                ultimas_membresias[dni_cliente] = data
            else:
                data["nombre_cliente"] = "Cliente no encontrado"
                ultimas_membresias[dni_cliente] = data
    
    # Convertir a lista para aplicar filtros
    membresias_data = list(ultimas_membresias.values())
    
    # Aplicar filtro de estado
    if filtro_estado == "Activas":
        membresias_data = [m for m in membresias_data if m.get("activa", True)]
    elif filtro_estado == "Inactivas":
        membresias_data = [m for m in membresias_data if not m.get("activa", True)]
    
    # Aplicar filtro de vencimiento
    if filtro_vencimiento == "Vigentes":
        membresias_data = [m for m in membresias_data if m["estado_vencimiento"] == "Vigente"]
    elif filtro_vencimiento == "Vencidas":
        membresias_data = [m for m in membresias_data if m["estado_vencimiento"] == "Vencida"]
    elif filtro_vencimiento == "Por vencer (7 días)":
        membresias_data = [m for m in membresias_data if m["estado_vencimiento"] == "Por vencer"]
    
    if membresias_data:
        # Ordenar por fecha de vencimiento (más próximos a vencer primero)
        membresias_data.sort(key=lambda x: x.get("fecha_vencimiento", datetime.max.date()))
        
        st.info(f"📊 Mostrando {len(membresias_data)} cliente(s) con sus últimas membresías")
        
        for membresia in membresias_data:
            # Determinar color según estado
            if membresia["estado_vencimiento"] == "Vencida":
                color_emoji = "🔴"
                border_color = "#dc3545"
                bg_color = "rgba(220, 53, 69, 0.1)"
            elif membresia["estado_vencimiento"] == "Por vencer":
                color_emoji = "🟡"
                border_color = "#ffc107"
                bg_color = "rgba(255, 193, 7, 0.1)"
            else:
                color_emoji = "🟢"
                border_color = "#28a745"
                bg_color = "rgba(40, 167, 69, 0.1)"
            
            # Calcular información de fecha
            fecha_venc = membresia['fecha_vencimiento']
            if membresia["estado_vencimiento"] == "Vencida":
                dias_vencida = (hoy - fecha_venc).days
                fecha_info = f"Venció hace {dias_vencida}d"
            elif membresia["estado_vencimiento"] == "Por vencer":
                dias_restantes = (fecha_venc - hoy).days
                fecha_info = f"Vence en {dias_restantes}d"
            else:
                dias_restantes = (fecha_venc - hoy).days
                fecha_info = f"Vigente {dias_restantes}d"
            
            # Una sola fila con información y botones
            with st.container():

                
                # Usar columnas para información + botones en la misma línea
                col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2.2, 1.3, 1.0, 1.3, 1.0, 1.0, 0.7, 0.7])
                
                with col1:
                    st.write(f"**{color_emoji} {membresia['nombre_cliente']}**")
                
                with col2:
                    st.write(f"DNI: {membresia['dni_cliente']}")
                
                with col3:
                    st.write(f"{membresia['tipo_membresia']}")
                
                with col4:
                    st.write(f"{fecha_info}")
                
                with col5:
                    st.write(f"{fecha_venc.strftime('%d/%m/%Y')}")
                
                with col6:
                    # Mostrar método de pago con emoji
                    metodo_pago = membresia.get('metodo_pago', 'efectivo')
                    pago_emoji = {
                        'efectivo': '💵',
                        'transferencia': '🏦', 
                        'debito_automatico': '💳'
                    }.get(metodo_pago, '💵')
                    st.write(f"{pago_emoji}")
                
                with col7:
                    # Botón para activar/desactivar
                    is_active = membresia.get("activa", True)
                    if is_active:
                        if st.button("🚫", key=f"toggle_memb_{membresia['id']}", help="Desactivar membresía"):
                            db.collection("membresias").document(membresia["id"]).update({"activa": False})
                            st.rerun()
                    else:
                        if st.button("✅", key=f"toggle_memb_{membresia['id']}", help="Activar membresía"):
                            db.collection("membresias").document(membresia["id"]).update({"activa": True})
                            st.rerun()
                
                with col8:
                    # Botón eliminar
                    if st.button("🗑️", key=f"delete_memb_{membresia['id']}", help="Eliminar membresía"):
                        db.collection("membresias").document(membresia["id"]).delete()
                        st.success("Membresía eliminada.")
                        st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No hay membresías que coincidan con los filtros seleccionados.")


def precios_membresias_ui():
    st.subheader("💰 Configuración de Precios de Membresías")

    # --- Crear/Actualizar precios de membresías ---
    with st.form("configurar_precios"):
        st.write("**Configurar Precios por Tipo de Membresía**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            precio_mensual = st.number_input(
                "Membresía Mensual (ARS)",
                min_value=0.0,
                step=500.0,
                value=5000.0,
                help="Precio por defecto para membresías mensuales"
            )
            
            precio_trimestral = st.number_input(
                "Membresía Trimestral (ARS)",
                min_value=0.0,
                step=500.0,
                value=13500.0,
                help="Precio por defecto para membresías trimestrales"
            )
        
        with col2:
            precio_semestral = st.number_input(
                "Membresía Semestral (ARS)",
                min_value=0.0,
                step=500.0,
                value=25000.0,
                help="Precio por defecto para membresías semestrales"
            )
            
            precio_anual = st.number_input(
                "Membresía Anual (ARS)",
                min_value=0.0,
                step=1000.0,
                value=45000.0,
                help="Precio por defecto para membresías anuales"
            )
        
        submitted = st.form_submit_button("💾 Guardar Precios")

        if submitted:
            precios_config = {
                "Mensual": int(precio_mensual * 100),  # Guardar en centavos
                "Trimestral": int(precio_trimestral * 100),
                "Semestral": int(precio_semestral * 100),
                "Anual": int(precio_anual * 100),
                "updated_at": gcfs.SERVER_TIMESTAMP,
            }
            
            # Guardar en Firebase con ID fijo para facilitar la consulta
            db.collection("configuracion").document("precios_membresias").set(precios_config)
            st.success("Precios de membresías actualizados ✅")

    st.divider()

    # --- Mostrar tabla de precios actuales ---
    st.write("**Precios Actuales**")
    
    try:
        precios_doc = db.collection("configuracion").document("precios_membresias").get()
        
        if precios_doc.exists:
            precios = precios_doc.to_dict()
            
            # Crear tabla de precios
            col1, col2, col3 = st.columns([2, 2, 2])
            
            with col1:
                st.metric("💳 Mensual", f"${precios.get('Mensual', 0)/100:,.0f}")
                st.metric("💳 Semestral", f"${precios.get('Semestral', 0)/100:,.0f}")
            
            with col2:
                st.metric("💳 Trimestral", f"${precios.get('Trimestral', 0)/100:,.0f}")
                st.metric("💳 Anual", f"${precios.get('Anual', 0)/100:,.0f}")
            
            with col3:
                # Calcular descuentos
                mensual = precios.get('Mensual', 0) / 100
                trimestral = precios.get('Trimestral', 0) / 100
                semestral = precios.get('Semestral', 0) / 100
                anual = precios.get('Anual', 0) / 100
                
                if mensual > 0:
                    desc_trim = ((mensual * 3 - trimestral) / (mensual * 3)) * 100
                    desc_sem = ((mensual * 6 - semestral) / (mensual * 6)) * 100
                    desc_anual = ((mensual * 12 - anual) / (mensual * 12)) * 100
                    
                    st.write("**Descuentos vs Mensual:**")
                    st.write(f"🎯 Trimestral: {desc_trim:.1f}%")
                    st.write(f"🎯 Semestral: {desc_sem:.1f}%")
                    st.write(f"🎯 Anual: {desc_anual:.1f}%")
                    
        else:
            st.info("No hay precios configurados. Use el formulario superior para establecer los precios.")
            
    except Exception as e:
        st.error(f"Error al cargar precios: {str(e)}")

def main():
    st.set_page_config(page_title="Membresías - Benjas", page_icon="�", layout="wide")
    st.title("👥 Gestión de Membresías")

    # Tabs para organizar la interfaz
    tab1, tab2 = st.tabs(["💳 Membresías", " Precios"])
    
    with tab1:
        membresias_ui()
    
    with tab2:
        precios_membresias_ui()


if __name__ == "__main__":
    main()
