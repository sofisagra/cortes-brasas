"""Cortes & Brasas — experiencia de compra inteligente (DEMO SIN IA).

Ejecutar: streamlit run app.py
Datos: productos.json en esta MISMA carpeta.
Futuro: integrar OpenAI en analizar_documentos_con_ia(), sin cambiar el motor.
"""
from __future__ import annotations

import base64
import csv
import html
import io
import json
from pathlib import Path
import time
from urllib.parse import quote, urlparse

import streamlit as st
from motor import (
    CATEGORIAS, CatalogoError, capacidad_comidas, catalogo_disponible,
    construir_propuestas, extras_menu, generar_menu, gramos_por_comida,
    leer_catalogo, sumar_carrito, total_comidas, totales_carrito,
    validar_compra,
)

ROOT = Path(__file__).resolve().parent
CATALOGO = ROOT / "productos.json"
LOGO = ROOT / "assets" / "logo_wordmark.png"
LOGO_COMPLETO = ROOT / "assets" / "logo_original.png"
ARCHIVOS_PERMITIDOS = ("pdf", "png", "jpg", "jpeg", "webp")
ICONOS = {"Res": "🥩", "Pollo": "🍗", "Cerdo": "🍖", "Pescado": "🐟", "Pavo": "🍽️"}
FONDOS = {
    "Res": "meat-res", "Pollo": "meat-pollo", "Cerdo": "meat-cerdo",
    "Pescado": "meat-pescado", "Pavo": "meat-pavo",
}

st.set_page_config(
    page_title="Cortes & Brasas | Compra inteligente",
    page_icon="🥩", layout="wide", initial_sidebar_state="expanded",
)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def crc(value: float) -> str:
    return "₡" + f"{value:,.0f}".replace(",", ".")


def kg_text(value: float) -> str:
    return f"{value:.2f}".replace(".", ",") + " kg"


def logo_b64(path: Path) -> str:
    if path.is_file():
        return base64.b64encode(path.read_bytes()).decode("ascii")
    return ""


def foto_producto(producto: dict) -> str | None:
    """Permite https://... o imágenes existentes dentro de assets/.

    Nunca acepta rutas absolutas ni escapes fuera de assets/.
    """
    value = str(producto.get("imagen", "") or "").strip()
    if not value:
        return None
    if value.startswith("https://") and urlparse(value).netloc:
        return value
    if not value.startswith("assets/"):
        return None
    target = (ROOT / value).resolve()
    assets = (ROOT / "assets").resolve()
    if not target.is_relative_to(assets) or not target.is_file():
        return None
    if target.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"} or target.stat().st_size > 3_000_000:
        return None
    types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    return "data:" + types[target.suffix.lower()] + ";base64," + base64.b64encode(target.read_bytes()).decode()


