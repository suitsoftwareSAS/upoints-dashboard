"""
uPoints Dashboard — Clientes, Cajeros y Puntos en tiempo real
"""
import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime, timedelta, date
import os
import hmac

# ── Autenticación ─────────────────────────────────────────────────────
def check_password():
    """Autenticación básica con usuario/contraseña por env vars."""
    if "authenticated" in st.session_state and st.session_state["authenticated"]:
        return True

    admin_user = os.getenv("DASHBOARD_USER", "")
    admin_pass = os.getenv("DASHBOARD_PASS", "")

    # Si no hay credenciales configuradas, acceso libre
    if not admin_user or not admin_pass:
        st.session_state["authenticated"] = True
        return True

    with st.form("login"):
        st.markdown("### 🔐 uPoints Dashboard")
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar")

        if submit:
            if user == admin_user and pwd == admin_pass:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    return False

if not check_password():
    st.stop()

st.set_page_config(
    page_title="uPoints Dashboard",
    page_icon="📊",
    layout="wide",
)

# ── Conexión ──────────────────────────────────────────────────────────
@st.cache_resource(ttl=300)
def get_connection():
    uri = os.getenv("DB_URI", "")
    if not uri:
        uri_file = os.path.expanduser("~/.hermes/scripts/.pg_uri")
        if os.path.exists(uri_file):
            with open(uri_file) as f:
                uri = f.read().strip()
    if not uri:
        st.error("❌ DB_URI no configurada. Define la variable de entorno DB_URI.")
        st.stop()
    try:
        return psycopg2.connect(uri)
    except Exception as e:
        st.error(f"❌ Error de conexión a la base de datos: {e}")
        st.stop()

if "conn" not in st.session_state:
    st.session_state.conn = get_connection()
conn = st.session_state.conn

# ── Sidebar ───────────────────────────────────────────────────────────
st.sidebar.title("📊 uPoints Dashboard")

# Filtro de fechas
default_end = date.today()
default_start = default_end - timedelta(days=30)
date_range = st.sidebar.date_input(
    "Periodo",
    value=(default_start, default_end),
    max_value=default_end,
)
if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, default_end

# Filtro de marcas
brands_df = pd.read_sql(
    "SELECT id, name FROM brands WHERE name != 'SuitSoftware' AND \"deletedAt\" IS NULL ORDER BY name",
    conn,
)
brand_options = brands_df["name"].tolist()
selected_brands = st.sidebar.multiselect(
    "Marcas", brand_options, default=[]
)

if not selected_brands:
    st.warning("Selecciona al menos una marca")
    st.stop()

brand_filter = "', '".join(selected_brands)

# ── Queries ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_customers(start, end, brands):
    query = f"""
        SELECT b.name as brand,
               DATE(cbb."createdAt") as day,
               COUNT(DISTINCT cbb."customerId") as new_customers,
               COUNT(DISTINCT CASE WHEN c."firebaseMessagingToken" IS NOT NULL
                     THEN cbb."customerId" END) as with_push
        FROM customer_brand_balance cbb
        JOIN brands b ON b.id = cbb."brandId"
        JOIN customer c ON c.id = cbb."customerId"
        WHERE cbb."createdAt" BETWEEN '{start}' AND '{end} 23:59:59'
          AND cbb."deletedAt" IS NULL
          AND b.name IN ('{brands}')
        GROUP BY b.name, DATE(cbb."createdAt")
        ORDER BY b.name, day
    """
    return pd.read_sql(query, conn)

@st.cache_data(ttl=300)
def load_cashiers(start, end, brands):
    query = f"""
        SELECT br.name as brand, ca.username as cashier,
               DATE(rp."createdAt") as day,
               SUM(rp.points) as total_points, COUNT(*) as transactions
        FROM redeem_points rp
        JOIN cash_accounts ca ON ca.id = rp."redeemById"
        JOIN businesses b ON b.id = rp."businessId"
        JOIN brands br ON br.id = b."brandId"
        WHERE rp."createdAt" BETWEEN '{start}' AND '{end} 23:59:59'
          AND rp."deletedAt" IS NULL
          AND rp.points > 0
          AND rp."redeemByActor" = 'cashier'
          AND br.name IN ('{brands}')
        GROUP BY br.name, ca.username, DATE(rp."createdAt")
        ORDER BY br.name, day
    """
    return pd.read_sql(query, conn)

