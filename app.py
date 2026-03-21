"""
NBA Middle Lab — Dashboard de Reportes
Accesible desde iPhone / cualquier navegador
"""
import streamlit as st
import pandas as pd
import urllib.request
import json
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
SUPABASE_URL = str(st.secrets["SUPABASE_URL"]).strip().strip("'\"<>")
SUPABASE_KEY = str(st.secrets["SUPABASE_KEY"]).strip().strip("'\"<>")
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def query_table(table, select="*", filters="", order="timestamp.desc", limit=1000):
    """Query Supabase REST API via urllib (works on all Python versions)."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}&order={order}&limit={limit}"
    if filters:
        url += f"&{filters}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"DB Error: {e}")
        return pd.DataFrame()


# ── Sidebar ──
st.sidebar.title("🏀 NBA Middle Lab")
page = st.sidebar.radio("", ["Dashboard", "Surebets T-Money", "Oportunidades", "Lineas", "Sesiones"])

# Date range filter
st.sidebar.markdown("---")
days = st.sidebar.selectbox("Periodo", [1, 3, 7, 30, 90], index=2)
since = datetime.utcnow() - timedelta(days=days)

# ── Dashboard ──
if page == "Dashboard":
    st.title("Dashboard")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)

    since_iso = since.strftime("%Y-%m-%dT%H:%M:%S")
    df_opor = query_table("oportunidades", filters=f"timestamp=gte.{since_iso}")
    df_ses = query_table("sesiones", filters=f"timestamp=gte.{since_iso}")

    st.caption(f"Datos: {len(df_opor)} oportunidades | {len(df_ses)} sesiones | Periodo: {days}d")

    with col1:
        st.metric("Oportunidades", len(df_opor))
    with col2:
        middlings = len(df_opor[df_opor["tipo"] == "MIDDLING"]) if len(df_opor) > 0 else 0
        st.metric("Middlings", middlings)
    with col3:
        surebets = len(df_opor[df_opor["tipo"] == "SUREBET"]) if len(df_opor) > 0 else 0
        st.metric("Surebets", surebets)
    with col4:
        mejor_gap = 0
        if len(df_opor) > 0 and "gap" in df_opor.columns:
            gaps = df_opor["gap"].dropna()
            mejor_gap = float(gaps.max()) if len(gaps) > 0 else 0
        mejor_profit = 0
        if len(df_opor) > 0 and "profit_pct" in df_opor.columns:
            profits = df_opor["profit_pct"].dropna()
            mejor_profit = float(profits.max()) if len(profits) > 0 else 0
        if mejor_gap > 0:
            st.metric("Mejor Gap", f"{mejor_gap:.1f} pts")
        elif mejor_profit > 0:
            st.metric("Mejor Profit", f"{mejor_profit:.1f}%")
        else:
            st.metric("Mejor Gap", "0")

    # Timeline
    if len(df_opor) > 0:
        st.subheader("Timeline de Oportunidades")
        df_plot = df_opor.copy()
        df_plot["timestamp"] = pd.to_datetime(df_plot["timestamp"])
        # Use profit_pct for surebets, gap for middlings
        df_plot["valor"] = df_plot["gap"].fillna(df_plot["profit_pct"]).fillna(1)
        fig = px.scatter(
            df_plot,
            x="timestamp",
            y="valor",
            color="tipo",
            hover_data=["partido", "casa_a", "casa_b", "prioridad"],
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


# ── Surebets T-Money ──
elif page == "Surebets T-Money":
    st.title("💰 Surebets T-Money Monitor")

    since_iso = since.strftime("%Y-%m-%dT%H:%M:%S")
    df = query_table("tmoney_surebets", filters=f"timestamp=gte.{since_iso}", limit=5000)

    if len(df) == 0:
        st.info("Sin datos de T-Money en este periodo")
    else:
        # Dedup
        df_u = df.drop_duplicates(subset=["pct", "event", "market1"], keep="last")

        # KPIs
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total", len(df))
        with col2:
            st.metric("Unicas", len(df_u))
        with col3:
            best = float(df_u["pct"].max()) if "pct" in df_u.columns and len(df_u) > 0 else 0
            st.metric("Mejor %", f"{best:.2f}%")
        with col4:
            avg = float(df_u["pct"].mean()) if "pct" in df_u.columns and len(df_u) > 0 else 0
            st.metric("Promedio %", f"{avg:.2f}%")
        with col5:
            success = len(df[df["status"] == "SUCCESS"]) if "status" in df.columns else 0
            st.metric("SUCCESS", success)

        # Status chart
        if "status" in df.columns:
            st.subheader("Status de ejecucion")
            status_counts = df["status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            fig = px.bar(status_counts, x="Status", y="Count", color="Status")
            st.plotly_chart(fig, use_container_width=True)

        # Sport + Casa breakdown
        col1, col2 = st.columns(2)
        with col1:
            if "sport" in df_u.columns:
                st.subheader("Por deporte")
                sports = df_u["sport"].str[:20].value_counts().head(8).reset_index()
                sports.columns = ["Deporte", "Count"]
                fig = px.pie(sports, values="Count", names="Deporte")
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            if "casa1" in df_u.columns and "casa2" in df_u.columns:
                st.subheader("Par de casas")
                df_u["pair"] = df_u["casa1"].fillna("?") + " vs " + df_u["casa2"].fillna("?")
                pairs = df_u["pair"].value_counts().head(8).reset_index()
                pairs.columns = ["Par", "Count"]
                fig = px.bar(pairs, x="Par", y="Count", color="Par")
                st.plotly_chart(fig, use_container_width=True)

        # Timeline
        if "timestamp" in df_u.columns and "pct" in df_u.columns:
            st.subheader("Timeline")
            df_plot = df_u.copy()
            df_plot["timestamp"] = pd.to_datetime(df_plot["timestamp"])
            fig = px.scatter(df_plot, x="timestamp", y="pct",
                color="status" if "status" in df_plot.columns else None,
                hover_data=[c for c in ["event", "casa1", "casa2", "market1", "sport"] if c in df_plot.columns],
                title="Oportunidades detectadas")
            fig.update_yaxes(title="Profit %")
            st.plotly_chart(fig, use_container_width=True)

        # Profit distribution
        if "pct" in df_u.columns:
            st.subheader("Distribucion de profit")
            fig = px.histogram(df_u, x="pct", nbins=30)
            fig.update_xaxes(title="Profit %")
            st.plotly_chart(fig, use_container_width=True)

        # Executed surebets detail
        if "initial_odds1" in df.columns:
            executed = df[df["status"].isin(["SUCCESS", "ODDS_CHANGED", "REJECTED", "CLICK_FAIL", "NAV_FAIL"])]
            executed = executed[executed["initial_odds1"].notna() | executed["dt_total"].notna()]
            if len(executed) > 0:
                st.subheader("Ejecuciones detalladas")
                exec_cols = [c for c in [
                    "timestamp", "pct", "status", "sport", "event",
                    "casa1", "market1", "initial_odds1", "final_odds1", "odds1_held",
                    "casa2", "market2", "initial_odds2", "final_odds2", "odds2_held",
                    "dt_total", "dt_click", "betslip_duration_s", "between_quarters",
                ] if c in executed.columns]
                st.dataframe(
                    executed[exec_cols].sort_values("timestamp", ascending=False).head(50),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "pct": st.column_config.NumberColumn("Profit %", format="%.2f%%"),
                        "dt_total": st.column_config.NumberColumn("Total (s)", format="%.1f"),
                        "dt_click": st.column_config.NumberColumn("Click (s)", format="%.2f"),
                        "betslip_duration_s": st.column_config.NumberColumn("Hold (s)", format="%.0f"),
                    },
                )

        # SUCCESS highlight
        if "status" in df.columns:
            successes = df[df["status"] == "SUCCESS"]
            if len(successes) > 0:
                st.subheader("SUREBETS EXITOSAS")
                for _, row in successes.iterrows():
                    st.success(
                        f"**{row.get('pct', 0):.2f}%** | {row.get('event', '?')} | "
                        f"{row.get('sport', '?')}\n\n"
                        f"**{row.get('casa1', '?')}**: {row.get('market1', '')} "
                        f"odds: {row.get('initial_odds1', '?')} → {row.get('final_odds1', '?')} "
                        f"({'HELD' if row.get('odds1_held') else 'MOVED'})\n\n"
                        f"**{row.get('casa2', '?')}**: {row.get('market2', '')} "
                        f"odds: {row.get('initial_odds2', '?')} → {row.get('final_odds2', '?')} "
                        f"({'HELD' if row.get('odds2_held') else 'MOVED'})\n\n"
                        f"Tiempo: {row.get('dt_total', 0):.1f}s | "
                        f"Hold: {row.get('betslip_duration_s', 0):.0f}s | "
                        f"Entre cuartos: {'Si' if row.get('between_quarters') else 'No'}"
                    )

        # Full table
        st.subheader("Todas las detecciones")
        display_cols = [c for c in ["timestamp", "pct", "sport", "event", "tab", "casa1", "casa2",
                        "market1", "odds1", "market2", "odds2", "status", "priority", "is_nba"]
                        if c in df_u.columns]
        st.dataframe(df_u[display_cols].sort_values("pct", ascending=False).head(100),
                     use_container_width=True, hide_index=True)

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
