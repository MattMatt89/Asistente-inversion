import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import plotly.graph_objects as go
import json
import os

st.set_page_config(page_title="Asistente de Inversión", layout="wide")

CARTERA_FILE = os.path.join(os.path.expanduser("~"), "Desktop", "cartera.json")

def cargar_cartera():
    if os.path.exists(CARTERA_FILE):
        with open(CARTERA_FILE, "r") as f:
            return json.load(f)
    return []

def guardar_cartera(cartera):
    with open(CARTERA_FILE, "w") as f:
        json.dump(cartera, f, indent=2)

if "cartera" not in st.session_state:
    st.session_state.cartera = cargar_cartera()

pagina = st.sidebar.radio("Navegación", ["Análisis de acciones", "Mi cartera", "🔍 Screener"])

# ─── PÁGINA 1: ANÁLISIS ───────────────────────────────────────────────────────
if pagina == "Análisis de acciones":
    st.title("Análisis de acciones")

    busqueda = st.text_input("Busca una empresa o ticker", placeholder="Ej: Tesla, Apple, Inditex...")
    ticker_seleccionado = None
    eleccion = None

    if busqueda and len(busqueda) >= 2:
        with st.spinner("Buscando..."):
            try:
                resultados = yf.Search(busqueda, max_results=6)
                quotes = resultados.quotes
                if quotes:
                    opciones = {
                        f"{q.get('shortname') or q.get('longname', 'Sin nombre')} ({q['symbol']})": q['symbol']
                        for q in quotes if q.get('symbol')
                    }
                    eleccion = st.selectbox("Selecciona la empresa", list(opciones.keys()))
                    ticker_seleccionado = opciones[eleccion]
                else:
                    st.warning("No se encontraron resultados.")
            except Exception as e:
                st.error(f"Error en la búsqueda: {e}")

    periodo = st.selectbox("Período", ["1mo", "3mo", "6mo", "1y", "2y"])

    if ticker_seleccionado:
        datos = yf.download(ticker_seleccionado, period=periodo, auto_adjust=True)

        if datos.empty:
            st.error("No se pudieron cargar datos para este ticker.")
        else:
            close = datos["Close"].squeeze()
            precio_actual = close.iloc[-1].item()
            precio_ayer = close.iloc[-2].item()
            cambio = precio_actual - precio_ayer
            cambio_pct = (cambio / precio_ayer) * 100

            datos["SMA20"] = ta.trend.SMAIndicator(close=close, window=20).sma_indicator()
            datos["SMA50"] = ta.trend.SMAIndicator(close=close, window=50).sma_indicator()
            bb = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
            datos["BB_alta"] = bb.bollinger_hband()
            datos["BB_baja"] = bb.bollinger_lband()
            datos["RSI"] = ta.momentum.RSIIndicator(close=close, window=14).rsi()
            macd_ind = ta.trend.MACD(close=close)
            datos["MACD"] = macd_ind.macd()
            datos["Señal"] = macd_ind.macd_signal()

            ticker_obj = yf.Ticker(ticker_seleccionado)
            info = ticker_obj.info
            financials = ticker_obj.financials
            cashflow = ticker_obj.cashflow
            balance = ticker_obj.balance_sheet

            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📊 Resumen", "📋 Datos financieros", "📈 Análisis fundamental", "⭐ Opiniones analistas", "📰 Noticias"
            ])

            # ── TAB 1: RESUMEN ────────────────────────────────────────────────
            with tab1:
                pe = info.get("trailingPE", None)
                market_cap = info.get("marketCap", None)

                col1, col2, col3, col4, col5 = st.columns(5)
                col1.metric("Precio actual", f"${precio_actual:.2f}")
                col2.metric("Cambio hoy", f"${cambio:.2f}", f"{cambio_pct:.2f}%")
                col3.metric("Volumen", f"{datos['Volume'].iloc[-1].item():,.0f}")
                col4.metric("P/E Ratio", f"{pe:.1f}x" if pe else "N/D")
                col5.metric("Market Cap", f"${market_cap/1e9:.1f}B" if market_cap else "N/D")

                st.subheader("Precio de cierre")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=datos.index, y=datos["BB_alta"].squeeze(),
                    line=dict(color="gray", width=1, dash="dot"), name="BB Alta"))
                fig.add_trace(go.Scatter(x=datos.index, y=datos["BB_baja"].squeeze(),
                    line=dict(color="gray", width=1, dash="dot"), name="BB Baja",
                    fill="tonexty", fillcolor="rgba(128,128,128,0.1)"))
                fig.add_trace(go.Scatter(x=datos.index, y=close,
                    line=dict(color="#4A90D9", width=2), name="Precio"))
                fig.add_trace(go.Scatter(x=datos.index, y=datos["SMA20"].squeeze(),
                    line=dict(color="#F5A623", width=1.5), name="SMA 20"))
                fig.add_trace(go.Scatter(x=datos.index, y=datos["SMA50"].squeeze(),
                    line=dict(color="#7ED321", width=1.5), name="SMA 50"))
                fig.update_layout(height=400, legend=dict(orientation="h"),
                    margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig, use_container_width=True)

                rsi_actual = datos["RSI"].iloc[-1].item()
                macd_val = datos["MACD"].iloc[-1].item()
                signal_val = datos["Señal"].iloc[-1].item()
                precio_sma20 = datos["SMA20"].iloc[-1].item()
                precio_sma50 = datos["SMA50"].iloc[-1].item()

                score = 50
                razones = []
                if rsi_actual < 30: score += 20; razones.append(f"RSI {rsi_actual:.1f} — sobrevendido")
                elif rsi_actual < 40: score += 10; razones.append(f"RSI {rsi_actual:.1f} — zona baja")
                elif rsi_actual > 70: score -= 20; razones.append(f"RSI {rsi_actual:.1f} — sobrecomprado")
                elif rsi_actual > 60: score -= 10; razones.append(f"RSI {rsi_actual:.1f} — zona alta")
                else: razones.append(f"RSI {rsi_actual:.1f} — zona neutral")
                if macd_val > signal_val: score += 15; razones.append("MACD alcista")
                else: score -= 15; razones.append("MACD bajista")
                if precio_actual > precio_sma20: score += 10; razones.append("Por encima de SMA20")
                else: score -= 10; razones.append("Por debajo de SMA20")
                if precio_actual > precio_sma50: score += 5; razones.append("Por encima de SMA50")
                else: score -= 5; razones.append("Por debajo de SMA50")
                score = max(0, min(100, score))

                col1, col2 = st.columns([1, 2])
                with col1:
                    if score >= 65: st.success(f"### COMPRAR\nScore: {score}/100")
                    elif score <= 35: st.error(f"### VENDER\nScore: {score}/100")
                    else: st.warning(f"### MANTENER\nScore: {score}/100")
                with col2:
                    st.caption("Factores:")
                    for r in razones:
                        st.caption(f"· {r}")

                st.caption("⚠️ Orientativo, no constituye asesoramiento financiero.")
                st.divider()
                st.subheader("Añadir a mi cartera")
                with st.form("añadir_posicion"):
                    col1, col2 = st.columns(2)
                    cantidad = col1.number_input("Cantidad de acciones", min_value=0.01, value=1.0, step=0.01)
                    precio_compra = col2.number_input("Precio de compra ($)", min_value=0.01, value=1.0, step=0.01)
                    submitted = st.form_submit_button("Añadir a cartera")
                    if submitted:
                        nueva = {
                            "ticker": ticker_seleccionado,
                            "nombre": eleccion.split(" (")[0],
                            "cantidad": cantidad,
                            "precio_compra": precio_compra,
                            "fecha": ""
                        }
                        st.session_state.cartera.append(nueva)
                        guardar_cartera(st.session_state.cartera)
                        st.success(f"{ticker_seleccionado} añadido a tu cartera.")

            # ── TAB 2: DATOS FINANCIEROS ──────────────────────────────────────
            with tab2:
                st.subheader("Datos financieros de la empresa")
                try:
                    datos_emp = {
                        "Nombre": info.get("longName", "N/D"),
                        "Sector": info.get("sector", "N/D"),
                        "Industria": info.get("industry", "N/D"),
                        "País": info.get("country", "N/D"),
                        "Empleados": f"{info.get('fullTimeEmployees', 0):,}" if info.get("fullTimeEmployees") else "N/D",
                        "Web": info.get("website", "N/D"),
                    }
                    col1, col2 = st.columns(2)
                    for i, (k, v) in enumerate(datos_emp.items()):
                        (col1 if i % 2 == 0 else col2).metric(k, v)
                    st.divider()
                    st.subheader("Descripción")
                    st.write(info.get("longBusinessSummary", "Sin descripción disponible."))
                    st.divider()
                    st.subheader("Métricas clave")
                    metricas = {
                        "P/E Ratio (TTM)": f"{info.get('trailingPE'):.2f}" if isinstance(info.get('trailingPE'), float) else "N/D",
                        "P/E Forward": f"{info.get('forwardPE'):.2f}" if isinstance(info.get('forwardPE'), float) else "N/D",
                        "P/B Ratio": f"{info.get('priceToBook'):.2f}" if isinstance(info.get('priceToBook'), float) else "N/D",
                        "EV/EBITDA": f"{info.get('enterpriseToEbitda'):.2f}" if isinstance(info.get('enterpriseToEbitda'), float) else "N/D",
                        "EPS (TTM)": f"${info.get('trailingEps'):.2f}" if isinstance(info.get('trailingEps'), float) else "N/D",
                        "ROE": f"{info.get('returnOnEquity')*100:.2f}%" if info.get('returnOnEquity') else "N/D",
                        "ROA": f"{info.get('returnOnAssets')*100:.2f}%" if info.get('returnOnAssets') else "N/D",
                        "Margen bruto": f"{info.get('grossMargins')*100:.2f}%" if info.get('grossMargins') else "N/D",
                        "Margen operativo": f"{info.get('operatingMargins')*100:.2f}%" if info.get('operatingMargins') else "N/D",
                        "Margen neto": f"{info.get('profitMargins')*100:.2f}%" if info.get('profitMargins') else "N/D",
                        "Deuda/Equity": f"{info.get('debtToEquity'):.2f}" if isinstance(info.get('debtToEquity'), float) else "N/D",
                        "Current Ratio": f"{info.get('currentRatio'):.2f}" if isinstance(info.get('currentRatio'), float) else "N/D",
                        "Quick Ratio": f"{info.get('quickRatio'):.2f}" if isinstance(info.get('quickRatio'), float) else "N/D",
                        "52w Máximo": f"${info.get('fiftyTwoWeekHigh'):.2f}" if isinstance(info.get('fiftyTwoWeekHigh'), float) else "N/D",
                        "52w Mínimo": f"${info.get('fiftyTwoWeekLow'):.2f}" if isinstance(info.get('fiftyTwoWeekLow'), float) else "N/D",
                        "Dividendo yield": f"{info.get('dividendYield')*100:.2f}%" if info.get('dividendYield') else "0%",
                    }
                    cols = st.columns(4)
                    for i, (k, v) in enumerate(metricas.items()):
                        cols[i % 4].metric(k, v)
                except Exception as e:
                    st.warning(f"No se pudieron cargar los datos: {e}")

            # ── TAB 3: ANÁLISIS FUNDAMENTAL ───────────────────────────────────
            with tab3:
                st.subheader("Los 8 pilares (Everything Money)")

                def pilar(nombre, valor, descripcion, estado):
                    icono = "🟢" if estado == "bien" else "🔴" if estado == "mal" else "🟡"
                    c1, c2, c3 = st.columns([2, 2, 4])
                    c1.markdown(f"{icono} **{nombre}**")
                    c2.markdown(f"`{valor}`")
                    c3.caption(descripcion)

                try:
                    pe = info.get("trailingPE", None)
                    if pe: pilar("P/E Ratio", f"{pe:.1f}x", "Bueno < 20 · Caro > 40", "bien" if pe < 20 else "mal" if pe > 40 else "neutral")
                    else: pilar("P/E Ratio", "N/D", "Sin datos", "neutral")

                    roic = info.get("returnOnEquity", None)
                    if roic: pilar("ROIC", f"{roic*100:.1f}%", "Bueno > 12% · Malo < 5%", "bien" if roic > 0.12 else "mal" if roic < 0.05 else "neutral")
                    else: pilar("ROIC", "N/D", "Sin datos", "neutral")

                    try:
                        ing = financials.loc["Total Revenue"].dropna()
                        if len(ing) >= 2:
                            crec = (ing.iloc[0] - ing.iloc[-1]) / abs(ing.iloc[-1])
                            pilar("Crecimiento ingresos", f"{crec*100:.1f}%", "Bueno > 5% · Malo < 0%", "bien" if crec > 0.05 else "mal" if crec < 0 else "neutral")
                        else: pilar("Crecimiento ingresos", "N/D", "Sin datos suficientes", "neutral")
                    except: pilar("Crecimiento ingresos", "N/D", "Sin datos", "neutral")

                    try:
                        ben = financials.loc["Net Income"].dropna()
                        if len(ben) >= 2:
                            crec = (ben.iloc[0] - ben.iloc[-1]) / abs(ben.iloc[-1])
                            pilar("Crecimiento beneficio neto", f"{crec*100:.1f}%", "Bueno > 5% · Malo < 0%", "bien" if crec > 0.05 else "mal" if crec < 0 else "neutral")
                        else: pilar("Crecimiento beneficio neto", "N/D", "Sin datos suficientes", "neutral")
                    except: pilar("Crecimiento beneficio neto", "N/D", "Sin datos", "neutral")

                    shares_now = info.get("sharesOutstanding", None)
                    shares_prev = info.get("impliedSharesOutstanding", None)
                    if shares_now:
                        sm = shares_now / 1_000_000
                        if shares_prev and shares_prev > 0:
                            diff = (shares_now - shares_prev) / shares_prev
                            pilar("Acciones en circulación", f"{sm:.0f}M", "Bueno: bajando · Malo: subiendo >3%", "bien" if diff < 0 else "mal" if diff > 0.03 else "neutral")
                        else: pilar("Acciones en circulación", f"{sm:.0f}M", "Sin comparativa", "neutral")
                    else: pilar("Acciones en circulación", "N/D", "Sin datos", "neutral")

                    try:
                        deu = balance.loc["Long Term Debt"].dropna()
                        fcf_s = cashflow.loc["Free Cash Flow"].dropna() if "Free Cash Flow" in cashflow.index else None
                        if len(deu) >= 1 and fcf_s is not None and len(fcf_s) >= 1:
                            ratio = deu.iloc[0] / abs(fcf_s.iloc[0])
                            pilar("Deuda L/P / FCF", f"{ratio:.1f}x", "Bueno < 3x · Malo > 5x", "bien" if ratio < 3 else "mal" if ratio > 5 else "neutral")
                        else: pilar("Deuda L/P / FCF", "N/D", "Sin datos", "neutral")
                    except: pilar("Deuda L/P / FCF", "N/D", "Sin datos", "neutral")

                    try:
                        fcf = cashflow.loc["Free Cash Flow"].dropna() if "Free Cash Flow" in cashflow.index else (cashflow.loc["Operating Cash Flow"].dropna() - cashflow.loc["Capital Expenditure"].dropna())
                        if len(fcf) >= 2:
                            crec = (fcf.iloc[0] - fcf.iloc[-1]) / abs(fcf.iloc[-1])
                            pilar("Crecimiento FCF", f"{crec*100:.1f}%", "Bueno > 5% · Malo < 0%", "bien" if crec > 0.05 else "mal" if crec < 0 else "neutral")
                        else: pilar("Crecimiento FCF", "N/D", "Sin datos suficientes", "neutral")
                    except: pilar("Crecimiento FCF", "N/D", "Sin datos", "neutral")

                    try:
                        mc = info.get("marketCap", None)
                        fcf_a = cashflow.loc["Free Cash Flow"].dropna().iloc[0] if "Free Cash Flow" in cashflow.index else (cashflow.loc["Operating Cash Flow"].dropna().iloc[0] - cashflow.loc["Capital Expenditure"].dropna().iloc[0])
                        if mc and fcf_a > 0:
                            mult = mc / fcf_a
                            pilar("Múltiplo FCF (P/FCF)", f"{mult:.1f}x", "Bueno < 20x · Caro > 40x", "bien" if mult < 20 else "mal" if mult > 40 else "neutral")
                        else: pilar("Múltiplo FCF (P/FCF)", "N/D", "FCF negativo o sin datos", "neutral")
                    except: pilar("Múltiplo FCF (P/FCF)", "N/D", "Sin datos", "neutral")

                    st.caption("🟢 Bien  🟡 Neutral  🔴 Atención — Datos de Yahoo Finance.")
                except Exception as e:
                    st.warning(f"Error cargando 8 pilares: {e}")

                st.divider()
                years = lambda df: [str(d.year) for d in df.index]

                try:
                    st.subheader("Ingresos y Beneficio Neto")
                    ing = financials.loc["Total Revenue"].dropna().sort_index()
                    ben = financials.loc["Net Income"].dropna().sort_index()
                    fig1 = go.Figure()
                    fig1.add_trace(go.Bar(x=years(ing), y=ing.values/1e9, name="Ingresos (B$)", marker_color="#4A90D9"))
                    fig1.add_trace(go.Bar(x=years(ben), y=ben.values/1e9, name="Beneficio Neto (B$)", marker_color="#7ED321"))
                    fig1.update_layout(height=320, barmode="group", margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h"))
                    st.plotly_chart(fig1, use_container_width=True)
                except: st.info("Sin datos de ingresos.")

                try:
                    st.subheader("Márgenes Operativos")
                    ing = financials.loc["Total Revenue"].dropna().sort_index()
                    fig2 = go.Figure()
                    if "Gross Profit" in financials.index:
                        gp = financials.loc["Gross Profit"].dropna().sort_index()
                        gm = (gp / ing * 100).dropna()
                        fig2.add_trace(go.Scatter(x=years(gm), y=gm.values, name="Gross Margin %", line=dict(color="#4A90D9", width=2)))
                    if "Operating Income" in financials.index:
                        op = financials.loc["Operating Income"].dropna().sort_index()
                        om = (op / ing * 100).dropna()
                        fig2.add_trace(go.Scatter(x=years(om), y=om.values, name="Operating Margin %", line=dict(color="#F5A623", width=2)))
                    ni = financials.loc["Net Income"].dropna().sort_index()
                    nm = (ni / ing * 100).dropna()
                    fig2.add_trace(go.Scatter(x=years(nm), y=nm.values, name="Net Margin %", line=dict(color="#7ED321", width=2)))
                    fig2.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h"))
                    st.plotly_chart(fig2, use_container_width=True)
                except: st.info("Sin datos de márgenes.")

                try:
                    st.subheader("Salud de Deuda")
                    deu_key = "Total Debt" if "Total Debt" in balance.index else "Long Term Debt"
                    eq_key = "Stockholders Equity" if "Stockholders Equity" in balance.index else "Total Equity Gross Minority Interest"
                    deu = balance.loc[deu_key].dropna().sort_index()
                    eq = balance.loc[eq_key].dropna().sort_index()
                    fig3 = go.Figure()
                    fig3.add_trace(go.Bar(x=years(deu), y=deu.values/1e9, name="Deuda Total (B$)", marker_color="#E74C3C"))
                    fig3.add_trace(go.Bar(x=years(eq), y=eq.values/1e9, name="Patrimonio Neto (B$)", marker_color="#7ED321"))
                    fig3.update_layout(height=300, barmode="group", margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h"))
                    st.plotly_chart(fig3, use_container_width=True)
                except: st.info("Sin datos de deuda.")

                try:
                    st.subheader("Liquidez a Corto Plazo")
                    cr = info.get("currentRatio", None)
                    qr = info.get("quickRatio", None)
                    if cr or qr:
                        fig4 = go.Figure()
                        if cr: fig4.add_trace(go.Bar(x=["Current Ratio"], y=[cr], name="Current Ratio", marker_color="#4A90D9"))
                        if qr: fig4.add_trace(go.Bar(x=["Quick Ratio"], y=[qr], name="Quick Ratio", marker_color="#F5A623"))
                        fig4.add_hline(y=1, line_dash="dot", line_color="red", annotation_text="Mínimo recomendado")
                        fig4.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0))
                        st.plotly_chart(fig4, use_container_width=True)
                    else: st.info("Sin datos de liquidez.")
                except: st.info("Sin datos de liquidez.")

                try:
                    st.subheader("Flujo de Caja")
                    ocf = cashflow.loc["Operating Cash Flow"].dropna().sort_index()
                    fcf = cashflow.loc["Free Cash Flow"].dropna().sort_index() if "Free Cash Flow" in cashflow.index else (ocf - cashflow.loc["Capital Expenditure"].dropna().sort_index()).dropna()
                    fig5 = go.Figure()
                    fig5.add_trace(go.Bar(x=years(ocf), y=ocf.values/1e9, name="Operating CF (B$)", marker_color="#4A90D9"))
                    fig5.add_trace(go.Bar(x=years(fcf), y=fcf.values/1e9, name="Free CF (B$)", marker_color="#7ED321"))
                    fig5.update_layout(height=300, barmode="group", margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h"))
                    st.plotly_chart(fig5, use_container_width=True)
                except: st.info("Sin datos de cash flow.")

                try:
                    st.subheader("Rentabilidad sobre Capital (ROE / ROA)")
                    roe = info.get("returnOnEquity", None)
                    roa = info.get("returnOnAssets", None)
                    if roe or roa:
                        fig6 = go.Figure()
                        if roe: fig6.add_trace(go.Bar(x=["ROE %"], y=[roe*100], marker_color="#9B59B6", name="ROE"))
                        if roa: fig6.add_trace(go.Bar(x=["ROA %"], y=[roa*100], marker_color="#4A90D9", name="ROA"))
                        fig6.add_hline(y=12, line_dash="dot", line_color="green", annotation_text="Objetivo > 12%")
                        fig6.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0))
                        st.plotly_chart(fig6, use_container_width=True)
                    else: st.info("Sin datos de rentabilidad.")
                except: st.info("Sin datos de rentabilidad.")

                try:
                    st.subheader("Valoración (P/E · P/E Forward · EV/EBITDA)")
                    vals, lbs = [], []
                    if info.get("trailingPE"): vals.append(info["trailingPE"]); lbs.append("P/E TTM")
                    if info.get("forwardPE"): vals.append(info["forwardPE"]); lbs.append("P/E Forward")
                    if info.get("enterpriseToEbitda"): vals.append(info["enterpriseToEbitda"]); lbs.append("EV/EBITDA")
                    if vals:
                        fig8 = go.Figure()
                        fig8.add_trace(go.Bar(x=lbs, y=vals, marker_color=["#4A90D9","#F5A623","#7ED321"][:len(vals)]))
                        fig8.add_hline(y=20, line_dash="dot", line_color="green", annotation_text="P/E justo ~20x")
                        fig8.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0))
                        st.plotly_chart(fig8, use_container_width=True)
                    else: st.info("Sin datos de valoración.")
                except: st.info("Sin datos de valoración.")

                try:
                    div_yield = info.get("dividendYield", None)
                    payout = info.get("payoutRatio", None)
                    if div_yield and div_yield > 0:
                        st.subheader("Dividendos y Payout")
                        fig9 = go.Figure()
                        fig9.add_trace(go.Bar(x=["Dividend Yield %"], y=[div_yield*100], marker_color="#4A90D9", name="Yield"))
                        if payout: fig9.add_trace(go.Bar(x=["Payout Ratio %"], y=[payout*100], marker_color="#F5A623", name="Payout"))
                        fig9.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h"))
                        st.plotly_chart(fig9, use_container_width=True)
                    else: st.info("Esta empresa no paga dividendos.")
                except: st.info("Sin datos de dividendos.")

            # ── TAB 4: OPINIONES ANALISTAS ────────────────────────────────────
            with tab4:
                st.subheader("Consenso de analistas")

                target_mean = info.get("targetMeanPrice", None)
                target_high = info.get("targetHighPrice", None)
                target_low = info.get("targetLowPrice", None)
                num_analistas = info.get("numberOfAnalystOpinions", None)
                recom_media = info.get("recommendationMean", None)
                recom_key = info.get("recommendationKey", "").upper().replace("_", " ")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Precio objetivo medio", f"${target_mean:.2f}" if target_mean else "N/D",
                    f"{((target_mean - precio_actual) / precio_actual * 100):+.1f}%" if target_mean else None)
                col2.metric("Precio objetivo alto", f"${target_high:.2f}" if target_high else "N/D")
                col3.metric("Precio objetivo bajo", f"${target_low:.2f}" if target_low else "N/D")
                col4.metric("Nº analistas", str(num_analistas) if num_analistas else "N/D")

                st.subheader("Valor intrínseco estimado (Graham Number)")
                try:
                    eps = info.get("trailingEps", None)
                    bvps = info.get("bookValue", None)
                    if eps and bvps and eps > 0 and bvps > 0:
                        graham = (22.5 * eps * bvps) ** 0.5
                        margen = ((graham - precio_actual) / precio_actual) * 100
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Graham Number", f"${graham:.2f}")
                        col2.metric("Precio actual", f"${precio_actual:.2f}")
                        col3.metric("Margen de seguridad", f"{margen:.1f}%",
                            delta=f"{'Infravalorado' if margen > 0 else 'Sobrevalorado'}")
                        if margen > 20:
                            st.success(f"✅ Cotiza un {margen:.1f}% por debajo del valor intrínseco — posible oportunidad.")
                        elif margen < -20:
                            st.error(f"⚠️ Cotiza un {abs(margen):.1f}% por encima del valor intrínseco — posiblemente cara.")
                        else:
                            st.info("Cotiza cerca de su valor intrínseco estimado.")
                    else:
                        st.info("Sin datos suficientes (se necesita EPS y Book Value positivos).")
                except:
                    st.info("No se pudo calcular el valor intrínseco.")

                st.caption("⚠️ El Graham Number es una estimación simplificada, no un valor intrínseco exacto.")
                st.divider()
                st.subheader("Distribución de recomendaciones")

                try:
                    rec = ticker_obj.recommendations
                    if rec is not None and not rec.empty:

                        # Nueva estructura: columnas strongBuy, buy, hold, sell, strongSell
                        if "strongBuy" in rec.columns:
                            # Sumar todos los períodos disponibles
                            total_sb = int(rec["strongBuy"].sum())
                            total_b = int(rec["buy"].sum())
                            total_h = int(rec["hold"].sum())
                            total_s = int(rec["sell"].sum())
                            total_ss = int(rec["strongSell"].sum()) if "strongSell" in rec.columns else 0

                            conteo = {
                                "Strong Buy": total_sb,
                                "Buy": total_b,
                                "Hold": total_h,
                                "Sell": total_s + total_ss
                            }
                            conteo = {k: v for k, v in conteo.items() if v > 0}
                            total_rec = sum(conteo.values())

                            colores_rec = {
                                "Strong Buy": "#1a7a1a",
                                "Buy": "#7ED321",
                                "Hold": "#A0A0A0",
                                "Sell": "#8B0000"
                            }

                            col1, col2 = st.columns([1, 1])

                            with col1:
                                st.markdown("#### Ratings por categoría")
                                for cat, val in conteo.items():
                                    pct = (val / total_rec) * 100
                                    color = colores_rec[cat]
                                    barra_llena = int(pct / 5)
                                    barra = "█" * barra_llena + "░" * (20 - barra_llena)
                                    st.markdown(
                                        f"<div style='margin-bottom:10px'>"
                                        f"<span style='color:{color};font-weight:bold;min-width:110px;display:inline-block'>{cat}</span>"
                                        f"<span style='font-family:monospace;color:{color};letter-spacing:-1px'>{barra}</span>"
                                        f"<span style='margin-left:8px;font-weight:bold'>{val}</span>"
                                        f"<span style='color:#888;font-size:12px;margin-left:4px'>({pct:.0f}%)</span>"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )
                                st.divider()
                                if recom_key:
                                    color_cons = "#1a7a1a" if "buy" in recom_key.lower() else "#8B0000" if "sell" in recom_key.lower() else "#A0A0A0"
                                    st.markdown(
                                        f"<div style='text-align:center;padding:12px;border:2px solid {color_cons};border-radius:8px'>"
                                        f"<div style='font-size:22px;font-weight:bold;color:{color_cons}'>{recom_key}</div>"
                                        f"<div style='color:#888;font-size:13px'>Basado en {total_rec} analistas</div>"
                                        f"</div>",
                                        unsafe_allow_html=True
                                    )
                                if recom_media:
                                    st.caption(f"Puntuación media: {recom_media:.2f} / 5.0 · (1 = Strong Buy · 5 = Strong Sell)")

                            with col2:
                                color_list = [colores_rec[g] for g in conteo.keys()]
                                fig_donut = go.Figure(go.Pie(
                                    labels=list(conteo.keys()),
                                    values=list(conteo.values()),
                                    hole=0.6,
                                    marker=dict(colors=color_list),
                                    textinfo="none",
                                    hovertemplate="%{label}: %{value} analistas (%{percent})<extra></extra>"
                                ))
                                fig_donut.add_annotation(
                                    text=f"<b>{total_rec}</b><br>Ratings",
                                    x=0.5, y=0.5,
                                    font=dict(size=18),
                                    showarrow=False
                                )
                                fig_donut.update_layout(
                                    height=340,
                                    margin=dict(l=0, r=0, t=20, b=0),
                                    showlegend=True,
                                    legend=dict(orientation="h", y=-0.1)
                                )
                                st.plotly_chart(fig_donut, use_container_width=True)

                        st.divider()
                        st.subheader("Historial de recomendaciones recientes")
                        st.dataframe(rec.tail(10).iloc[::-1], use_container_width=True, hide_index=True)

                    else:
                        st.info("No hay recomendaciones disponibles.")

                except Exception as e:
                    st.info(f"No se pudieron cargar las recomendaciones: {e}")

            # ── TAB 5: NOTICIAS ───────────────────────────────────────────────
            with tab5:
                st.subheader(f"Últimas noticias — {ticker_seleccionado}")
                try:
                    noticias = ticker_obj.news
                    if noticias:
                        for n in noticias[:10]:
                            titulo = n.get("content", {}).get("title", "Sin título")
                            url = n.get("content", {}).get("canonicalUrl", {}).get("url", "#")
                            fuente = n.get("content", {}).get("provider", {}).get("displayName", "Fuente desconocida")
                            fecha = n.get("content", {}).get("pubDate", "")[:10]
                            resumen = n.get("content", {}).get("summary", "")
                            with st.expander(f"📰 {titulo}"):
                                st.caption(f"{fuente} · {fecha}")
                                if resumen:
                                    st.write(resumen)
                                st.markdown(f"[Leer artículo completo →]({url})")
                    else:
                        st.info("No hay noticias disponibles.")
                except Exception:
                    st.info("No se pudieron cargar las noticias.")

