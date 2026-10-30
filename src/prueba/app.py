"""Visor de archivos CSV con Streamlit.

Ejecutar con: uv run prueba  (o uv run streamlit run src/prueba/app.py)
"""

import io

import pandas as pd
import plotly.express as px
import streamlit as st

SEPARADORES = {"Auto": None, "Coma (,)": ",", "Punto y coma (;)": ";", "Tabulador": "\t"}
MAX_CATEGORIAS = 50
SIN_COLOR = "(ninguno)"


@st.cache_data
def load_csv(data: bytes, sep: str | None, encoding: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(data), sep=sep, engine="python", encoding=encoding)


def filtrar(df: pd.DataFrame) -> pd.DataFrame:
    columnas = st.multiselect("Columnas a filtrar", df.columns.tolist())
    for col in columnas:
        serie = df[col]
        if pd.api.types.is_numeric_dtype(serie) and serie.notna().any():
            lo, hi = float(serie.min()), float(serie.max())
            if lo == hi:
                continue
            desde, hasta = st.slider(col, lo, hi, (lo, hi))
            df = df[serie.between(desde, hasta)]
        elif serie.nunique() <= MAX_CATEGORIAS:
            opciones = serie.dropna().unique().tolist()
            elegidos = st.multiselect(col, opciones, default=opciones)
            df = df[serie.isin(elegidos)]
        else:
            texto = st.text_input(f"{col} contiene")
            if texto:
                df = df[serie.astype(str).str.contains(texto, case=False, na=False)]
    return df


def tab_datos(df: pd.DataFrame) -> pd.DataFrame:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas", f"{len(df):,}")
    c2.metric("Columnas", df.shape[1])
    c3.metric("Valores nulos", f"{int(df.isna().sum().sum()):,}")
    c4.metric("Filas duplicadas", f"{int(df.duplicated().sum()):,}")

    visibles = st.multiselect("Columnas visibles", df.columns.tolist(), default=df.columns.tolist())
    filtrado = filtrar(df)
    st.caption(f"{len(filtrado):,} de {len(df):,} filas")
    st.dataframe(filtrado[visibles], width="stretch")
    st.download_button(
        "Descargar CSV filtrado",
        filtrado[visibles].to_csv(index=False).encode("utf-8"),
        file_name="filtrado.csv",
        mime="text/csv",
    )
    return filtrado


def tab_resumen(df: pd.DataFrame) -> None:
    st.subheader("Columnas")
    info = pd.DataFrame(
        {
            "tipo": df.dtypes.astype(str),
            "no nulos": df.notna().sum(),
            "% nulos": (df.isna().mean() * 100).round(2),
            "valores únicos": df.nunique(),
        }
    )
    st.dataframe(info, width="stretch")
    st.subheader("Estadísticas descriptivas")
    st.dataframe(df.describe(include="all").T, width="stretch")


def tab_graficos(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("No hay filas para graficar.")
        return
    columnas = df.columns.tolist()
    numericas = df.select_dtypes("number").columns.tolist()
    tipo = st.selectbox(
        "Tipo de gráfico",
        ["Histograma", "Barras de conteo", "Dispersión", "Líneas", "Box plot", "Matriz de correlación"],
    )

    def color() -> str | None:
        c = st.selectbox("Color", [SIN_COLOR, *columnas])
        return None if c == SIN_COLOR else c

    fig = None
    if tipo == "Histograma":
        x = st.selectbox("Columna", columnas)
        bins = st.slider("Bins", 5, 200, 30)
        fig = px.histogram(df, x=x, color=color(), nbins=bins)
    elif tipo == "Barras de conteo":
        x = st.selectbox("Columna", columnas)
        top = st.slider("Mostrar los N más frecuentes", 5, 100, 20)
        conteo = df[x].value_counts().head(top).rename_axis(x).reset_index(name="cantidad")
        fig = px.bar(conteo, x=x, y="cantidad")
    elif tipo in ("Dispersión", "Líneas"):
        x = st.selectbox("Eje X", columnas)
        y = st.selectbox("Eje Y", numericas or columnas)
        if tipo == "Dispersión":
            fig = px.scatter(df, x=x, y=y, color=color())
        else:
            fig = px.line(df.sort_values(x), x=x, y=y, color=color())
    elif tipo == "Box plot":
        if not numericas:
            st.warning("No hay columnas numéricas.")
            return
        y = st.selectbox("Columna numérica", numericas)
        x = st.selectbox("Agrupar por", [SIN_COLOR, *columnas])
        fig = px.box(df, x=None if x == SIN_COLOR else x, y=y)
    elif tipo == "Matriz de correlación":
        if len(numericas) < 2:
            st.warning("Se necesitan al menos dos columnas numéricas.")
            return
        corr = df[numericas].corr()
        fig = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1)

    st.plotly_chart(fig, width="stretch")


def main() -> None:
    st.set_page_config(page_title="Visor CSV", layout="wide")
    st.title("Visor de archivos CSV")

    with st.sidebar:
        archivos = st.file_uploader("Subir archivos CSV", type="csv", accept_multiple_files=True)
        sep = SEPARADORES[st.selectbox("Separador", list(SEPARADORES))]
        encoding = st.selectbox("Codificación", ["utf-8", "latin-1"])

    if not archivos:
        st.info("Subí uno o más archivos CSV desde la barra lateral para empezar.")
        return

    nombres = [a.name for a in archivos]
    elegido = st.sidebar.selectbox("Archivo a visualizar", nombres)
    archivo = archivos[nombres.index(elegido)]

    try:
        df = load_csv(archivo.getvalue(), sep, encoding)
    except Exception as e:
        st.error(f"No se pudo leer {archivo.name}: {e}")
        return

    st.subheader(archivo.name)
    datos, resumen, graficos = st.tabs(["Datos", "Resumen", "Gráficos"])
    with datos:
        filtrado = tab_datos(df)
    with resumen:
        tab_resumen(filtrado)
    with graficos:
        tab_graficos(filtrado)


main()