def estilo() -> None:
    st.markdown('''<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700;800&display=swap');
    :root{--cream:#f7f5f1;--paper:#fffefa;--ink:#241f1c;--muted:#746b62;--stroke:#e8e0d8;--terracotta:#8d5e47;}
    html,body,[data-testid="stAppViewContainer"], [data-testid="stSidebar"]{font-family:'DM Sans', sans-serif;}
    [data-testid="stAppViewContainer"]{background:var(--cream);color:var(--ink)}
    [data-testid="stSidebar"]{background:#efeae3;border-right:1px solid var(--stroke)}
    .block-container{max-width:1310px;padding-top:1.35rem;padding-bottom:5rem}
    h1,h2,h3{font-family:'Playfair Display',Georgia,serif!important;letter-spacing:-.03em;color:var(--ink)}
    h2{font-size:2rem!important}h3{font-size:1.3rem!important}
    .hero{background:linear-gradient(120deg,#f1ece5 0%,#fdfaf6 65%,#eee5da 100%);border:1px solid #e3d9ce;
          border-radius:22px;padding:2.2rem 2.6rem;min-height:290px;display:flex;align-items:center;gap:30px;justify-content:space-between;margin-bottom:2rem}
    .hero-text{max-width:720px}.hero h1{font-family:'Playfair Display',Georgia,serif;font-size:clamp(2.4rem,4.2vw,4.5rem);line-height:1.03;margin:.38rem 0 1rem}
    .hero p{max-width:610px;color:#635b54;font-size:1rem;line-height:1.7}
    .hero-logo{max-width:290px;width:37%;padding:1rem;display:flex;align-items:center;justify-content:center}
    .hero-logo img{max-width:100%;width:270px;mix-blend-mode:multiply}
    .eyebrow{font-size:.7rem;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:#976b55}
    .pill{display:inline-block;background:#e8dcd0;color:#5b4438;padding:7px 13px;border-radius:100px;font-size:.75rem;font-weight:700;margin:0 7px 5px 0}
    .section-intro{padding-top:8px;padding-bottom:9px}.section-intro p{color:var(--muted);max-width:740px}
    .section-n{font-size:.73rem;font-weight:800;letter-spacing:.18em;color:#9b6b51;text-transform:uppercase}
    .design-card{background:#fffdf9;border:1px solid var(--stroke);border-radius:18px;padding:20px 22px}
    .plan-head{padding:.4rem 0 .6rem}.plan-head h3{margin:.3rem 0 .4rem;font-size:1.75rem!important}
    .plan-sub{color:#736a62;font-size:.89rem;line-height:1.6;min-height:37px}
    .product-card{display:flex;align-items:center;gap:14px;background:#fffefa;border:1px solid #e5ddd4;border-radius:15px;padding:11px;margin:7px 0 4px;min-height:125px}
    .food-media{width:112px;height:108px;flex:0 0 112px;border-radius:11px;display:flex;align-items:center;justify-content:center;
          font-size:3.8rem;position:relative;overflow:hidden;text-shadow:0 5px 18px #0002}
    .food-media img{width:100%;height:100%;object-fit:cover;border-radius:11px;display:block}
    .food-media:before{content:'';position:absolute;border-radius:100%;width:92px;height:92px;background:#ffffff24;right:-23px;top:-35px}
    .meat-res{background:linear-gradient(130deg,#caaea0,#9c6a62)}
    .meat-pollo{background:linear-gradient(130deg,#eadbbd,#d0af79)}
    .meat-cerdo{background:linear-gradient(130deg,#d9b8a7,#b98470)}
    .meat-pescado{background:linear-gradient(130deg,#b8d2d3,#81adb2)}
    .meat-pavo{background:linear-gradient(130deg,#d7c5b3,#b49e85)}
    .product-copy{flex:1;min-width:0}.product-copy .family{font-size:.65rem;font-weight:800;letter-spacing:.15em;color:#976b55;text-transform:uppercase}
    .product-copy strong{display:block;font-size:1rem;line-height:1.36;margin:.2rem 0;font-weight:700;color:#27221e}
    .product-copy .desc{color:#786e66;font-size:.77rem;line-height:1.5;display:block}
    .product-copy .price{display:block;margin-top:4px;color:#554235;font-weight:800;font-size:.88rem}
    .mix-label{font-size:.70rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:#8b7362;margin:17px 0 9px}
    .mix-row{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:.77rem;color:#6e6259}
    .mix-name{width:126px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:0 0 126px}
    .mix-bar{height:8px;background:#eae3da;border-radius:12px;flex:1;overflow:hidden}
    .mix-fill{height:100%;background:linear-gradient(90deg,#ab8167,#604839);border-radius:12px}
    .mix-pct{width:37px;text-align:right;font-weight:700}
    .stat-strip{background:#f0ebe4;border:1px solid #dfd6cc;padding:15px;border-radius:13px;margin:14px 0 10px}
    .stat-strip b{font-family:'Playfair Display',Georgia,serif;font-size:1.6rem;color:#302620}
    .stat-strip small{display:block;color:#776b62;margin-top:3px}
    .step-line{border-top:1px solid #e5ded5;margin:2.2rem 0}
    .hint{padding:12px 16px;border-left:3px solid #a4775e;background:#f1e9e0;border-radius:8px;color:#60554c;font-size:.84rem}
    .menu-meal{border:1px solid #e6ddd4;background:#fffefa;padding:14px 16px;border-radius:12px;margin-bottom:9px}
    .menu-meal .meal{font-size:.69rem;text-transform:uppercase;letter-spacing:.15em;color:#9e735f;font-weight:800}
    .menu-meal strong{display:block;color:#2d231f;margin-top:4px}.menu-meal small{display:block;color:#756b62;margin-top:3px}
    .tag{display:inline-block;background:#f2ece4;border:1px solid #e2d8cc;border-radius:100px;font-size:.7rem;color:#765847;padding:4px 9px;margin:2px}
    [data-testid="stForm"]{background:#fffdf9;border:1px solid #e8e0d8;border-radius:17px;padding:20px 22px}
    [data-testid="stMetric"]{background:#fffdf9;padding:14px 18px;border:1px solid #e7ded5;border-radius:14px}
    [data-testid="stMetricValue"]{font-family:'Playfair Display',Georgia,serif}
    div.stButton>button[kind="primary"],div.stFormSubmitButton>button[kind="primary"]{background:#2b2420!important;border-color:#2b2420!important;color:white!important}
    div.stButton>button[kind="primary"]:hover,div.stFormSubmitButton>button[kind="primary"]:hover{background:#674b3b!important;border-color:#674b3b!important}
    div.stButton>button,div.stFormSubmitButton>button,div.stDownloadButton>button{border-radius:9px;min-height:42px;font-weight:650}
    .footer{color:#8c8178;text-align:center;font-size:.76rem;letter-spacing:.06em;padding-top:1rem}
    @media(max-width:750px){.hero{display:block;padding:1.4rem}.hero-logo{width:78%;margin:10px auto}.food-media{width:85px;height:90px;flex-basis:85px;font-size:2.8rem}.product-card{gap:10px}.block-container{padding-left:1rem;padding-right:1rem}}
    </style>''', unsafe_allow_html=True)


