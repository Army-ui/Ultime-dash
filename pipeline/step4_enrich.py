"""
ÉTAPE 4 — ENRICHISSEMENT / SEGMENTATION (dépôt, unité métier, propriétaire)
Logique strictement identique au script original fourni par l'utilisateur.
"""

import pandas as pd


def run_enrich(fichier="cleaned_file_metadata.csv", log_callback=None):

    def log(msg):
        print(msg)
        if log_callback:
            log_callback(msg)

    # =========================
    # 1. CHARGEMENT DU MÊME FICHIER
    # =========================
    df = pd.read_csv(fichier)

    log("✅ Fichier chargé")
    log(f"Taille : {df.shape}")

    if df.empty:
        log("⚠️ Aucune donnée à enrichir (dossier scanné vide).")
        for col in ["type_duplication", "id_groupe", "depot", "unite_metier", "proprietaire"]:
            df[col] = pd.Series(dtype="object")
        df.to_csv(fichier, index=False)
        return df

    # =========================
    # 2. MARQUER LES DOUBLONS EXACTS
    # =========================
    df["type_duplication"] = "Aucun"
    df.loc[df["est_doublon_exact"], "type_duplication"] = "Exact"

    df["id_groupe"] = ""
    df.loc[df["est_doublon_exact"], "id_groupe"] = (
        "EXACT_" + df["id_groupe_doublon"].astype(str)
    )

    # =========================
    # 3. SEGMENTATION
    # =========================
    def extraire_segment(chemin, position, defaut="Inconnu"):
        segments = [s for s in str(chemin).split("/") if s != ""]
        if len(segments) > position:
            return segments[position]
        return defaut

    df["depot"] = df["chemin"].apply(lambda x: extraire_segment(x, 0))
    df["unite_metier"] = df["chemin"].apply(lambda x: extraire_segment(x, 1))
    df["proprietaire"] = df["chemin"].apply(lambda x: extraire_segment(x, 2))

    log("✅ Colonnes ajoutées au DataFrame")

    # =========================
    # 4. ANALYSE (EN MÉMOIRE)
    # =========================
    df_exacts = df[df["est_doublon_exact"]]

    log(f"✅ Doublons exacts : {len(df_exacts)}")
    log(f"   → Fichiers uniques dupliqués : {df_exacts['chemin'].nunique()}")

    # =========================
    # 5. KPI
    # =========================
    kpis = {
        "fichiers_dupliques": df_exacts["chemin"].nunique(),
        "groupes_doublons": df_exacts["id_groupe"].nunique(),
        "espace_total_MB": round(df_exacts["taille_octets"].sum() / (1024 * 1024), 2),
        "nb_depots": df_exacts["depot"].nunique(),
        "nb_unites_metier": df_exacts["unite_metier"].nunique(),
    }

    log("\n✅ KPI")
    for k, v in kpis.items():
        log(f"   → {k} : {v}")

    # =========================
    # 🔥 ANALYSE PAR DÉPÔT
    # =========================
    agg_depot = (
        df_exacts.groupby("depot")
        .agg(
            nb_fichiers=("chemin", "nunique"),
            nb_groupes=("id_groupe", "nunique"),
            espace_octets=("taille_octets", "sum"),
        )
        .reset_index()
        .sort_values("espace_octets", ascending=False)
    )

    log("\n🔥 TOP DEPOTS")
    log(str(agg_depot.head(10)))

    # =========================
    # 🔥 ANALYSE PAR UNITÉ MÉTIER
    # =========================
    agg_unite = (
        df_exacts.groupby("unite_metier")
        .agg(
            nb_fichiers=("chemin", "nunique"),
            espace_octets=("taille_octets", "sum"),
        )
        .reset_index()
        .sort_values("espace_octets", ascending=False)
    )

    log("\n🔥 TOP UNITÉS MÉTIER")
    log(str(agg_unite.head(10)))

    # =========================
    # 🔥 ANALYSE PAR EXTENSION
    # =========================
    agg_extension = (
        df_exacts.groupby("extension")
        .agg(
            nb_fichiers=("chemin", "nunique"),
            espace_octets=("taille_octets", "sum"),
        )
        .reset_index()
        .sort_values("espace_octets", ascending=False)
    )

    log("\n🔥 TOP EXTENSIONS")
    log(str(agg_extension.head(10)))

    # =========================
    # 6. ÉCRASEMENT DU FICHIER
    # =========================
    df.to_csv(fichier, index=False)

    log("\n✅ Fichier mis à jour : cleaned_file_metadata.csv")
    return df