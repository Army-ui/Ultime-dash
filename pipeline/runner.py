"""
Orchestrateur du pipeline complet.
Exécute les 4 étapes (scan -> nettoyage -> détection -> enrichissement)
dans un thread d'arrière-plan, et maintient un état partagé (PIPELINE_STATE)
que l'interface Dash peut interroger via dcc.Interval pour afficher
une barre de progression / écran de chargement en temps réel.
"""

import threading
import time
import traceback

from pipeline.step1_scan import run_scan
from pipeline.step2_clean import run_clean
from pipeline.step3_detect import run_detect_duplicates
from pipeline.step4_enrich import run_enrich

RAW_CSV = "raw_file_metadata.csv"
CLEANED_CSV = "cleaned_file_metadata.csv"

# État global partagé, lu par les callbacks Dash (un seul process / un seul worker)
PIPELINE_STATE = {
    "status": "idle",       # idle | running | done | error
    "step": 0,               # 0..4
    "step_label": "",
    "progress": 0,            # 0..100 (pour l'étape de scan, granulaire)
    "logs": [],
    "error": None,
    "started_at": None,
    "finished_at": None,
}

_lock = threading.Lock()


def _set_state(**kwargs):
    with _lock:
        PIPELINE_STATE.update(kwargs)


def _add_log(message):
    with _lock:
        PIPELINE_STATE["logs"].append(message)
        # Garde les 200 dernières lignes pour ne pas saturer la mémoire
        PIPELINE_STATE["logs"] = PIPELINE_STATE["logs"][-200:]


def get_state():
    with _lock:
        return dict(PIPELINE_STATE)


def _run_pipeline(dossier_cible=None, nb_threads=4):
    try:
        _set_state(status="running", step=0, step_label="scan", progress=0,
                    started_at=time.time(), error=None, logs=[])

        # ---- ÉTAPE 1 : SCAN ----
        _set_state(step=1, step_label="scan", progress=0)

        def on_progress(current, total):
            pct = int((current / total) * 100) if total else 100
            _set_state(progress=pct)

        run_scan(
            dossier_cible=dossier_cible,
            nb_threads=nb_threads,
            output_csv=RAW_CSV,
            progress_callback=on_progress,
            log_callback=_add_log,
        )

        # ---- ÉTAPE 2 : NETTOYAGE ----
        _set_state(step=2, step_label="clean", progress=0)
        run_clean(input_csv=RAW_CSV, output_csv=CLEANED_CSV, log_callback=_add_log)
        _set_state(progress=100)

        # ---- ÉTAPE 3 : DÉTECTION DOUBLONS ----
        _set_state(step=3, step_label="detect", progress=0)
        run_detect_duplicates(fichier=CLEANED_CSV, log_callback=_add_log)
        _set_state(progress=100)

        # ---- ÉTAPE 4 : ENRICHISSEMENT ----
        _set_state(step=4, step_label="enrich", progress=0)
        run_enrich(fichier=CLEANED_CSV, log_callback=_add_log)
        _set_state(progress=100)

        _set_state(status="done", step=5, step_label="done", finished_at=time.time())

    except Exception as e:
        tb = traceback.format_exc()
        _add_log(f"❌ ERREUR : {e}\n{tb}")
        _set_state(status="error", error=str(e), finished_at=time.time())


def start_pipeline_async(dossier_cible=None, nb_threads=4):
    """Lance le pipeline complet dans un thread daemon. Sans bloquer l'app Dash."""
    state = get_state()
    if state["status"] == "running":
        return  # déjà en cours
    thread = threading.Thread(
        target=_run_pipeline,
        kwargs={"dossier_cible": dossier_cible, "nb_threads": nb_threads},
        daemon=True,
    )
    thread.start()