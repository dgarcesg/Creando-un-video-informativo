"""Vuelve a narrar una sola escena del reel y la pega en salidas/reel.wav, sin tocar las demás.

Sirve cuando la voz pronuncia mal una palabra: a la voz se le da el texto escrito como suena ("guit jab" por
"GitHub"), mientras guion.json conserva la palabra bien escrita para los subtítulos.

    # 1. Generar tomas de la escena 7 para escucharlas (quedan en salidas/escena7_toma*.wav)
    .venv\\Scripts\\python -X utf8 renarrar_escena.py --voz mi_voz.m4a --escena 7 --texto "... mi guit jab, ..."
    # 2. Pegar la toma elegida y rehacer subtítulos y video
    .venv\\Scripts\\python -X utf8 renarrar_escena.py --escena 7 --elegir 2
    .venv\\Scripts\\python -X utf8 rehacer_video.py --autor "Adriana Garcés" --fuente "NASA FIRMS, Open-Meteo y Sentinel-2"
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from rehacer_video import AQUI, CURSO, escenas_por_silencios

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--escena", type=int, required=True, help="número de escena, desde 1")
    p.add_argument("--voz", help="tu grabación; hace falta para generar tomas")
    p.add_argument("--texto", action="append", help="cómo debe sonar la escena; se repite para probar varias escrituras")
    p.add_argument("--tomas", type=int, default=2, help="tomas por cada --texto")
    p.add_argument("--elegir", type=int, help="pega en reel.wav la toma con este número")
    p.add_argument("--recortar-final", type=float, default=0, help="con --elegir: segundos de silencio que se quitan al final")
    p.add_argument("--tts", default="Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    p.add_argument("--salidas", default=str(AQUI / "salidas"))
    p.add_argument("--curso", default=str(CURSO), help="carpeta de la sesión 15, donde está reel.py")
    a = p.parse_args()

    sys.path.insert(0, a.curso)
    import reel

    salidas = Path(a.salidas)
    guion = json.loads((salidas / "guion.json").read_text(encoding="utf-8"))
    audio, sr = sf.read(salidas / "reel.wav", dtype="float32")
    ini, fin = escenas_por_silencios(audio, sr, len(guion["escenas"]))[a.escena - 1]
    i0, i1 = round(ini * sr), round(fin * sr)

    if a.elegir:
        toma, sr_toma = sf.read(salidas / f"escena{a.escena}_toma{a.elegir}.wav", dtype="float32")
        if sr_toma != sr:
            raise SystemExit(f"La toma está a {sr_toma} Hz y la narración a {sr} Hz.")
        respaldo = salidas / f"reel_antes_escena{a.escena}.wav"
        if not respaldo.exists():
            shutil.copy(salidas / "reel.wav", respaldo)
        nuevo = np.concatenate([audio[:i0], toma, audio[i1:]])
        if a.recortar_final:
            n = round(a.recortar_final * sr)
            if np.any(nuevo[-n:]):
                raise SystemExit(f"Los últimos {a.recortar_final} s no son silencio: no se pueden recortar.")
            nuevo = nuevo[:-n]
        sf.write(salidas / "reel.wav", nuevo, sr)
        print(f"toma {a.elegir} pegada en la escena {a.escena}: la narración pasa de {len(audio) / sr:.1f} s "
              f"a {len(nuevo) / sr:.1f} s (respaldo en {respaldo.name})")
        raise SystemExit

    if not (a.voz and a.texto):
        raise SystemExit("Para generar tomas hacen falta --voz y --texto.")
    voz = reel.Voz(a.voz, modelo=a.tts)
    textos = [t for t in a.texto for _ in range(a.tomas)]
    wavs = voz.decir(textos)
    if voz.sr != sr:
        raise SystemExit(f"La voz genera a {voz.sr} Hz y la narración está a {sr} Hz.")
    print(f"escena {a.escena}: ahora dura {fin - ini:.1f} s; la narración, {len(audio) / sr:.1f} s")
    for k, (texto, w) in enumerate(zip(textos, wavs), 1):
        w = np.asarray(w, np.float32)
        sf.write(salidas / f"escena{a.escena}_toma{k}.wav", w, sr)
        total = (len(audio) - (i1 - i0) + len(w)) / sr
        print(f"  toma {k}: {len(w) / sr:.1f} s -> reel de {total:.1f} s{'  (pasa de 60 s)' if total > 60 else ''}")
        print(f"     texto: {texto}")
        print(f"     Whisper oye: {reel._transcribir(reel._a16k(w, sr))}")
