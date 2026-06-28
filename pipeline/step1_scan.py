"""
ÉTAPE 1 — SCAN
Logique strictement identique au script original fourni par l'utilisateur.
Encapsulée en fonction pour pouvoir être pilotée par le pipeline runner
(avec callback de progression optionnel pour l'UI).
"""

import os
import hashlib
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_scan(dossier_cible=None, nb_threads=4, output_csv="raw_file_metadata.csv",
             progress_callback=None, log_callback=None):
    """
    progress_callback(current, total) -> appelé périodiquement pendant le scan
    log_callback(message) -> appelé pour chaque message de log
    """

    def log(msg):
        print(msg)
        if log_callback:
            log_callback(msg)

    # =========================
    # CONFIGURATION
    # =========================
    DOSSIER_CIBLE = dossier_cible or os.path.expanduser("~")
    NB_THREADS = nb_threads
    EXCLUSIONS = ["AppData", "Program Files", "Windows", ".git", "__pycache__"]

    # =========================
    # FONCTION MD5
    # =========================
    def calculer_md5(chemin):
        try:
            hash_md5 = hashlib.md5()
            with open(chemin, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return None

    # =========================
    # TRAITEMENT D'UN FICHIER
    # =========================
    def traiter_fichier(chemin_complet):
        try:
            return {
                "nom_fichier": os.path.basename(chemin_complet),
                "chemin": chemin_complet,
                "taille_octets": os.path.getsize(chemin_complet),
                "extension": os.path.splitext(chemin_complet)[1],
                "hash_md5": calculer_md5(chemin_complet),
                "date_creation": datetime.fromtimestamp(
                    os.path.getctime(chemin_complet)
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "date_modification": datetime.fromtimestamp(
                    os.path.getmtime(chemin_complet)
                ).strftime("%Y-%m-%d %H:%M:%S")
            }
        except (PermissionError, FileNotFoundError, OSError):
            return None

    # =========================
    # COLLECTE DES FICHIERS
    # =========================
    log(f"Debut du scan du dossier : {DOSSIER_CIBLE}")

    liste_fichiers = []

    for dossier, sous_dossiers, fichiers in os.walk(DOSSIER_CIBLE):
        sous_dossiers[:] = [
            d for d in sous_dossiers
            if not any(ex in d for ex in EXCLUSIONS)
        ]

        for fichier in fichiers:
            liste_fichiers.append(os.path.join(dossier, fichier))

    log(f"Nombre de fichiers detectes : {len(liste_fichiers)}")
    log("Debut du traitement en parallele")

    total = len(liste_fichiers)

    # =========================
    # TRAITEMENT PARALLÈLE
    # =========================
    donnees = []

    with ThreadPoolExecutor(max_workers=NB_THREADS) as executor:
        futures = []

        for f in liste_fichiers:
            try:
                future = executor.submit(traiter_fichier, f)
                futures.append(future)
            except Exception as e:
                log(f"Impossible de soumettre le fichier {f} : {e}")

        for i, future in enumerate(as_completed(futures)):
            try:
                resultat = future.result()
                if resultat:
                    donnees.append(resultat)
            except Exception as e:
                log(f"Erreur : {e}")

            if i % 1000 == 0:
                log(f"{i} fichiers traites")

            if progress_callback:
                progress_callback(i + 1, total)

    log("Traitement termine")
    log(f"Nombre de donnees collecte : {len(donnees)}")

    # =========================
    # EXPORT DES DONNÉES
    # =========================
    df = pd.DataFrame(donnees)

    if df.empty:
        # Garantit les colonnes attendues même si aucun fichier n'a été
        # trouvé, pour que les étapes suivantes du pipeline (nettoyage,
        # détection, enrichissement) ne plantent pas sur un CSV sans entêtes.
        df = pd.DataFrame(columns=[
            "nom_fichier", "chemin", "taille_octets", "extension",
            "hash_md5", "date_creation", "date_modification",
        ])
        log("⚠️ Aucun fichier trouvé dans le dossier ciblé.")

    df.to_csv(output_csv, index=False)

    log(f"{len(df)} fichiers scannés sur tous les dépôts !")
    return df