# ─── PÁGINA 2: CARTERA ───────────────────────────────────────────────────────
elif pagina == "Mi cartera":
    st.title("Mi cartera")

    if not st.session_state.cartera:
        st.info("Tu cartera está vacía. Ve a 'Análisis de acciones' para añadir posiciones.")
    else:
        filas = []
        total_invertido = 0
        total_actual = 0

        for i, pos in enumerate(st.session_state.cartera):
            try:
                inf = yf.Ticker(pos["ticker"]).fast_info
                precio_hoy = inf.last_price
                if precio_hoy is None:
                    raise ValueError("Sin precio")
            except Exception:
                try:
                    d = yf.download(pos["ticker"], period="5d", auto_adjust=True)
                    precio_hoy = d["Close"].iloc[-1].item()
                except Exception:
                    precio_hoy = pos["precio_compra"]

            invertido = pos["cantidad"] * pos["precio_compra"]
            actual = pos["cantidad"] * precio_hoy
            pl = actual - invertido
            pl_pct = (pl / invertido) * 100
            total_invertido += invertido
            total_actual += actual

            filas.append({
                "Empresa": pos["nombre"],
                "Ticker": pos["ticker"],
                "Cantidad": pos["cantidad"],
                "Precio compra": pos["precio_compra"],
                "Precio actual": precio_hoy,
                "Invertido": invertido,
                "Valor actual": actual,
                "P&L ($)": pl,
                "P&L (%)": pl_pct,
            })

        pl_total = total_actual - total_invertido
        pl_total_pct = (pl_total / total_invertido) * 100

        col1, col2, col3 = st.columns(3)
        col1.metric("Total invertido", f"${total_invertido:,.2f}")
        col2.metric("Valor actual", f"${total_actual:,.2f}")
        col3.metric("P&L total", f"${pl_total:,.2f}", f"{pl_total_pct:.2f}%")

        st.divider()

        df = pd.DataFrame(filas)

        def color_pl(val):
            color = "#1a7a1a" if val > 0 else "#8B0000" if val < 0 else "#555555"
            return f"color: {color}; font-weight: bold"

        def format_usd(val):
            return f"${val:,.2f}"

        def format_pct(val):
            return f"{val:+.2f}%"

        styled = df.style \
            .format({
                "Precio compra": format_usd,
                "Precio actual": format_usd,
                "Invertido": format_usd,
                "Valor actual": format_usd,
                "P&L ($)": format_usd,
                "P&L (%)": format_pct,
            }) \
            .map(color_pl, subset=["P&L ($)", "P&L (%)"])

        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Distribución de la cartera")
        labels = [f["Ticker"] for f in filas]
        values = [f["Valor actual"] for f in filas]
        fig_pie = go.Figure(go.Pie(labels=labels, values=values, hole=0.4))
        fig_pie.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()
        st.subheader("Eliminar una posición")
        opciones_borrar = [f"{f['Empresa']} ({f['Ticker']})" for f in filas]
        seleccion = st.selectbox("Selecciona la posición a eliminar", opciones_borrar)
        if st.button("Eliminar posición"):
            idx = opciones_borrar.index(seleccion)
            st.session_state.cartera.pop(idx)
            guardar_cartera(st.session_state.cartera)
            st.rerun()

            # ─── PÁGINA 3: SCREENER ───────────────────────────────────────────────────────
