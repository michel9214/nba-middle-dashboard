"""
NBA Middle Lab — Dashboard de Reportes
Accesible desde iPhone / cualquier navegador
"""
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(
    page_title="NBA Middle Lab",
    page_icon="🏀",
    layout="wide",
)

# ── Auth simple ──
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🏀 NBA Middle Lab")
    pwd = st.text_input("Password", type="password")
    if pwd == st.secrets.get("APP_PASSWORD", "middle2026"):
        st.session_state.auth = True
        st.rerun()
    elif pwd:
        st.error("Password incorrecto")
    st.stop()


# ── Supabase REST API ──
SUPABASE_URL = st.secrets["SUPABASE_URL"].strip().strip("'\"")
SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip().strip("'\"")
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def query_table(table, select="*", filters="", order="timestamp.desc", limit=1000):
    """Query Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}&order={order}&limit={limit}"
    if filters:
        url += f"&{filters}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json() if r.status_code == 200 else []
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"DB Error: {e}")
        return pd.DataFrame()


# ── Sidebar ──
st.sidebar.title("🏀 NBA Middle Lab")
page = st.sidebar.radio("", ["Dashboard", "Oportunidades", "Lineas", "Sesiones"])

# Date range filter
st.sidebar.markdown("---")
days = st.sidebar.selectbox("Periodo", [1, 3, 7, 30, 90], index=2)
since = datetime.utcnow() - timedelta(days=days)

# ── Dashboard ──
if page == "Dashboard":
    st.title("Dashboard")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)

    since_str = since.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    df_opor = query_table("oportunidades", filters=f"timestamp=gte.{since_str}")
    df_ses = query_table("sesiones", filters=f"timestamp=gte.{since_str}")

    # Debug: if empty try without filter
    if len(df_opor) == 0:
        df_opor = query_table("oportunidades")
    if len(df_ses) == 0:
        df_ses = query_table("sesiones")

    # Debug
    st.caption(f"URL: {SUPABASE_URL[:30]}... | Key: {SUPABASE_KEY[:20]}... | Opor rows: {len(df_opor)} | Ses rows: {len(df_ses)}")

    with col1:
        st.metric("Oportunidades", len(df_opor))
    with col2:
        middlings = len(df_opor[df_opor["tipo"] == "MIDDLING"]) if len(df_opor) > 0 else 0
        st.metric("Middlings", middlings)
    with col3:
        surebets = len(df_opor[df_opor["tipo"] == "SUREBET"]) if len(df_opor) > 0 else 0
        st.metric("Surebets", surebets)
    with col4:
        mejor_gap = df_opor["gap"].max() if len(df_opor) > 0 and "gap" in df_opor.columns else 0
        st.metric("Mejor Gap", f"{mejor_gap:.1f} pts" if mejor_gap else "0")

    # Timeline
    if len(df_opor) > 0:
        st.subheader("Timeline de Oportunidades")
        df_opor["hora"] = pd.to_datetime(df_opor["timestamp"]).dt.strftime("%m/%d %H:%M")
        fig = px.scatter(
            df_opor,
            x="timestamp",
            y="gap",
            color="prioridad",
            size="gap",
            hover_data=["partido", "casa_a", "casa_b", "tipo"],
            color_discrete_map={"ALTA": "red", "MEDIA": "orange", "BAJA": "gray"},
            title="Oportunidades detectadas",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Scans por hora
    if len(df_ses) > 0:
        st.subheader("Actividad de Escaneo")
        df_ses["hora"] = pd.to_datetime(df_ses["timestamp"]).dt.floor("h")
        scans_hora = df_ses.groupby("hora").size().reset_index(name="scans")
        fig2 = px.bar(scans_hora, x="hora", y="scans", title="Scans por hora")
        st.plotly_chart(fig2, use_container_width=True)


# ── Oportunidades ──
elif page == "Oportunidades":
    st.title("Oportunidades Detectadas")

    df = query_table("oportunidades", filters=f"timestamp=gte.{since.strftime('%Y-%m-%dT%H:%M:%S')}")

    if len(df) == 0:
        st.info("Sin oportunidades en este periodo")
    else:
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            tipo_filter = st.multiselect("Tipo", df["tipo"].unique(), default=df["tipo"].unique())
        with col2:
            prio_filter = st.multiselect("Prioridad", df["prioridad"].unique(), default=df["prioridad"].unique())

        df_f = df[df["tipo"].isin(tipo_filter) & df["prioridad"].isin(prio_filter)]

        st.dataframe(
            df_f[["timestamp", "tipo", "prioridad", "partido", "casa_a", "spread_a", "odds_a",
                  "casa_b", "spread_b", "odds_b", "gap", "profit_pct"]],
            use_container_width=True,
            hide_index=True,
        )

        # Distribucion por casa
        st.subheader("Casas mas frecuentes")
        casas = pd.concat([df_f["casa_a"], df_f["casa_b"]]).value_counts()
        fig = px.bar(x=casas.index, y=casas.values, labels={"x": "Casa", "y": "Apariciones"})
        st.plotly_chart(fig, use_container_width=True)

        # Distribucion de gaps
        if df_f["gap"].notna().any():
            st.subheader("Distribucion de Gaps")
            fig2 = px.histogram(df_f[df_f["gap"].notna()], x="gap", nbins=20, title="Gaps detectados")
            st.plotly_chart(fig2, use_container_width=True)


# ── Lineas ──
elif page == "Lineas":
    st.title("Movimiento de Lineas")

    df = query_table("snapshots", filters=f"timestamp=gte.{since.strftime('%Y-%m-%dT%H:%M:%S')}", limit=5000)

    if len(df) == 0:
        st.info("Sin snapshots en este periodo")
    else:
        # Selector de partido
        partidos = sorted(df["partido"].unique())
        partido_sel = st.selectbox("Partido", partidos)

        df_p = df[df["partido"] == partido_sel]

        if len(df_p) > 0:
            # Spreads por casa en el tiempo
            df_spreads = df_p[df_p["tipo_mercado"] == "spread"].copy()
            if len(df_spreads) > 0:
                st.subheader(f"Spread: {partido_sel}")
                fig = px.line(
                    df_spreads,
                    x="timestamp",
                    y="spread",
                    color="casa",
                    markers=True,
                    title=f"Movimiento de spread - {partido_sel}",
                )
                st.plotly_chart(fig, use_container_width=True)

            # ML por casa
            df_ml = df_p[df_p["tipo_mercado"] == "moneyline"].copy()
            if len(df_ml) > 0:
                st.subheader(f"Moneyline: {partido_sel}")
                fig2 = px.line(
                    df_ml,
                    x="timestamp",
                    y="odds",
                    color="casa",
                    markers=True,
                    title=f"Movimiento ML - {partido_sel}",
                )
                st.plotly_chart(fig2, use_container_width=True)

        # Tabla raw
        with st.expander("Datos raw"):
            st.dataframe(df_p, use_container_width=True, hide_index=True)


# ── Sesiones ──
elif page == "Sesiones":
    st.title("Sesiones de Escaneo")

    df = query_table("sesiones", filters=f"timestamp=gte.{since.strftime('%Y-%m-%dT%H:%M:%S')}")

    if len(df) == 0:
        st.info("Sin sesiones en este periodo")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Scans", len(df))
        with col2:
            avg_dur = df["duracion_scan_seg"].mean() if "duracion_scan_seg" in df.columns else 0
            st.metric("Duracion Promedio", f"{avg_dur:.1f}s")
        with col3:
            total_opor = df["oportunidades_detectadas"].sum() if "oportunidades_detectadas" in df.columns else 0
            st.metric("Total Oportunidades", int(total_opor))

        st.dataframe(df, use_container_width=True, hide_index=True)
