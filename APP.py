
import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# CONFIGURAÇÃO DO DASHBOARD

st.set_page_config(
    page_title="Estação Meteorológica Inteligente",
    page_icon="🌦️",
    layout="wide",
)

# Atualização automática da tela a cada 10 segundos
st_autorefresh(
    interval=10_000,
    limit=None,
    key="atualizacao_automatica",
)

# Endereço da API
try:
    API_URL = st.secrets["API_URL"]
except Exception:
    API_URL = os.getenv(
        "API_URL",
        "http://127.0.0.1:8000/publico/medicoes",
    )

# Localização aproximada da estação
LOCAL_ESTACAO = "Água Branca, São Paulo - SP"
LAT_ESTACAO = -23.512
LON_ESTACAO = -46.702

st.title("🌦️ Estação Meteorológica Inteligente")
st.caption(
    f"Monitoramento ambiental urbano | {LOCAL_ESTACAO}"
)
st.caption("🔄 O painel atualiza automaticamente a cada 10 segundos.")


# BUSCAR MEDIÇÕES NA API

@st.cache_data(ttl=5, show_spinner=False)
def buscar_medicoes(url):
    resposta = requests.get(url, timeout=10)
    resposta.raise_for_status()

    dados = resposta.json()

    if isinstance(dados, dict):
        registros = dados.get("medicoes", [])
    elif isinstance(dados, list):
        registros = dados
    else:
        registros = []

    return pd.DataFrame(registros)


# CONFIGURAÇÃO DOS ALERTAS

st.sidebar.header("⚙️ Configurações dos alertas")

limite_temperatura = st.sidebar.number_input(
    "Temperatura elevada (°C)",
    min_value=0.0,
    max_value=80.0,
    value=35.0,
    step=1.0,
)

limite_umidade = st.sidebar.number_input(
    "Umidade baixa (%)",
    min_value=0.0,
    max_value=100.0,
    value=30.0,
    step=5.0,
)

limite_mq2 = st.sidebar.number_input(
    "Limite do MQ-2 (ADC)",
    min_value=0,
    max_value=4095,
    value=2500,
    step=100,
)

tempo_desatualizado = st.sidebar.number_input(
    "Dados desatualizados após (minutos)",
    min_value=1,
    max_value=1440,
    value=5,
    step=1,
)

st.sidebar.caption(
    "Os limites são configuráveis e servem para demonstração. "
    "A leitura ADC do MQ-2 não é uma concentração certificada de gás."
)

if st.sidebar.button("🔄 Atualizar dados agora"):
    buscar_medicoes.clear()
    st.rerun()

# CARREGAR OS DADOS

try:
    df = buscar_medicoes(API_URL)

except requests.RequestException as erro:
    st.error("🚨 Não foi possível acessar a API.")
    st.write(
        "Verifique se a FastAPI está funcionando e se o endereço "
        "configurado em API_URL está correto."
    )
    st.caption(f"Detalhe técnico: {erro}")
    st.stop()

except Exception as erro:
    st.error("Não foi possível processar os dados recebidos.")
    st.caption(f"Detalhe técnico: {erro}")
    st.stop()

if df.empty:
    st.warning(
        "A API respondeu, mas ainda não existem medições disponíveis."
    )
    st.stop()


# TRATAMENTO DOS DADOS

colunas_numericas = [
    "Temperatura",
    "Umidade",
    "Pressao_hPa",
    "Luminosidade",
    "MQ2_ADC",
    "Chuva_mm",
]

for coluna in colunas_numericas:
    if coluna in df.columns:
        df[coluna] = pd.to_numeric(
            df[coluna],
            errors="coerce",
        )

if "DataHora" in df.columns:
    df["DataHora"] = pd.to_datetime(
        df["DataHora"],
        errors="coerce",
        utc=True,
    )

    df = df.dropna(subset=["DataHora"])
    df = df.sort_values("DataHora").reset_index(drop=True)

if df.empty:
    st.warning("Não existem medições com data e hora válidas.")
    st.stop()

ultima = df.iloc[-1]


# STATUS DA ESTAÇÃO

st.subheader("📡 Status da estação")

idade_minutos = None

if "DataHora" in df.columns and pd.notna(ultima["DataHora"]):
    agora_utc = pd.Timestamp.now(tz="UTC")

    idade_minutos = (
        agora_utc - ultima["DataHora"]
    ).total_seconds() / 60

    idade_minutos = max(0, idade_minutos)

    data_local = ultima["DataHora"].tz_convert(
        "America/Sao_Paulo"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Última medição",
        data_local.strftime("%d/%m/%Y %H:%M:%S"),
    )

    c2.metric(
        "Tempo desde a medição",
        f"{idade_minutos:.1f} min",
    )

    if idade_minutos > tempo_desatualizado:
        c3.error("⚠️ Dados desatualizados")
    else:
        c3.success("✅ Dados recentes")

else:
    st.warning(
        "Não foi possível identificar a data da última medição."
    )


# ALERTAS AUTOMÁTICOS

st.subheader("🚨 Alertas ambientais")

alertas = []

if (
    idade_minutos is not None
    and idade_minutos > tempo_desatualizado
):
    alertas.append(
        f"Dados desatualizados: última medição há "
        f"{idade_minutos:.1f} minutos."
    )