def inicio() -> None:
    logo = logo_b64(LOGO)
    imagen = f'<img src="data:image/png;base64,{logo}" alt="Logo de Cortes & Brasas">' if logo else '<h3>Cortes & Brasas</h3>'
    st.markdown(f'''<div class="hero"><div class="hero-text"><span class="eyebrow">Cortes & Brasas · Boutique de carnes</span>
    <h1>Tu compra perfecta.<br>Mucho más que carne.</h1>
    <p>Elegí tus objetivos, compará <strong>dos propuestas</strong> y descubrí cómo transformar una sola compra en comidas variadas para tu hogar.</p>
    <span class="pill">Compra a tu medida</span><span class="pill">Recetas sin rutina</span><span class="pill">Opciones intercambiables</span>
    </div><div class="hero-logo">{imagen}</div></div>''', unsafe_allow_html=True)


def seccion(n: str, titulo: str, subtitulo: str) -> None:
    st.markdown(f'<div class="section-intro"><span class="section-n">{esc(n)}</span><h2>{esc(titulo)}</h2><p>{esc(subtitulo)}</p></div>', unsafe_allow_html=True)


def tarjeta_producto(p: dict) -> None:
    img = foto_producto(p)
    art = f'<img src="{esc(img)}" alt="{esc(p["producto"])}">' if img else ICONOS.get(p["categoria"], "🥩")
    etiquetas = " ".join(f'<span class="tag">{esc(t)}</span>' for t in p.get("etiquetas", [])[:2])
    st.markdown(f'''<div class="product-card"><div class="food-media {FONDOS.get(p["categoria"], "meat-res")}">{art}</div>
    <div class="product-copy"><span class="family">{esc(p["categoria"])}</span><strong>{esc(p["producto"])}</strong>
    <span class="desc">{esc(p.get("descripcion", ""))}</span><span class="price">{crc(float(p["precio_kg_crc"]))} / kg</span>{etiquetas}</div></div>''', unsafe_allow_html=True)


