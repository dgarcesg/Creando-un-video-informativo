"""Vuelve a armar el reel con la misma narración (salidas/reel.wav) y corrige palabras que Whisper escribió mal
en los subtítulos. No vuelve a clonar la voz, que es el paso que tarda varios minutos.

    .venv\\Scripts\\python -X utf8 rehacer_video.py --autor "Adriana Garcés" --fuente "NASA FIRMS, Open-Meteo y Sentinel-2"

Usa reel.py de la sesión 15 del curso (Data-Science-Python/sessions/15-texto-a-reel).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

AQUI = Path(__file__).resolve().parent
CURSO = AQUI.parents[2] / "Data-Science-Python" / "sessions" / "15-texto-a-reel"

# Cómo lo escribió Whisper (en minúsculas, sin puntuación) -> cómo debe verse en pantalla
CORRECCIONES = {"gitbo": "GitHub", "github": "GitHub"}


def escenas_por_silencios(audio, sr, n):
    """reel.narrar separa las escenas con silencios exactos (ceros): 0.3 s al inicio, 0.35 s entre escenas
    y 0.8 s al final. La voz clonada nunca tiene tantos ceros seguidos, así que los silencios marcan las escenas."""
    cero = np.concatenate([[False], audio == 0, [False]]).astype(np.int8)
    bordes = np.flatnonzero(np.diff(cero))
    silencios = [(a, b) for a, b in zip(bordes[::2], bordes[1::2]) if b - a >= int(0.3 * sr)]
    if len(silencios) != n + 1:
        raise SystemExit(f"Esperaba {n + 1} silencios para {n} escenas y encontré {len(silencios)}.")
    return [(silencios[i][1] / sr, silencios[i + 1][0] / sr) for i in range(n)]


def corregir(palabras, fin_voz):
    """Aplica CORRECCIONES y descarta lo que Whisper "oye" en el silencio final (suele repetir la última frase)."""
    salida = []
    for ini, fin, p in palabras:
        if ini >= fin_voz:
            print(f"   {ini:5.1f} s  «{p}» descartada: cae en el silencio final")
            continue
        base = p.rstrip(".,;:?!")
        nueva = CORRECCIONES.get(base.lower(), base) + p[len(base):]
        if nueva != p:
            print(f"   {ini:5.1f} s  «{p}» -> «{nueva}»")
        salida.append((ini, fin, nueva))
    return salida


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--autor", required=True)
    p.add_argument("--fuente", required=True, help="fuente de los datos, aparece en el video")
    p.add_argument("--salidas", default=str(AQUI / "salidas"))
    p.add_argument("--curso", default=str(CURSO), help="carpeta de la sesión 15, donde está reel.py")
    a = p.parse_args()

    sys.path.insert(0, a.curso)
    import reel

    salidas = Path(a.salidas)
    guion = json.loads((salidas / "guion.json").read_text(encoding="utf-8"))
    audio, sr = sf.read(salidas / "reel.wav", dtype="float32")
    escenas = escenas_por_silencios(audio, sr, len(guion["escenas"]))
    print(f"{len(audio) / sr:.1f} s de narración; escenas desde los segundos:",
          ", ".join(f"{ini:.1f}" for ini, _ in escenas))

    narracion = reel.Narracion(audio, sr, escenas)
    reel.subtitulos(narracion, guion)
    narracion.palabras = corregir(narracion.palabras, fin_voz=escenas[-1][1])
    reel.a_srt(narracion, salidas / "reel.srt")
    reel.portada(guion, narracion, salidas / "portada.png", a.fuente, a.autor)
    reel.video(guion, narracion, salidas / "reel.mp4", a.fuente, a.autor)
    print(f"listo: {salidas / 'reel.mp4'}")
