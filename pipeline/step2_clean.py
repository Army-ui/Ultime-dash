"""
ÉTAPE 2 — NETTOYAGE
Logique strictement identique au script original fourni par l'utilisateur.
"""

import pandas as pd
import re
from datetime import datetime


def run_clean(input_csv="raw_file_metadata.csv", output_csv="cleaned_file_metadata.csv",
              log_callback=None):

    def log(msg):
        print(msg)
        if log_callback:
            log_callback(msg)

    # =========================
    # 1. CHARGEMENT
    # =========================
    df = pd.read_csv(input_csv)

    log("✅ Fichier chargé")
    log(f"Taille initiale : {df.shape}")

    if df.empty:
        log("⚠️ Aucune donnée à nettoyer (dossier scanné vide).")
        df_final = pd.DataFrame(columns=[
            "nom_fichier", "chemin", "chemin_dossier", "profondeur_dossier",
            "taille_octets", "taille_lisible", "categorie_taille_fichier",
            "extension", "hash_md5", "date_creation", "date_modification",
            "age_fichier", "jours_depuis_modification",
        ])
        df_final.to_csv(output_csv, index=False)
        return df_final

    # =========================
    # 2. NETTOYAGE
    # =========================
    df = df.dropna(subset=[
        "nom_fichier",
        "chemin",
        "taille_octets",
        "hash_md5",
        "date_creation",
        "date_modification"
    ])

    def supprimer_extensions_nulles(df):
        avant = len(df)
        df = df.dropna(subset=["extension"])
        df = df[df["extension"].astype(str).str.strip() != ""]
        apres = len(df)
        log(f"✅ Lignes supprimées (extensions nulles/vides) : {avant - apres}")
        return df

    df = supprimer_extensions_nulles(df)

    # Normalisation
    df["nom_fichier"] = df["nom_fichier"].str.lower().str.strip()
    df["extension"] = df["extension"].str.lower().str.strip()
    df["chemin"] = df["chemin"].str.replace("\\\\", "/", regex=True)

    log("✅ Nettoyage OK")
    log(f"Taille : {df.shape}")

    # =========================
    # 3. VALIDATION DATES
    # =========================
    df["date_creation"] = pd.to_datetime(df["date_creation"], errors="coerce")
    df["date_modification"] = pd.to_datetime(df["date_modification"], errors="coerce")

    df = df.dropna(subset=["date_creation", "date_modification"])
    df = df[df["date_creation"] <= df["date_modification"]]

    log("✅ Dates validées")

    # =========================
    # 4. DOUBLONS DE CHEMIN
    # =========================
    df = df.drop_duplicates(subset=["chemin"])

    # =========================
    # 5. NOM NETTOYÉ
    # =========================
    def supprimer_extension(nom):
        if "." in nom:
            return ".".join(nom.split(".")[:-1])
        return nom

    df["nom_sans_extension"] = df["nom_fichier"].apply(supprimer_extension)

    df["nom_fichier"] = df["nom_sans_extension"].apply(
        lambda x: re.sub(r'[^a-zA-Z0-9]', '', str(x))
    )

    df = df[df["nom_fichier"] != ""]

    # =========================
    # 6. FEATURE ENGINEERING
    # =========================
    df["chemin_dossier"] = df["chemin"].apply(lambda x: "/".join(x.split("/")[:-1]))

    df["profondeur_dossier"] = df["chemin_dossier"].apply(
        lambda x: len([p for p in x.split("/") if p != ""])
    )

    def categoriser_taille(taille):
        if taille < 1_000_000:
            return "Petit"
        elif taille < 100_000_000:
            return "Moyen"
        else:
            return "Grand"

    df["categorie_taille_fichier"] = df["taille_octets"].apply(categoriser_taille)

    aujourdhui = pd.Timestamp(datetime.now())

    df["age_fichier"] = (aujourdhui - df["date_creation"]).dt.days
    df["jours_depuis_modification"] = (aujourdhui - df["date_modification"]).dt.days

    def formater_taille(taille):
        return f"{round(taille / (1024 * 1024), 2)} MB"

    df["taille_lisible"] = df["taille_octets"].apply(formater_taille)

    log("✅ Feature engineering appliqué")

    # =========================
    # 7. DATASET FINAL
    # =========================
    df = df[[
        "nom_fichier",
        "chemin",
        "chemin_dossier",
        "profondeur_dossier",
        "taille_octets",
        "taille_lisible",
        "categorie_taille_fichier",
        "extension",
        "hash_md5",
        "date_creation",
        "date_modification",
        "age_fichier",
        "jours_depuis_modification"
    ]]

    log(f"✅ Dataset final prêt : {df.shape}")

    # =========================
    # 8. EXPORT CSV UNIQUE
    # =========================
    df.to_csv(output_csv, index=False)

    log("✅ Export CSV terminé")
    log(f"✅ Nombre final de fichiers : {len(df)}")
    return df