def simular_carga() -> None:
    """Barra animada SOLO visual. NO representa una llamada a un modelo de IA."""
    progress = st.progress(0, text="Iniciando tu experiencia…")
    etapas = [
        (0, "Organizando la información que ingresaste"),
        (21, "Consultando el catálogo local de productos"),
        (43, "Calculando las cantidades de compra"),
        (67, "Preparando dos combinaciones alternativas"),
        (86, "Seleccionando ideas de recetas"),
    ]
    for p in range(0, 101, 2):
        status = etapas[0][1]
        for lower, message in etapas:
            if p >= lower:
                status = message
        progress.progress(p, text=f"{status} · {p}%")
        time.sleep(0.035)
    progress.empty()


def archivo_info(uploads: list) -> list[str]:
    if len(uploads) > 3:
        raise ValueError("Podés adjuntar un máximo de 3 archivos.")
    names = []
    for up in uploads:
        if len(up.getvalue()) > 8 * 1024 * 1024:
            raise ValueError(f"{up.name} supera el límite de 8 MB.")
        if Path(up.name).suffix.lower().lstrip(".") not in ARCHIVOS_PERMITIDOS:
            raise ValueError(f"Formato no permitido: {up.name}.")
        names.append(Path(up.name).name)
    return names


# Punto previsto para la futura integración, sin utilizarlo en la demo.
def analizar_documentos_con_ia(perfil: dict, archivos: list) -> dict:
    """Futura conexión OpenAI: interpretar documentos SOLO con consentimiento.

    Una respuesta estructurada podrá sugerir preferencias; la compra seguirá
    calculándose y verificándose de forma determinista en motor.py.
    """
    raise NotImplementedError("La interpretación con IA está desactivada en esta versión.")


def panel_perfil(data: dict) -> None:
    seccion("01 · Tu perfil", "Contanos para quién compramos",
            "Una compra familiar, un menú semanal o una selección para tu entrenamiento. Vos controlás las cantidades.")
    with st.form("formulario_perfil", clear_on_submit=False):
        c1, c2, c3 = st.columns(3, gap="large")
        with c1:
            objetivo = st.selectbox("¿Cuál es tu objetivo?", [
                "Organizar las comidas de la semana",
                "Ganar masa muscular",
                "Mantener hábitos de alimentación",
                "Cocinar para toda la familia",
                "Variar nuestras recetas",
                "Seguir un plan del nutricionista",
            ])
            adultos = st.number_input("Adultos", 1, 12, 2, 1)
            ninos = st.number_input("Niños", 0, 12, 0, 1)
        with c2:
            dias = st.slider("¿Para cuántos días?", min_value=2, max_value=14, value=7)
            comidas = st.selectbox("Comidas con proteína al día", [1, 2, 3], index=1)
            porcion_adulto = st.number_input("Gramos crudos por adulto / comida", 80, 300, 160, step=10,
                help="Cantidad de compra editable. NO es una prescripción nutricional.")
            porcion_nino = st.number_input("Gramos crudos por niño / comida", 30, 180, 90, step=10,
                help="Estimación de compra editable, no indicación nutricional infantil.")
        with c3:
            categorias = st.multiselect("¿Qué proteínas te gustan?", list(CATEGORIAS),
                                       default=["Res", "Pollo", "Cerdo"])
            excluidas = st.multiselect("¿Cuáles querés excluir?", list(CATEGORIAS), default=[])
            presupuesto = st.number_input("Presupuesto de referencia (₡)", min_value=0, max_value=5_000_000,
                                          value=0, step=5_000, help="Opcional. 0 significa sin límite definido.")
        nota = st.text_area("Contanos tus gustos, objetivos o indicaciones generales (opcional)", height=98,
              placeholder="Ej.: me gusta la carne mechada, hago ejercicio, busco recetas rápidas y no quiero repetir almuerzos…")
        restricciones = st.text_input("Otras alergias o restricciones que debamos conocer",
              placeholder="Ej.: alergia a nueces, sin gluten… Verificá los ingredientes de las recetas.")
        uploads = st.file_uploader("InBody, foto o PDF del nutricionista (opcional)",
             type=list(ARCHIVOS_PERMITIDOS), accept_multiple_files=True,
             help="Esta demostración permite adjuntar archivos, pero NO los interpreta; usá los campos manuales para la recomendación.")
        st.caption("**Modo demostración:** los archivos adjuntos no se leen ni analizan. Si hay una indicación médica, ingresá manualmente lo necesario y confirmalo con tu profesional.")
        submitted = st.form_submit_button("Ver mis dos propuestas de compra", type="primary", use_container_width=True)
    if submitted:
        if not categorias or not set(categorias).difference(excluidas):
            st.error("Seleccioná al menos una categoría que no esté excluida.")
            return
        try:
            names = archivo_info(uploads or [])
            perfil = {
                "objetivo": objetivo, "adultos": int(adultos), "ninos": int(ninos),
                "dias": int(dias), "comidas_dia": int(comidas),
                "porcion_adulto_g": int(porcion_adulto), "porcion_nino_g": int(porcion_nino),
                "categorias": list(categorias), "excluidas": list(excluidas),
                "presupuesto": int(presupuesto), "nota": nota.strip(),
                "restricciones_texto": restricciones.strip(), "archivos": names,
            }
            propuestas = construir_propuestas(data, perfil)
        except (ValueError, CatalogoError) as e:
            st.error(str(e))
            return
        simular_carga()
        st.session_state.perfil = perfil
        st.session_state.propuestas = propuestas
        st.session_state.compra = None
        st.session_state.menu = None
        st.session_state.plan_aprobado = None
        st.session_state.version = st.session_state.get("version", 0) + 1
        st.success("¡Listo! Ya tenés dos propuestas, y podés cambiar todos los cortes.")
        if names:
            st.caption(f"Adjuntos recibidos (sin analizar): {', '.join(names)}")


