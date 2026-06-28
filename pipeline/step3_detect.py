"""
ÉTAPE 3 — DÉTECTION DES DOUBLONS
Logique strictement identique au script original fourni par l'utilisateur.
"""

import pandas as pd


def run_detect_duplicates(fichier="cleaned_file_metadata.csv", log_callback=None):

    def log(msg):
        print(msg)
        if log_callback:
            log_callback(msg)

    # =========================
    # 1. CHARGEMENT
    # =========================
    df = pd.read_csv(fichier)

    log("✅ Fichier chargé")
    log(f"Taille initiale : {df.shape}")

    if df.empty:
        log("⚠️ Aucune donnée à analyser (dossier scanné vide).")
        for col in ["nb_occurrences", "est_doublon_exact", "rang_dans_groupe",
                    "id_groupe_doublon", "statut_doublon"]:
            df[col] = pd.Series(dtype="object")
        df.to_csv(fichier, index=False)
        return df

    # =========================
    # 2. NORMALISATION (IMPORTANT)
    # =========================
    df["hash_md5"] = df["hash_md5"].astype(str)
    df["taille_octets"] = pd.to_numeric(df["taille_octets"], errors="coerce")

    # =========================
    # 3. DÉTECTION DES DOUBLONS
    # =========================
    cles_doublons = ["hash_md5", "taille_octets"]

    df["nb_occurrences"] = df.groupby(cles_doublons)["hash_md5"].transform("count")

    df["est_doublon_exact"] = df["nb_occurrences"] > 1

    df = df.sort_values("date_creation")

    df["rang_dans_groupe"] = (
        df.groupby(cles_doublons).cumcount() + 1
    )

    df["id_groupe_doublon"] = -1
    masque = df["est_doublon_exact"]

    df.loc[masque, "id_groupe_doublon"] = (
        df[masque].groupby(cles_doublons).ngroup()
    )

    df["id_groupe_doublon"] = df["id_groupe_doublon"].astype(int)

    # =========================
    # Statut lisible
    # =========================
    def statut_doublon(row):
        if not row["est_doublon_exact"]:
            return "Unique"
        elif row["rang_dans_groupe"] == 1:
            return "Original"
        else:
            return f"Doublon #{row['rang_dans_groupe'] - 1}"

    df["statut_doublon"] = df.apply(statut_doublon, axis=1)

    # =========================
    # 4. ANALYSES
    # =========================
    df_doublons = df[df["est_doublon_exact"]].sort_values(
        ["id_groupe_doublon", "rang_dans_groupe"]
    )

    resume = (
        df_doublons.groupby("id_groupe_doublon")
        .agg(
            nb_fichiers=("chemin", "count"),
            taille_octets=("taille_octets", "first"),
            taille_lisible=("taille_lisible", "first"),
            extension=("extension", "first"),
            hash_md5=("hash_md5", "first"),
            chemins=("chemin", lambda x: " | ".join(x.astype(str).tolist())),
        )
        .reset_index()
    )

    resume["espace_gaspille_octets"] = (
        resume["taille_octets"] * (resume["nb_fichiers"] - 1)
    )

    resume["espace_gaspille_lisible"] = resume["espace_gaspille_octets"].apply(
        lambda t: f"{round(t / (1024 * 1024), 2)} MB"
    )

    # =========================
    # 5. EXPORT CSV
    # =========================
    df.to_csv(fichier, index=False)

    log("\n✅ Fichier CSV mis à jour directement")
    log(f"✅ Nombre final de fichiers : {len(df)}")

    # =========================
    # 6. Résumé console
    # =========================
    originaux = (df["statut_doublon"] == "Original").sum()

    log("\n✅ Détection terminée")
    log(f"   → Fichiers uniques     : {(df['statut_doublon'] == 'Unique').sum()}")
    log(f"   → Originaux            : {originaux}")
    log(f"   → Doublons exacts      : {df['est_doublon_exact'].sum() - originaux}")
    log(f"   → Groupes de doublons  : {df[df['est_doublon_exact']]['id_groupe_doublon'].nunique()}")

    log(f"\n   → Total doublons détectés : {len(df_doublons)}")
    log(
        f"   → Espace disque gaspillé : "
        f"{round(resume['espace_gaspille_octets'].sum() / (1024 * 1024), 2)} MB"
    )
    return df