#!/usr/bin/env python3
"""
Genera modelos de prueba de formato para Section 1 y Section 2.
Envía cada variación a Telegram para que el usuario elija su favorita.
"""
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.notifier import send_to_telegram
from datetime import datetime
from dateutil import tz

ny_now = datetime.now(tz.gettz("America/New_York"))
dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
dia = dias[ny_now.weekday()]
fecha = ny_now.strftime("%d/%m/%Y")


# ============================================================
#  SECCIÓN 1 — Sector Económico del Día
# ============================================================

SEC1_A = f"""📊 *SECTOR ECONÓMICO DEL DÍA*
{dia} {fecha}
━━━━━━━━━━━━━━━━━━━━

*1.* ⭐⭐⭐ FOMC Meeting Minutes
🕐 14:00 ET · 📰 Forex Factory · 🇺🇸

📝 *Resumen:*
Las actas de la última reunión del Comité Federal de Mercado Abierto detallan las deliberaciones sobre política monetaria y las perspectivas económicas.

📈 *Análisis:*
Se espera volatilidad en bonos y acciones. Si las actas sugieren más recortes de tasas, el mercado accionario podría subir. Tono hawkish presionaría a la baja.

🟢 *Beneficiados:* SPY, QQQ, NVDA
🔴 *Perjudicados:* TLT, XLU, USD

━━━━━━━━━━━━━━━━━━━━

*2.* ⭐⭐ Consumer Price Index (CPI)
🕐 8:30 ET · 📰 Yahoo Finance · 🇺🇸

📝 *Resumen:*
Índice de precios al consumidor. Mide la inflación mensual y anual en EE.UU. Dato clave para la Fed.

📈 *Análisis:*
Inflación menor a lo esperado = alcista para acciones. Mayor a lo esperado = bajista, reaviva temores de tasas altas.

🟢 *Beneficiados:* SPY, QQQ (si baja)
🔴 *Perjudicados:* TLT, XLU (si sube)

━━━━━━━━━━━━━━━━━━━━
🤖 Sector Económico del Día · 2 eventos
⚠️ _Contenido informativo, no es asesoría financiera._"""


SEC1_B = f"""📊 *SECTOR ECONÓMICO DEL DÍA*
{dia} {fecha}
━━━━━━━━━━━━━━━━━━━━

1️⃣ ⭐⭐⭐ *FOMC Meeting Minutes*

📰 _Forex Factory_ · 🕐 14:00 · 🇺🇸 USD

Las actas de la reunión del FOMC revelan las deliberaciones internas sobre política monetaria, inflación y empleo.

▸ *Expectativa:* Volatilidad moderada. Mercado busca señales sobre el ritmo de recortes de tasas.
▸ *Si es positivo:* Los índices suben si hay tono dovish.
▸ *Si es negativo:* Presión bajista si sugieren mantener tasas altas.

🟢 `SPY` `QQQ` `NVDA`
🔴 `TLT` `XLU`

━━━━━━━━━━━━━━━━━━━━

2️⃣ ⭐⭐ *Consumer Price Index (CPI)*

📰 _Yahoo Finance_ · 🕐 8:30 · 🇺🇸 USD

El CPI mide la inflación mensual. Es el dato macro que más mueve al mercado después del NFP.

▸ *Expectativa:* Alta volatilidad inmediata tras la publicación.
▸ *Si es positivo:* Inflación controlada → acciones al alza.
▸ *Si es negativo:* Inflación alta → temor a más subidas de tasas.

🟢 `SPY` `QQQ`
🔴 `TLT` `XLU`

━━━━━━━━━━━━━━━━━━━━
🤖 Sector Económico del Día · 2 eventos
⚠️ _Informativo, no asesoría financiera_"""


SEC1_C = f"""📊 *SECTOR ECONÓMICO DEL DÍA*
{dia} {fecha}
━━━━━━━━━━━━━━━━━━━━

*1.* ⭐⭐⭐ FOMC Meeting Minutes
├ 📰 Forex Factory
├ 🕐 14:00 ET · 🇺🇸
├ 📝 Actas de la reunión del FOMC sobre política monetaria
├ 📈 Volatilidad esperada. Tono dovish = alcista; hawkish = bajista
├ 🟢 SPY, QQQ, NVDA
└ 🔴 TLT, XLU

*2.* ⭐⭐ Consumer Price Index (CPI)
├ 📰 Yahoo Finance
├ 🕐 8:30 ET · 🇺🇸
├ 📝 Inflación mensual de EE.UU. Dato clave para la Fed
├ 📈 Baja = alcista; Alta = bajista
├ 🟢 SPY, QQQ
└ 🔴 TLT, XLU

━━━━━━━━━━━━━━━━━━━━
🤖 Sector Económico del Día · 2 eventos"""


