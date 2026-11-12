"""Motor determinista para Cortes & Brasas (SIN IA).

El catalogo se lee desde productos.json ubicado junto a app.py.
Las cantidades son de compra, no recomendaciones medicas.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import json
import math

CATEGORIAS = ("Res", "Pollo", "Cerdo", "Pescado", "Pavo")
PRIORIDAD_A = {
    "Res": ["R01", "R03", "R04", "R05", "R02", "R06"],
    "Pollo": ["P01", "P04", "P02", "P03"],
    "Cerdo": ["C01", "C03", "C02"],
    "Pescado": ["F02", "F01"],
    "Pavo": ["T01"],
}
PRIORIDAD_B = {
    "Res": ["R02", "R01", "R06", "R03", "R05", "R04"],
    "Pollo": ["P02", "P03", "P04", "P01"],
    "Cerdo": ["C02", "C03", "C01"],
    "Pescado": ["F01", "F02"],
    "Pavo": ["T01"],
}


class CatalogoError(ValueError):
    pass


def leer_catalogo(ruta: str | Path) -> dict:
    ruta = Path(ruta)
    if not ruta.exists():
        raise CatalogoError(f"No encontré {ruta.name} junto a app.py.")
    try:
        data = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogoError(f"No se puede leer {ruta.name}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("productos"), list):
        raise CatalogoError("El JSON debe incluir una lista 'productos'.")
    vistos = set()
    for i, p in enumerate(data["productos"], 1):
        if not isinstance(p, dict):
            raise CatalogoError(f"El producto {i} debe ser un objeto JSON.")
        sku = str(p.get("sku", "")).strip()
        nombre = str(p.get("producto", "")).strip()
        cat = p.get("categoria")
        if not sku or sku in vistos or not nombre:
            raise CatalogoError(f"Producto {i}: el SKU y nombre deben existir; los SKU no pueden repetirse.")
        vistos.add(sku)
        if cat not in CATEGORIAS:
            raise CatalogoError(f"Producto {sku}: categoría no reconocida: {cat}.")
        precio = p.get("precio_kg_crc")
        if isinstance(precio, bool) or not isinstance(precio, (int, float)) or not math.isfinite(precio) or precio <= 0:
            raise CatalogoError(f"Producto {sku}: 'precio_kg_crc' debe ser un número positivo.")
        if not isinstance(p.get("disponible"), bool):
            raise CatalogoError(f"Producto {sku}: 'disponible' debe ser true o false.")
        stock = p.get("stock_kg")
        if stock is not None and (isinstance(stock, bool) or not isinstance(stock, (int, float)) or not math.isfinite(stock) or stock < 0):
            raise CatalogoError(f"Producto {sku}: 'stock_kg' debe ser null o un número no negativo.")
        if not isinstance(p.get("recetas", []), list):
            raise CatalogoError(f"Producto {sku}: 'recetas' debe ser una lista.")
    config = data.get("configuracion") or {}
    step = config.get("incremento_compra_kg", 0.25)
    if isinstance(step, bool) or not isinstance(step, (int, float)) or not (0 < step <= 1):
        raise CatalogoError("incremento_compra_kg debe ser mayor que 0 y como máximo 1.")
    if not data["productos"]:
        raise CatalogoError("El catálogo no tiene productos.")
    return data


def catalogo_disponible(data: dict, perfil: dict) -> list[dict]:
    preferidas = set(perfil["categorias"])
    excluidas = set(perfil["excluidas"])
    paso = float(data.get("configuracion", {}).get("incremento_compra_kg", 0.25))
    return [p for p in data["productos"] if p["categoria"] in preferidas
            and p["categoria"] not in excluidas and p["disponible"]
            and (p.get("stock_kg") is None or p["stock_kg"] + 1e-8 >= paso)]


def gramos_por_comida(perfil: dict) -> int:
    # Los menores usan una proporción ilustrativa configurable en la UI.
    return int(perfil["adultos"] * perfil["porcion_adulto_g"]
               + perfil["ninos"] * perfil["porcion_nino_g"])


def total_comidas(perfil: dict) -> int:
    return int(perfil["dias"] * perfil["comidas_dia"])


def ceil_to_step(value: float, step: float) -> float:
    return round(math.ceil((value - 1e-10) / step) * step, 5)


def _orden_categorias(perfil: dict) -> list[str]:
    return [c for c in perfil["categorias"] if c not in perfil["excluidas"]]


def _seleccionar_productos(disponibles: list[dict], perfil: dict, variant: str) -> list[dict]:
    por_sku = {p["sku"]: p for p in disponibles}
    por_cat = defaultdict(list)
    for p in disponibles:
        por_cat[p["categoria"]].append(p)
    prioridades = PRIORIDAD_A if variant == "A" else PRIORIDAD_B
    categorias = _orden_categorias(perfil)
    if variant == "B":
        # Misma variedad de familias en un orden distinto, con cortes alternativos.
        categorias = sorted(categorias, key=lambda c: min(
            (p["precio_kg_crc"] for p in por_cat[c]), default=float("inf")))
    elegidos: list[dict] = []
    max_n = min(3, total_comidas(perfil), len(disponibles))
    for cat in categorias:
        if len(elegidos) >= max_n:
            break
        for sku in prioridades.get(cat, []):
            if sku in por_sku and por_sku[sku] not in elegidos:
                elegidos.append(por_sku[sku])
                break
        else:
            lista = por_cat.get(cat, [])
            if lista:
                elegidos.append(sorted(lista, key=lambda p: p["precio_kg_crc"])[0])
    # Completar hasta 3 cortes incluso si el cliente eligió una sola familia.
    if len(elegidos) < max_n:
        ordered = sorted(disponibles,
            key=lambda p: (p["precio_kg_crc"] if variant == "B" else -len(p.get("recetas", [])),
                           p["sku"]))
        for p in ordered:
            if p not in elegidos:
                elegidos.append(p)
                if len(elegidos) == max_n:
                    break
    return elegidos


def _asignar_comidas(n: int, k: int) -> list[int]:
    """Distribuye n comidas completas para permitir un menú realizable."""
    if k == 0 or n == 0:
        return []
    weights = [0.45, 0.35, 0.20][:k]
    s = sum(weights)
    raw = [n * w / s for w in weights]
    counts = [max(1, int(math.floor(x))) for x in raw]
    while sum(counts) > n:
        idx = max((i for i in range(k) if counts[i] > 1), key=lambda i: counts[i] - raw[i])
        counts[idx] -= 1
    while sum(counts) < n:
        idx = max(range(k), key=lambda i: raw[i] - counts[i])
        counts[idx] += 1
    return counts


def construir_propuestas(data: dict, perfil: dict) -> list[dict]:
    disponibles = catalogo_disponible(data, perfil)
    if not disponibles:
        raise ValueError("No hay productos disponibles para las categorías seleccionadas.")
    step = float(data.get("configuracion", {}).get("incremento_compra_kg", 0.25))
    kg_comida = gramos_por_comida(perfil) / 1000
    opciones = []
    for variant in ("A", "B"):
        productos = _seleccionar_productos(disponibles, perfil, variant)
        counts = _asignar_comidas(total_comidas(perfil), len(productos))
        filas = []
        for p, n in zip(productos, counts):
            kg = ceil_to_step(n * kg_comida, step)
            if p.get("stock_kg") is not None:
                # Con stock conocido, nunca prometer más de lo disponible.
                max_kg = math.floor((p["stock_kg"] + 1e-9) / step) * step
                kg = min(kg, max_kg)
            if kg > 0:
                filas.append({"sku": p["sku"], "kg": kg})
        opciones.append({
            "id": variant,
            "titulo": "Selección boutique" if variant == "A" else "Selección alternativa",
            "subtitulo": "Cortes versátiles para una semana con variedad." if variant == "A"
                else "Otra combinación de proteínas y preparaciones.",
            "filas": filas,
        })
    return opciones


def sumar_carrito(filas: list[dict]) -> dict[str, float]:
    cart = defaultdict(float)
    for item in filas:
        kg = float(item["kg"])
        if kg > 0:
            cart[str(item["sku"])] += kg
    return {sku: round(kg, 4) for sku, kg in cart.items()}


def totales_carrito(cart: dict[str, float], por_sku: dict[str, dict]) -> tuple[float, float]:
    kg = sum(cart.values())
    total = sum(cart[sku] * float(por_sku[sku]["precio_kg_crc"]) for sku in cart)
    return round(kg, 3), round(total, 2)


def capacidad_comidas(cart: dict[str, float], perfil: dict) -> int:
    por = gramos_por_comida(perfil)
    if por <= 0:
        return 0
    return sum(int((kg * 1000 + 1e-6) // por) for kg in cart.values())


def validar_compra(cart: dict[str, float], perfil: dict, disponibles: list[dict]) -> tuple[bool, str]:
    by_sku = {p["sku"]: p for p in disponibles}
    if not cart:
        return False, "Elegí al menos un producto."
    for sku, kg in cart.items():
        if sku not in by_sku:
            return False, f"{sku} no está disponible."
        stock = by_sku[sku].get("stock_kg")
        if stock is not None and kg > float(stock) + 1e-8:
            return False, f"Stock insuficiente para {by_sku[sku]['producto']}."
    cubiertas = capacidad_comidas(cart, perfil)
    req = total_comidas(perfil)
    if cubiertas < req:
        return False, f"La selección cubre {cubiertas} de {req} comidas completas; agregá más cantidad."
    return True, ""


def generar_menu(cart: dict[str, float], perfil: dict, por_sku: dict[str, dict]) -> list[dict]:
    req = total_comidas(perfil)
    por = gramos_por_comida(perfil)
    remaining = {sku: int((kg * 1000 + 1e-6) // por) for sku, kg in cart.items()}
    used = Counter()
    menu = []
    last = None
    for index in range(req):
        posibles = [sku for sku, slots in remaining.items() if slots > 0]
        if not posibles:
            raise ValueError("La compra no alcanza para el menú: incrementá las cantidades.")
        sku = min(posibles, key=lambda x: (x == last, used[x], -remaining[x], x))
        p = por_sku[sku]
        recetas = p.get("recetas", [])
        if not recetas:
            recetas = [{"nombre": f"{p['producto']} con vegetales",
                        "minutos": 35, "ingredientes_extra": ["vegetales", "arroz"],
                        "pasos": ["Prepará los acompañamientos.", "Cociná completamente la proteína.", "Serví."]}]
        receta = recetas[used[sku] % len(recetas)]
        menu.append({
            "dia": index // perfil["comidas_dia"] + 1,
            "momento": ("Almuerzo", "Cena", "Otra comida")[index % perfil["comidas_dia"]],
            "sku": sku,
            "gramos": por,
            "producto": p["producto"],
            "receta": receta,
        })
        remaining[sku] -= 1
        used[sku] += 1
        last = sku
    return menu


def extras_menu(menu: list[dict]) -> list[str]:
    return sorted({str(x) for item in menu for x in item["receta"].get("ingredientes_extra", [])})