@st.cache_data(ttl=600)
def load_cashier_list(brands):
    query = f"""
        SELECT br.name as brand, ca.username as cashier,
               ca.status, b.name as business
        FROM cash_accounts ca
        JOIN businesses b ON b.id = ca."businessId"
        JOIN brands br ON br.id = b."brandId"
        WHERE ca."deletedAt" IS NULL AND b."deletedAt" IS NULL
          AND br.name IN ('{brands}')
        ORDER BY br.name, ca.username
    """
    return pd.read_sql(query, conn)

customers_df = load_customers(start_date, end_date, brand_filter)
cashiers_df = load_cashiers(start_date, end_date, brand_filter)
all_cashiers_df = load_cashier_list(brand_filter)

# ── KPIs ──────────────────────────────────────────────────────────────
total_customers = customers_df["new_customers"].sum()
total_push = customers_df["with_push"].sum()
push_rate = round(100 * total_push / total_customers, 1) if total_customers else 0
total_points = int(cashiers_df["total_points"].sum())
active_cashiers = cashiers_df["cashier"].nunique()
inactive = len(all_cashiers_df[~all_cashiers_df["cashier"].isin(cashiers_df["cashier"].unique())])

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Clientes nuevos", total_customers)
col2.metric("Tasa push", f"{push_rate}%")
col3.metric("Puntos entregados", f"{total_points:,}")
col4.metric("Cajeros activos", active_cashiers)
col5.metric("Cajeros inactivos", inactive, delta=None)

st.divider()

# ── Gráficos ──────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈 Clientes", "🏪 Cajeros", "📋 Detalle"])

with tab1:
    st.subheader("Clientes nuevos por día")
    if not customers_df.empty:
        chart_data = customers_df.pivot_table(
            index="day", columns="brand", values="new_customers", fill_value=0
        )
        st.area_chart(chart_data, height=400)

        st.subheader("Tasa de push notifications")
        push_data = customers_df.groupby("brand").agg(
            total=("new_customers", "sum"),
            push=("with_push", "sum"),
        )
        push_data["% push"] = round(100 * push_data["push"] / push_data["total"], 1)
        st.dataframe(
            push_data[["total", "push", "% push"]],
            use_container_width=True,
            column_config={
                "total": "Clientes", "push": "Con push", "% push": st.column_config.NumberColumn("% Push", format="%.1f%%")
            },
        )

with tab2:
    st.subheader("Puntos entregados por cajero (diario)")
    if not cashiers_df.empty:
        for brand in selected_brands:
            brand_cashiers = cashiers_df[cashiers_df["brand"] == brand]
            if not brand_cashiers.empty:
                st.markdown(f"**{brand}**")
                pivot = brand_cashiers.pivot_table(
                    index="day", columns="cashier", values="total_points", fill_value=0
                )
                st.line_chart(pivot, height=300)

        # Resumen por cajero
        st.subheader("Ranking de cajeros")
        summary = cashiers_df.groupby(["brand", "cashier"]).agg(
            pts=("total_points", "sum"),
            tx=("transactions", "sum"),
        ).sort_values("pts", ascending=False)
        st.dataframe(summary, use_container_width=True)

    # Cajeros inactivos
    active_list = cashiers_df["cashier"].unique()
    inactive_df = all_cashiers_df[~all_cashiers_df["cashier"].isin(active_list)]
    if not inactive_df.empty:
        st.subheader("🔴 Cajeros sin actividad")
        st.dataframe(inactive_df[["brand", "cashier", "business"]], use_container_width=True)

with tab3:
    st.subheader("Datos crudos — Clientes")
    st.dataframe(customers_df, use_container_width=True)
    st.subheader("Datos crudos — Cajeros")
    st.dataframe(cashiers_df, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────
st.divider()
st.caption(f"Actualizado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Periodo: {start_date} → {end_date}")