# ============================================================
#  SECCIÓN 2 — Último Minuto
# ============================================================

SEC2_A = """🚨 *ÚLTIMO MINUTO*
""" + dia + " " + fecha + """
━━━━━━━━━━━━━━━━━━━━

⭐⭐⭐ *Circle obtiene licencia bancaria del OCC*

📰 CNBC · 🕐 17:42 ET · 🇺🇸 · 🟢 Positivo · 85%

📝 *Resumen:*
Circle, emisor de stablecoins, obtuvo aprobación del OCC para operar como banco de confianza en EE.UU. Las acciones suben 5% en pre-market.

📈 *Análisis:*
Noticia positiva para el sector cripto. Mayor confianza regulatoria podría atraer capital institucional al ecosistema de stablecoins.

🟢 *Beneficiados:* COIN, ARKW, BITO
🔴 *Perjudicados:* —

🔗 *Leer noticia completa:*
https://www.cnbc.com/2026/07/10/circle-gets-an-occ-bank-charter.html
📱 *Publicado por: CNBC*

━━━━━━━━━━━━━━━━━━━━
🤖 Último Minuto · Alerta en tiempo real
⚠️ _Informativo, no asesoría financiera_"""


SEC2_B = """🚨 *ÚLTIMO MINUTO*
""" + dia + " " + fecha + """
━━━━━━━━━━━━━━━━━━━━

*Circle obtiene licencia bancaria del OCC* ⭐⭐⭐
🟢 Positivo · 85% de confianza

📰 _CNBC_ · 🕐 17:42 · 🇺🇸

Circle, emisor de stablecoins, recibe aprobación del OCC para operar como banco. Acciones +5% en pre-market.

▸ *Impacto:* Positivo para cripto y fintech
▸ *Razón:* Mayor legitimidad regulatoria atrae capital institucional

🟢 `COIN` `ARKW` `BITO`
🔴 —

🔗 https://www.cnbc.com/2026/07/10/circle-gets-an-occ-bank-charter.html
📱 Fuente: CNBC

━━━━━━━━━━━━━━━━━━━━
🤖 Último Minuto"""


SEC2_C = """🚨 *ÚLTIMO MINUTO*
""" + dia + " " + fecha + """
━━━━━━━━━━━━━━━━━━━━

Circle obtiene licencia bancaria del OCC
⭐⭐⭐ ALTO IMPACTO · 🟢 85%

📰 CNBC | 🕐 17:42 ET | 🇺🇸

Circle, emisor de stablecoins, obtuvo aprobación del OCC para operar como banco. Las acciones suben 5%.

Se espera impacto positivo en el sector cripto por mayor confianza regulatoria.

🟢 COIN · ARKW · BITO
🔴 —

🔗 https://www.cnbc.com/2026/07/10/circle-gets-an-occ-bank-charter.html
📱 CNBC

━━━━━━━━━━━━━━━━━━━━"""


# ============================================================
#  ENVIAR A TELEGRAM
# ============================================================

def main():
    print("=" * 55)
    print("🎨 ENVIANDO MODELOS DE PRUEBA A TELEGRAM")
    print("=" * 55)

    mensajes = [
        ("📋 SECCIÓN 1 — Modelo A (Compacto)", SEC1_A),
        ("📋 SECCIÓN 1 — Modelo B (Detallado)", SEC1_B),
        ("📋 SECCIÓN 1 — Modelo C (Estructurado)", SEC1_C),
        ("🚨 SECCIÓN 2 — Modelo A (Completo)", SEC2_A),
        ("🚨 SECCIÓN 2 — Modelo B (Conciso)", SEC2_B),
        ("🚨 SECCIÓN 2 — Modelo C (Minimalista)", SEC2_C),
    ]

    for titulo, texto in mensajes:
        print(f"\n📤 Enviando: {titulo}")
        ok = send_to_telegram(texto)
        if ok:
            print(f"   ✅ Enviado")
        else:
            print(f"   ❌ Error")

    print(f"\n{'=' * 55}")
    print("✅ Todos los modelos enviados a Telegram")
    print("Revisa tu Telegram y dime cuál te gusta más")
    print("para cada sección (A, B o C).")
    print("=" * 55)


if __name__ == "__main__":
    main()