def render_propuesta(op: dict, disponibles: list[dict], perfil: dict, data: dict) -> None:
    ident = op["id"]
    version = st.session_state.version
    by_sku = {p["sku"]: p for p in disponibles}
    opciones_sku = list(by_sku)
    st.markdown(f'''<div class="plan-head"><span class="eyebrow">Opción {esc(ident)}</span><h3>{esc(op["titulo"])}</h3>
    <div class="plan-sub">{esc(op["subtitulo"])}</div></div>''', unsafe_allow_html=True)
    filas = []
    for j, row in enumerate(op["filas"]):
        current = row["sku"] if row["sku"] in by_sku else opciones_sku[0]
        key_sku = f"selector_{version}_{ident}_{j}"
        selected_sku = st.selectbox("Cambiar corte", opciones_sku,
            index=opciones_sku.index(current), key=key_sku,
            format_func=lambda sku: f"{by_sku[sku]['producto']} · {crc(by_sku[sku]['precio_kg_crc'])}/kg")
        producto = by_sku[selected_sku]
        tarjeta_producto(producto)
        initial_kg = float(row["kg"])
        kg = st.number_input("Cantidad para este producto (kg)", min_value=0.25, max_value=80.0,
                             value=initial_kg, step=0.25, key=f"cantidad_{version}_{ident}_{j}")
        filas.append({"sku": selected_sku, "kg": float(kg)})
    cart = sumar_carrito(filas)
    kg_total, total = totales_carrito(cart, by_sku)
    req = total_comidas(perfil)
    capacity = capacidad_comidas(cart, perfil)
    st.markdown('<div class="mix-label">Composición de tu compra</div>', unsafe_allow_html=True)
    for sku, amount in cart.items():
        fraction = 100 * amount / kg_total if kg_total else 0
        label = by_sku[sku]['producto']
        st.markdown(f'<div class="mix-row"><span class="mix-name" title="{esc(label)}">{esc(label)}</span>'
            f'<div class="mix-bar"><div class="mix-fill" style="width:{fraction:.1f}%"></div></div>'
            f'<span class="mix-pct">{fraction:.0f}%</span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="stat-strip"><small>Tu selección estimada</small><b>{crc(total)}</b><small>{kg_text(kg_total)} · Cubre {min(capacity,req)}/{req} comidas familiares</small></div>',
                unsafe_allow_html=True)
    valid, reason = validar_compra(cart, perfil, disponibles)
    if not valid:
        st.warning(reason)
    presupuesto = perfil["presupuesto"]
    if presupuesto and total > presupuesto:
        st.caption(f"Supera tu presupuesto de referencia en {crc(total - presupuesto)}.")
    if st.button(f"Elegir opción {ident}", key=f"approve_{version}_{ident}",
                 type="primary" if ident == "A" else "secondary",
                 use_container_width=True, disabled=not valid):
        by_all = {p["sku"]: p for p in data["productos"]}
        st.session_state.compra = cart
        st.session_state.plan_aprobado = ident
        st.session_state.menu = generar_menu(cart, perfil, by_all)
        st.success(f"Elegiste la opción {ident}. Abajo está tu menú y tu lista de compra.")