if (
    "Temperatura" in df.columns
    and pd.notna(ultima.get("Temperatura"))
):
    temperatura = float(ultima["Temperatura"])

    if temperatura > limite_temperatura:
        alertas.append(
            f"Temperatura elevada: {temperatura:.1f} °C. "
            f"Limite: {limite_temperatura:.1f} °C."
        )

if (
    "Umidade" in df.columns
    and pd.notna(ultima.get("Umidade"))
):
    umidade = float(ultima["Umidade"])

    if umidade < limite_umidade:
        alertas.append(
            f"Umidade baixa: {umidade:.1f}%. "
            f"Limite: {limite_umidade:.1f}%."
        )

if (
    "MQ2_ADC" in df.columns
    and pd.notna(ultima.get("MQ2_ADC"))
):
    mq2 = float(ultima["MQ2_ADC"])

    if mq2 > limite_mq2:
        alertas.append(
            f"Leitura elevada do MQ-2: {mq2:.0f} ADC. "
            f"Limite: {limite_mq2}."
        )

if alertas:
    for alerta in alertas:
        st.error(f"🚨 {alerta}")
else:
    st.success("✅ Nenhum alerta configurado foi acionado.")

st.caption(
    "Os alertas são baseados na última medição recebida. "
    "Não substituem equipamentos certificados de segurança."
)


# INDICADORES PRINCIPAIS

st.subheader("📊 Indicadores atuais")


def valor_formatado(coluna, formato, unidade=""):
    if (
        coluna not in df.columns
        or pd.isna(ultima.get(coluna))
    ):
        return "Sem dados"

    return f"{float(ultima[coluna]):{formato}}{unidade}"


m1, m2, m3 = st.columns(3)
m4, m5, m6 = st.columns(3)

m1.metric(
    "🌡️ Temperatura",
    valor_formatado("Temperatura", ".1f", " °C"),
)

m2.metric(
    "💧 Umidade",
    valor_formatado("Umidade", ".1f", "%"),
)

m3.metric(
    "🌬️ Pressão atmosférica",
    valor_formatado("Pressao_hPa", ".2f", " hPa"),
)

m4.metric(
    "🌧️ Chuva acumulada",
    valor_formatado("Chuva_mm", ".2f", " mm"),
)

m5.metric(
    "☀️ Luminosidade (ADC)",
    valor_formatado("Luminosidade", ".0f"),
)

m6.metric(
    "🫧 Leitura do MQ-2 (ADC)",
    valor_formatado("MQ2_ADC", ".0f"),
)


# GRÁFICOS INTERATIVOS

st.subheader("📈 Histórico das medições")

graficos = [
    ("Temperatura", "Temperatura", "°C"),
    ("Umidade", "Umidade", "%"),
    ("Pressao_hPa", "Pressão atmosférica", "hPa"),
    ("Luminosidade", "Luminosidade", "ADC"),
    ("MQ2_ADC", "Leitura do MQ-2", "ADC"),
    ("Chuva_mm", "Chuva acumulada", "mm"),
]

if "DataHora" in df.columns:
    opcoes = {
        nome: coluna
        for coluna, nome, unidade in graficos
        if coluna in df.columns
    }

    if opcoes:
        selecao = st.selectbox(
            "Escolha o indicador",
            list(opcoes.keys()),
        )

        coluna = opcoes[selecao]

        unidade = next(
            item[2]
            for item in graficos
            if item[0] == coluna
        )

        grafico_df = df[["DataHora", coluna]].dropna()

        if not grafico_df.empty:
            fig = px.line(
                grafico_df,
                x="DataHora",
                y=coluna,
                markers=True,
                title=f"{selecao} ao longo do tempo",
                labels={
                    "DataHora": "Data e hora",
                    coluna: f"{selecao} ({unidade})",
                },
            )

            fig.update_layout(
                hovermode="x unified",
                margin=dict(l=20, r=20, t=60, b=20),
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )
        else:
            st.info("Não existem valores válidos para esse gráfico.")
    else:
        st.info("Nenhuma coluna compatível com os gráficos foi encontrada.")
else:
    st.info("Os gráficos precisam da coluna DataHora.")


# MAPA E GEOLOCALIZAÇÃO

st.subheader("📍 Localização da estação")

st.write(f"Local informado: **{LOCAL_ESTACAO}**")

mapa = pd.DataFrame({
    "latitude": [LAT_ESTACAO],
    "longitude": [LON_ESTACAO],
})

st.map(
    mapa,
    latitude="latitude",
    longitude="longitude",
    size=200,
    color="#e63946",
    zoom=13,
)

st.link_button(
    "Abrir localização no Google Maps",
    f"https://www.google.com/maps?q={LAT_ESTACAO},{LON_ESTACAO}",
)


# HISTÓRICO DAS MEDIÇÕES

st.subheader("📋 Histórico das medições")

quantidade = st.selectbox(
    "Quantidade de registros",
    [10, 25, 50, 100, "Todos"],
    index=1,
)

historico = df.copy()

if quantidade != "Todos":
    historico = historico.tail(int(quantidade))

if "DataHora" in historico.columns:
    historico["DataHora"] = (
        historico["DataHora"]
        .dt.tz_convert("America/Sao_Paulo")
        .dt.strftime("%d/%m/%Y %H:%M:%S")
    )

st.dataframe(
    historico.sort_index(ascending=False),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Painel demonstrativo da estação meteorológica inteligente. "
    "Os dados são consultados novamente conforme o intervalo "
    "de atualização configurado."
)