elif pagina == "🔍 Screener":
    st.title("Screener S&P 500")
    st.caption("Filtra entre las 500 empresas más grandes de EEUU. La carga inicial tarda ~30 segundos.")

    # Lista S&P 500 via Wikipedia
    @st.cache_data(ttl=86400)
    def cargar_sp500():
        try:
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "parse",
                "page": "List_of_S%26P_500_companies",
                "prop": "wikitext",
                "format": "json"
            }
            import re, requests
            r = requests.get(url, params=params, timeout=10)
            texto = r.json()["parse"]["wikitext"]["*"]
            filas = re.findall(r'\|\|([A-Z]{1,5}(?:-[A-Z])?)\n\|\|(.+?)\n\|\|(.+?)\n', texto)
            if filas:
                df = pd.DataFrame(filas, columns=["Ticker", "Empresa", "Sector"])
                df["Ticker"] = df["Ticker"].str.strip()
                df["Empresa"] = df["Empresa"].str.strip()
                df["Sector"] = df["Sector"].str.strip()
                return df[df["Ticker"].str.len() <= 5].reset_index(drop=True)
            else:
                raise ValueError("No se encontraron datos en el wikitext")
        except Exception as e:
            st.warning(f"No se pudo cargar desde Wikipedia API: {e}. Usando lista de respaldo.")
            empresas = [
                ("AAPL","Apple","Information Technology"),("MSFT","Microsoft","Information Technology"),
                ("NVDA","NVIDIA","Information Technology"),("AMZN","Amazon","Consumer Discretionary"),
                ("GOOGL","Alphabet A","Communication Services"),("META","Meta Platforms","Communication Services"),
                ("TSLA","Tesla","Consumer Discretionary"),("BRK-B","Berkshire Hathaway","Financials"),
                ("JPM","JPMorgan Chase","Financials"),("LLY","Eli Lilly","Health Care"),
                ("V","Visa","Financials"),("UNH","UnitedHealth","Health Care"),
                ("XOM","Exxon Mobil","Energy"),("MA","Mastercard","Financials"),
                ("JNJ","Johnson & Johnson","Health Care"),("PG","Procter & Gamble","Consumer Staples"),
                ("AVGO","Broadcom","Information Technology"),("HD","Home Depot","Consumer Discretionary"),
                ("MRK","Merck","Health Care"),("COST","Costco","Consumer Staples"),
                ("ABBV","AbbVie","Health Care"),("CVX","Chevron","Energy"),
                ("CRM","Salesforce","Information Technology"),("BAC","Bank of America","Financials"),
                ("NFLX","Netflix","Communication Services"),("AMD","AMD","Information Technology"),
                ("PEP","PepsiCo","Consumer Staples"),("TMO","Thermo Fisher","Health Care"),
                ("LIN","Linde","Materials"),("ORCL","Oracle","Information Technology"),
                ("WMT","Walmart","Consumer Staples"),("MCD","McDonald's","Consumer Discretionary"),
                ("ADBE","Adobe","Information Technology"),("CSCO","Cisco","Information Technology"),
                ("TXN","Texas Instruments","Information Technology"),("WFC","Wells Fargo","Financials"),
                ("NKE","Nike","Consumer Discretionary"),("NEE","NextEra Energy","Utilities"),
                ("PM","Philip Morris","Consumer Staples"),("INTC","Intel","Information Technology"),
                ("RTX","Raytheon","Industrials"),("UPS","UPS","Industrials"),
                ("QCOM","Qualcomm","Information Technology"),("HON","Honeywell","Industrials"),
                ("IBM","IBM","Information Technology"),("GE","GE Aerospace","Industrials"),
                ("CAT","Caterpillar","Industrials"),("LOW","Lowe's","Consumer Discretionary"),
                ("GS","Goldman Sachs","Financials"),("MS","Morgan Stanley","Financials"),
                ("BLK","BlackRock","Financials"),("DE","Deere","Industrials"),
                ("GILD","Gilead","Health Care"),("AXP","American Express","Financials"),
                ("BKNG","Booking Holdings","Consumer Discretionary"),("ISRG","Intuitive Surgical","Health Care"),
                ("VRTX","Vertex","Health Care"),("REGN","Regeneron","Health Care"),
                ("PANW","Palo Alto","Information Technology"),("SBUX","Starbucks","Consumer Discretionary"),
                ("KO","Coca-Cola","Consumer Staples"),("PFE","Pfizer","Health Care"),
                ("EOG","EOG Resources","Energy"),("SLB","SLB","Energy"),
                ("SO","Southern Company","Utilities"),("DUK","Duke Energy","Utilities"),
                ("CL","Colgate","Consumer Staples"),("MO","Altria","Consumer Staples"),
                ("TJX","TJX","Consumer Discretionary"),("MMM","3M","Industrials"),
                ("USB","US Bancorp","Financials"),("F","Ford","Consumer Discretionary"),
                ("GM","General Motors","Consumer Discretionary"),("UBER","Uber","Industrials"),
                ("COP","ConocoPhillips","Energy"),("OXY","Occidental","Energy"),
                ("PYPL","PayPal","Financials"),("SNOW","Snowflake","Information Technology"),
                ("PLTR","Palantir","Information Technology"),("ABNB","Airbnb","Consumer Discretionary"),
                ("SPOT","Spotify","Communication Services"),("COIN","Coinbase","Financials"),
            ]
            return pd.DataFrame(empresas, columns=["Ticker", "Empresa", "Sector"])

    @st.cache_data(ttl=3600)
    def cargar_datos_screener(tickers):
        filas = []
        progress = st.progress(0, text="Cargando datos...")
        total = len(tickers)
        for i, (ticker, empresa, sector) in enumerate(tickers):
            try:
                info = yf.Ticker(ticker).info
                filas.append({
                    "Ticker": ticker,
                    "Empresa": empresa,
                    "Sector": sector,
                    "Precio ($)": round(info.get("currentPrice") or info.get("regularMarketPrice") or 0, 2),
                    "Market Cap (B$)": round((info.get("marketCap") or 0) / 1e9, 1),
                    "P/E Ratio": round(info.get("trailingPE") or 0, 1),
                    "Dividendo (%)": round((info.get("dividendYield") or 0) * 100, 2),
                    "ROE (%)": round((info.get("returnOnEquity") or 0) * 100, 1),
                    "Margen neto (%)": round((info.get("profitMargins") or 0) * 100, 1),
                    "Deuda/Equity": round(info.get("debtToEquity") or 0, 1),
                    "52w Alto ($)": round(info.get("fiftyTwoWeekHigh") or 0, 2),
                    "52w Bajo ($)": round(info.get("fiftyTwoWeekLow") or 0, 2),
                })
            except Exception:
                pass
            progress.progress((i + 1) / total, text=f"Cargando {ticker}... ({i+1}/{total})")
        progress.empty()
        return pd.DataFrame(filas)

    sp500 = cargar_sp500()

    if sp500.empty:
        st.stop()

    # Controles de carga
    col1, col2 = st.columns([2, 1])
    with col1:
        max_empresas = st.slider("Número de empresas a analizar", 50, 500, 100, step=50)
        st.caption("Más empresas = más tiempo de carga. 100 tarda ~20s, 500 tarda ~2 min.")
    with col2:
        if st.button("🔄 Limpiar caché y recargar datos"):
            cargar_datos_screener.clear()
            st.rerun()

    tickers_list = list(zip(sp500["Ticker"], sp500["Empresa"], sp500["Sector"]))[:max_empresas]

    with st.spinner("Cargando datos del mercado..."):
        df_screen = cargar_datos_screener(tickers_list)

    if df_screen.empty:
        st.warning("No se pudieron cargar datos.")
        st.stop()

    st.divider()
    st.subheader("Filtros")

    col1, col2, col3, col4 = st.columns(4)

    # Filtro sector
    sectores = ["Todos"] + sorted(df_screen["Sector"].dropna().unique().tolist())
    sector_sel = col1.selectbox("Sector", sectores)

    # Filtro P/E
    pe_max = col2.slider("P/E máximo", 0, 200, 50)

    # Filtro dividendo mínimo
    div_min = col3.slider("Dividendo mínimo (%)", 0.0, 10.0, 0.0, step=0.5)

    # Filtro market cap mínimo
    mc_min = col4.slider("Market Cap mínimo (B$)", 0, 500, 0, step=10)

    # Aplicar filtros
    df_filtrado = df_screen.copy()
    if sector_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Sector"] == sector_sel]
    if pe_max > 0:
        df_filtrado = df_filtrado[(df_filtrado["P/E Ratio"] > 0) & (df_filtrado["P/E Ratio"] <= pe_max)]
    if div_min > 0:
        df_filtrado = df_filtrado[df_filtrado["Dividendo (%)"] >= div_min]
    if mc_min > 0:
        df_filtrado = df_filtrado[df_filtrado["Market Cap (B$)"] >= mc_min]

    st.divider()
    st.subheader(f"Resultados: {len(df_filtrado)} empresas")

    if df_filtrado.empty:
        st.info("Ninguna empresa cumple los filtros seleccionados. Prueba a ampliarlos.")
    else:
        # Colorear P/E y dividendo
        def color_pe(val):
            if val <= 0: return "color: #888"
            if val < 15: return "color: #1a7a1a; font-weight:bold"
            if val < 25: return "color: #7ED321"
            if val < 40: return "color: #F5A623"
            return "color: #E74C3C"

        def color_div(val):
            if val <= 0: return "color: #888"
            if val >= 3: return "color: #1a7a1a; font-weight:bold"
            if val >= 1: return "color: #7ED321"
            return "color: #F5A623"

        def color_roe(val):
            if val <= 0: return "color: #E74C3C"
            if val >= 15: return "color: #1a7a1a; font-weight:bold"
            if val >= 8: return "color: #7ED321"
            return "color: #F5A623"

        styled_screen = df_filtrado.style \
            .format({
                "Precio ($)": "${:.2f}",
                "Market Cap (B$)": "${:.1f}B",
                "P/E Ratio": "{:.1f}",
                "Dividendo (%)": "{:.2f}%",
                "ROE (%)": "{:.1f}%",
                "Margen neto (%)": "{:.1f}%",
                "Deuda/Equity": "{:.1f}",
                "52w Alto ($)": "${:.2f}",
                "52w Bajo ($)": "${:.2f}",
            }) \
            .map(color_pe, subset=["P/E Ratio"]) \
            .map(color_div, subset=["Dividendo (%)"]) \
            .map(color_roe, subset=["ROE (%)"])

        st.dataframe(styled_screen, use_container_width=True, hide_index=True)

        # Gráfica de distribución por sector
        st.subheader("Distribución por sector")
        sector_count = df_filtrado["Sector"].value_counts()
        fig_sector = go.Figure(go.Bar(
            x=sector_count.index,
            y=sector_count.values,
            marker_color="#4A90D9",
            text=sector_count.values,
            textposition="outside"
        ))
        fig_sector.update_layout(
            height=320,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(tickangle=-30),
            yaxis=dict(title="Nº empresas")
        )
        st.plotly_chart(fig_sector, use_container_width=True)

        # Scatter P/E vs Dividendo
        st.subheader("P/E vs Dividendo")
        df_scatter = df_filtrado[(df_filtrado["P/E Ratio"] > 0) & (df_filtrado["Dividendo (%)"] >= 0)].copy()
        if not df_scatter.empty:
            fig_scatter = go.Figure(go.Scatter(
                x=df_scatter["P/E Ratio"],
                y=df_scatter["Dividendo (%)"],
                mode="markers+text",
                text=df_scatter["Ticker"],
                textposition="top center",
                marker=dict(
                    size=df_scatter["Market Cap (B$)"].clip(5, 100) / 5,
                    color=df_scatter["ROE (%)"],
                    colorscale="RdYlGn",
                    showscale=True,
                    colorbar=dict(title="ROE %")
                ),
                hovertemplate="<b>%{text}</b><br>P/E: %{x:.1f}<br>Dividendo: %{y:.2f}%<extra></extra>"
            ))
            fig_scatter.update_layout(
                height=450,
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis=dict(title="P/E Ratio"),
                yaxis=dict(title="Dividendo (%)"),
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
            st.caption("Tamaño del punto = Market Cap · Color = ROE (verde = mejor)")

        # Botón para analizar empresa seleccionada
        st.divider()
        st.subheader("Ir al análisis detallado")
        empresa_sel = st.selectbox("Selecciona una empresa de los resultados",
            [f"{row['Ticker']} — {row['Empresa']}" for _, row in df_filtrado.iterrows()])
        if st.button("Analizar esta empresa →"):
            ticker_directo = empresa_sel.split(" — ")[0]
            st.session_state["ticker_directo"] = ticker_directo
            st.info(f"Ve a 'Análisis de acciones' y busca **{ticker_directo}** para ver el análisis completo.")