def panel_opciones(data: dict) -> None:
    perfil = st.session_state.perfil
    propuestas = st.session_state.propuestas
    seccion("02 · Compará y personalizá", "Dos caminos para una misma meta",
            "Compará productos, sustituí cualquier corte y ajustá cantidades. Los precios cambian según tu elección.")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Personas", str(perfil["adultos"] + perfil["ninos"]))
    m2.metric("Días", str(perfil["dias"]))
    m3.metric("Comidas a preparar", str(total_comidas(perfil)))
    m4.metric("Proteína cruda por comida", f"{gramos_por_comida(perfil)} g")
    if perfil["restricciones_texto"]:
        st.warning("Restricciones escritas: revisalas manualmente. En esta demo el sistema solo aplica las categorías excluidas mediante los selectores.")
    st.markdown('<div class="hint"><strong>Precios de demostración.</strong> Los valores del JSON son ilustrativos y no garantizan inventario. Cambialos por los oficiales antes de usar la aplicación con clientes.</div>', unsafe_allow_html=True)
    disponibles = catalogo_disponible(data, perfil)
    if not disponibles:
        st.error("Ya no hay productos disponibles; revisá productos.json y generá de nuevo.")
        return
    left, right = st.columns(2, gap="large")
    for op, container in zip(propuestas, (left, right)):
        with container:
            with st.container(border=True):
                render_propuesta(op, disponibles, perfil, data)
    st.caption("A y B son dos combinaciones diferentes; el costo exacto depende de los cortes y las cantidades que elijas. No son dietas prescritas.")


def menu_txt(perfil: dict, cart: dict, menu: list[dict], by_sku: dict) -> str:
    kg, total = totales_carrito(cart, by_sku)
    rows = ["CORTES & BRASAS — MI COMPRA Y MENÚ", "PRECIOS DE DEMOSTRACIÓN, NO COTIZACIÓN FINAL", "",
            f"Para {perfil['adultos']} adulto(s) y {perfil['ninos']} niño(s); {perfil['dias']} día(s)",
            f"Total: {kg_text(kg)} · {crc(total)}", "", "LISTA DE COMPRA"]
    for sku, qty in cart.items():
        rows.append(f"- {by_sku[sku]['producto']}: {kg_text(qty)} — {crc(qty * by_sku[sku]['precio_kg_crc'])}")
    rows.extend(["", "MENÚ PROPUESTO"])
    for item in menu:
        r = item["receta"]
        rows.append(f"Día {item['dia']} / {item['momento']}: {r['nombre']} ({item['producto']}, {item['gramos']} g crudos para el hogar)")
    rows.extend(["", "INGREDIENTES ADICIONALES (NO INCLUIDOS EN LA COMPRA DE PROTEÍNAS)"])
    rows.extend("- " + x for x in extras_menu(menu))
    rows.extend(["", "Cantidades orientativas; requieren revisión profesional cuando exista una pauta clínica.",
                  "Verificá disponibilidad, precios, alérgenos y temperaturas seguras de cocción."])
    return "\n".join(rows)


