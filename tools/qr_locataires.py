"""Planches de QR codes « Mon logement » : une étiquette par logement, à coller dans le livret d'accueil
ou le placard technique. Chaque QR ouvre locataire/?l=<logement> sur le site du jumeau.

    python tools/qr_locataires.py

Sortie : locataire/qr/QR_logements_A1.pdf, QR_logements_A2.pdf (A4, 12 étiquettes par page).
"""
import io
import json
import os

import segno
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = 'https://lucasdupuymontbrun-del.github.io/jumeau-fontbelleau/locataire/'
OUT = os.path.join(ROOT, 'locataire', 'qr')
NOIR, OR, GRIS = '#0b0b0d', '#b89464', '#5b5f63'

pdfmetrics.registerFont(TTFont('Archivo', os.path.join(HERE, 'fonts', 'Archivo-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Archivo-Bold', os.path.join(HERE, 'fonts', 'Archivo-Bold.ttf')))
LOGO = ImageReader(os.path.join(ROOT, 'assets', 'img', 'veck-construction-640.png'))


def qr_png(url):
    buf = io.BytesIO()
    segno.make(url, error='m').save(buf, kind='png', scale=12, border=0, dark=NOIR)
    buf.seek(0)
    return ImageReader(buf)


def planche(tour, logs, path):
    W, H = A4
    cols, rows = 3, 4
    mx, my = 10 * mm, 12 * mm
    cw, ch = (W - 2 * mx) / cols, (H - 2 * my) / rows
    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle(f'QR codes « Mon logement » — tour {tour} — Domaine de Fontbelleau')
    c.setAuthor('Veck Construction')
    for i, l in enumerate(logs):
        k = i % (cols * rows)
        if i and k == 0:
            c.showPage()
        col, row = k % cols, k // cols
        x0, y0 = mx + col * cw, H - my - (row + 1) * ch
        # repères de découpe
        c.setStrokeColor(HexColor('#cfd4d2'))
        c.setLineWidth(0.4)
        c.setDash(2, 2)
        c.rect(x0, y0, cw, ch)
        c.setDash()
        # contenu
        cx = x0 + cw / 2
        c.setFillColor(HexColor(OR))
        c.setFont('Archivo-Bold', 7)
        c.drawCentredString(cx, y0 + ch - 8 * mm, 'DOMAINE DE FONTBELLEAU · MON LOGEMENT')
        c.setFillColor(HexColor(NOIR))
        c.setFont('Archivo-Bold', 15)
        c.drawCentredString(cx, y0 + ch - 14.5 * mm, f"Logement {l['id']}")
        q = 30 * mm
        c.drawImage(qr_png(f"{SITE}?l={l['id']}"), cx - q / 2, y0 + ch - 18 * mm - q, q, q)
        c.setFont('Archivo', 7.6)
        c.setFillColor(HexColor(GRIS))
        c.drawCentredString(cx, y0 + 15.5 * mm, 'Scannez pour voir votre consommation')
        c.drawCentredString(cx, y0 + 12 * mm, 'd\'énergie et d\'eau, mois par mois')
        lw = 20 * mm
        c.drawImage(LOGO, cx - lw / 2, y0 + 3.5 * mm, lw, lw * 119 / 640, mask='auto')
    c.save()


def main():
    logs = json.load(open(os.path.join(ROOT, 'data', 'energie', 'logements.json'), encoding='utf-8'))['logements']
    os.makedirs(OUT, exist_ok=True)
    for t in ('A1', 'A2'):
        lt = [l for l in logs if l['tour'] == t]
        p = os.path.join(OUT, f'QR_logements_{t}.pdf')
        planche(t, lt, p)
        print(p, len(lt), 'étiquettes')


if __name__ == '__main__':
    main()
