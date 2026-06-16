"""Visual theme helpers for the Streamlit presentation layer."""

from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import streamlit as st


KAPPO_BLUE = "#0b86d5"
KAPPO_NAVY = "#062657"
KAPPO_LIGHT_BLUE = "#e8f7fc"


def aplicar_tema_kappo() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --kappo-blue: {KAPPO_BLUE};
            --kappo-navy: {KAPPO_NAVY};
            --kappo-light-blue: {KAPPO_LIGHT_BLUE};
            --kappo-muted: #6f7f91;
            --kappo-border: #dce6ef;
            --kappo-surface: #ffffff;
            --kappo-background: #f2f8fc;
        }}

        .stApp {{
            background: var(--kappo-background);
        }}

        .block-container {{
            max-width: 1420px;
            padding-top: 1.1rem;
            padding-bottom: 4rem;
        }}

        [data-testid="stSidebar"] {{
            min-width: 286px;
            background:
                linear-gradient(180deg, #031a40 0%, var(--kappo-navy) 52%, #0a326c 100%);
            border-right: 0;
            box-shadow: 8px 0 28px rgba(2, 24, 58, 0.12);
        }}

        [data-testid="stSidebar"] > div:first-child {{
            padding-top: 1.35rem;
        }}

        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {{
            color: #ffffff;
        }}

        [data-testid="stSidebar"] h2 {{
            margin-top: 0.6rem;
            font-size: 1.05rem;
            letter-spacing: -0.02em;
        }}

        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{
            background: rgba(255, 255, 255, 0.97);
            border: 1px solid rgba(255, 255, 255, 0.32);
            border-radius: 10px;
        }}

        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] p,
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] span,
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small {{
            color: #41536a;
        }}

        [data-testid="stSidebar"] [data-testid="stImage"] {{
            margin: 0 auto 0.8rem;
        }}

        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: var(--kappo-surface);
            border: 1px solid var(--kappo-border);
            border-radius: 13px;
            box-shadow: 0 6px 18px rgba(16, 54, 93, 0.055);
        }}

        [data-testid="stVerticalBlockBorderWrapper"] h2 {{
            color: var(--kappo-navy);
            font-size: 1.45rem;
            letter-spacing: -0.025em;
        }}

        [data-testid="stMetric"] {{
            min-height: 112px;
            padding: 1rem 1.05rem 0.9rem;
            background: #ffffff;
            border: 1px solid var(--kappo-border);
            border-top: 4px solid var(--kappo-blue);
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(16, 54, 93, 0.045);
        }}

        [data-testid="stMetricLabel"] {{
            color: var(--kappo-muted);
            font-size: 0.77rem;
            font-weight: 750;
            letter-spacing: 0.025em;
            text-transform: uppercase;
        }}

        [data-testid="stMetricValue"] {{
            color: #031c43;
            letter-spacing: -0.035em;
        }}

        [data-testid="stDataFrame"] {{
            border: 1px solid var(--kappo-border);
            border-radius: 10px;
            overflow: hidden;
        }}

        [data-testid="stExpander"] {{
            border-color: var(--kappo-border);
            border-radius: 10px;
            background: #ffffff;
        }}

        .stButton > button[kind="primary"] {{
            border: 0;
            border-radius: 8px;
            background: var(--kappo-blue);
            box-shadow: 0 5px 14px rgba(11, 134, 213, 0.22);
            font-weight: 700;
        }}

        .stButton > button[kind="primary"]:hover {{
            background: #0875bd;
        }}

        .kappo-hero {{
            display: grid;
            grid-template-columns: minmax(210px, 0.72fr) minmax(0, 2.8fr);
            gap: 0;
            margin-bottom: 1.25rem;
            border: 1px solid var(--kappo-border);
            border-radius: 13px;
            box-shadow: 0 8px 22px rgba(16, 54, 93, 0.08);
            overflow: hidden;
        }}

        .kappo-hero-logo {{
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 170px;
            padding: 1.35rem;
            background: #ffffff;
        }}

        .kappo-hero-logo img {{
            display: block;
            width: min(100%, 250px);
            height: auto;
        }}

        .kappo-hero-copy {{
            position: relative;
            overflow: hidden;
            min-height: 170px;
            padding: 1.65rem 1.9rem;
            color: #ffffff;
            background:
                radial-gradient(circle at 96% 10%, rgba(11, 134, 213, 0.25), transparent 32%),
                linear-gradient(125deg, #062657 0%, #0b3977 100%);
        }}

        .kappo-hero h1 {{
            max-width: 980px;
            margin: 0;
            color: #ffffff;
            font-size: clamp(1.65rem, 2.6vw, 2.35rem);
            line-height: 1.08;
            letter-spacing: -0.035em;
        }}

        .kappo-hero-subtitle {{
            margin: 0.8rem 0 0;
            color: #d8eafb;
            font-size: 0.96rem;
        }}

        .kappo-context {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1rem;
        }}

        .kappo-chip {{
            padding: 0.38rem 0.7rem;
            color: #f8fafc;
            background: rgba(255, 255, 255, 0.09);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 999px;
            font-size: 0.82rem;
        }}

        div[data-testid="stAlert"] {{
            border-radius: 9px;
            border-width: 0 0 0 4px;
        }}

        @media (max-width: 800px) {{
            .kappo-hero {{
                grid-template-columns: 1fr;
            }}

            .kappo-hero-logo {{
                min-height: 112px;
            }}

            .kappo-hero-copy {{
                min-height: auto;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def renderizar_hero(
    *,
    logo_path: str | Path,
    empresa: str | None = None,
    periodo: str | None = None,
    formato: str | None = None,
) -> None:
    logo_bytes = Path(logo_path).read_bytes()
    logo_base64 = base64.b64encode(logo_bytes).decode("ascii")
    context_items = []
    if empresa:
        context_items.append(f"Empresa: {escape(str(empresa))}")
    if periodo:
        context_items.append(f"Período: {escape(str(periodo))}")
    if formato:
        context_items.append(f"Formato EERR: {escape(str(formato).title())}")

    context_html = "".join(
        f'<span class="kappo-chip">{item}</span>' for item in context_items
    )
    context_block = (
        f'<div class="kappo-context">{context_html}</div>' if context_html else ""
    )

    st.markdown(
        f"""
        <section class="kappo-hero">
            <div class="kappo-hero-logo">
                <img
                    src="data:image/png;base64,{logo_base64}"
                    alt="Kappo Consultoría y Gestión a Empresas"
                />
            </div>
            <div class="kappo-hero-copy">
                <h1>Punto de Equilibrio y Rentabilidad Comercial</h1>
                <p class="kappo-hero-subtitle">
                    Análisis global EERR · Rentabilidad comercial ·
                    Conciliación controller · Sensibilidad
                </p>
                {context_block}
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