def panel_aprobado(data: dict) -> None:
    perfil = st.session_state.perfil
    cart = st.session_state.compra
    menu = st.session_state.menu
    by_sku = {p["sku"]: p for p in data["productos"]}
    kg, total = totales_carrito(cart, by_sku)
    st.markdown('<div class="step-line"></div>', unsafe_allow_html=True)
    seccion("03 · Tu compra elegida", f"Opción {st.session_state.plan_aprobado}, lista para organizar",
            "Con tu selección aprobada, armamos un menú determinista con las recetas que ya existen en productos.json.")
    a, b, c = st.columns(3)
    a.metric("Peso de proteína", kg_text(kg))
    b.metric("Total estimado", crc(total))
    c.metric("Recetas planificadas", str(len(menu)))
    pestañas = st.tabs(["Calendario de comidas", "Recetas e ideas", "Mi pedido"])
    with pestañas[0]:
        ncols = min(3, perfil["dias"])
        cols = st.columns(ncols)
        for day in range(1, perfil["dias"] + 1):
            with cols[(day - 1) % ncols]:
                st.markdown(f"### Día {day:02d}")
                daily = [item for item in menu if item["dia"] == day]
                for item in daily:
                    st.markdown(f'''<div class="menu-meal"><span class="meal">{esc(item["momento"])}</span>
                    <strong>{esc(item["receta"]["nombre"])}</strong>
                    <small>{esc(item["producto"])} · {item["gramos"]} g crudos para el hogar</small></div>''', unsafe_allow_html=True)
        st.info("Las recetas reutilizan los productos comprados. Los acompañamientos (arroz, tortillas, vegetales...) se calculan aparte y no se cobran en este carrito.")
    with pestañas[1]:
        st.markdown("### Un mismo corte, distintas posibilidades")
        st.caption("Las recetas son ideas almacenadas en el JSON, no generadas por IA.")
        for sku in cart:
            producto = by_sku[sku]
            st.markdown(f"#### {ICONOS.get(producto['categoria'], '🥩')} {producto['producto']}")
            recetas = producto.get("recetas", [])
            cols = st.columns(min(3, max(1,len(recetas))))
            for j, r in enumerate(recetas):
                with cols[j % len(cols)]:
                    with st.container(border=True):
                        st.markdown(f"**{r['nombre']}**")
                        st.caption(f"⏱️ {r.get('minutos', 35)} min aprox. · Ideas de acompañamiento")
                        with st.expander("Ver ingredientes y preparación"):
                            st.markdown("**Acompañamientos**")
                            for ingredient in r.get("ingredientes_extra", []):
                                st.write("• " + str(ingredient))
                            st.markdown("**Pasos**")
                            for index, paso in enumerate(r.get("pasos", []), 1):
                                st.write(f"{index}. {paso}")
            st.divider()
        extras = extras_menu(menu)
        with st.expander("Lista de supermercado adicional", expanded=False):
            st.write(", ".join(extras) if extras else "Sin acompañamientos registrados.")
    with pestañas[2]:
        st.markdown("### Resumen de compra")
        for sku, quantity in cart.items():
            p = by_sku[sku]
            col_title, col_cost = st.columns([3, 1])
            with col_title:
                st.markdown(f"**{p['producto']}** · {kg_text(quantity)}")
                st.caption(f"{p['categoria']} · {crc(p['precio_kg_crc'])}/kg")
            with col_cost:
                st.markdown("**" + crc(quantity * p["precio_kg_crc"]) + "**")
            st.divider()
        st.metric("Total estimado", crc(total))
        st.caption("Precios ilustrativos; no incluyen envío ni constituyen un pedido confirmado.")
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow(["SKU", "Producto", "Categoría", "kg", "Precio por kg (CRC)", "Subtotal CRC"])
        for sku, quantity in cart.items():
            p = by_sku[sku]
            writer.writerow([sku, p["producto"], p["categoria"], quantity,
                             p["precio_kg_crc"], round(quantity * p["precio_kg_crc"], 2)])
        resumen = menu_txt(perfil, cart, menu, by_sku)
        wa_msg = ("Hola, Cortes & Brasas. Quisiera consultar esta compra:\n" + "\n".join(
            f"• {by_sku[sku]['producto']}: {kg_text(qty)}" for sku, qty in cart.items())
            + f"\nTotal referencial: {crc(total)}. ¿Me confirman precios y disponibilidad?")
        phone = "".join(ch for ch in str(data.get("tienda", {}).get("whatsapp", "")) if ch.isdigit())
        whatsapp = ("https://wa.me/" + phone if phone else "https://api.whatsapp.com/send") + "?text=" + quote(wa_msg)
        b1, b2, b3 = st.columns(3)
        b1.download_button("Descargar compra CSV", csv_buf.getvalue().encode("utf-8-sig"),
                           file_name="compra_cortes_brasas.csv", mime="text/csv", use_container_width=True)
        b2.download_button("Descargar menú TXT", resumen.encode("utf-8"),
                           file_name="menu_cortes_brasas.txt", mime="text/plain", use_container_width=True)
        b3.link_button("Compartir por WhatsApp", whatsapp, use_container_width=True)
        if not phone:
            st.caption("Podés colocar el número de la carnicería en tienda.whatsapp del JSON para abrir el chat directamente.")
    st.markdown('<div class="step-line"></div>', unsafe_allow_html=True)


def sidebar(data: dict) -> None:
    if LOGO.is_file():
        st.sidebar.image(str(LOGO), use_container_width=True)
    else:
        st.sidebar.markdown("## Cortes & Brasas")
    st.sidebar.markdown("**Boutique de carnes**")
    st.sidebar.caption("Una experiencia de compra más personalizada")
    st.sidebar.divider()
    st.sidebar.success("Modo demostración · Using AI")
    st.sidebar.write("Todo el catálogo se carga desde **productos.json** (misma carpeta que app.py).")
    st.sidebar.metric("Productos en catálogo", str(len(data["productos"])))
    st.sidebar.metric("Productos disponibles", str(sum(p["disponible"] for p in data["productos"])))
    st.sidebar.caption("Los PDF y las imágenes se adjuntan sin analizarse. No se realiza ninguna llamada a OpenAI.")
    with st.sidebar.expander("¿Cómo actualizo precios, productos o fotos?"):
        st.markdown("Editá `productos.json` y guardalo. Refrescá Streamlit para ver los cambios. Para una foto, colocala en `assets/` y escribí su ruta en `imagen`, por ejemplo `assets/pechuga.jpg`. También funciona una URL HTTPS.")
    with st.sidebar.expander("Siguiente etapa: conectar IA"):
        st.markdown("La función `analizar_documentos_con_ia()` está reservada para esa integración. Luego podrás leer el InBody o el PDF mediante OpenAI, solicitar confirmación de datos y alimentar el mismo motor de compra.")
    if data.get("configuracion", {}).get("precios_son_demo", True):
        st.sidebar.warning("Precios del JSON: DEMOSTRATIVOS.")


def main() -> None:
    estilo()
    try:
        data = leer_catalogo(CATALOGO)
    except CatalogoError as e:
        st.error(str(e))
        st.code('{"tienda": {"nombre": "Cortes & Brasas"}, "productos": []}', language="json")
        st.stop()
    st.session_state.setdefault("version", 0)
    st.session_state.setdefault("perfil", None)
    st.session_state.setdefault("propuestas", None)
    st.session_state.setdefault("compra", None)
    st.session_state.setdefault("menu", None)
    st.session_state.setdefault("plan_aprobado", None)
    sidebar(data)
    inicio()
    panel_perfil(data)
    if st.session_state.propuestas:
        st.markdown('<div class="step-line"></div>', unsafe_allow_html=True)
        panel_opciones(data)
    if st.session_state.compra and st.session_state.menu:
        panel_aprobado(data)
    st.markdown('''<div class="footer">CORTES & BRASAS · BOUTIQUE DE CARNES · PROTOTIPO DEMOSTRATIVO SIN IA<br>
    Porciones y costos orientativos · Verificar indicaciones nutricionales, stock, alérgenos y precios antes de confirmar.</div>''', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
