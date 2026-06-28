"""
Dictionnaire de traductions pour l'interface (FR / EN).
Utilisé par les callbacks pour régénérer les libellés dynamiquement.
"""

TRANSLATIONS = {
    "fr": {
        "app_title": "Scanner de Doublons",
        "app_subtitle": "Analyse des doublons uniquement",
        "scanning_title": "Analyse en cours",
        "scanning_subtitle": "Exécution du pipeline en arrière-plan…",
        "step_scan": "Scan",
        "step_clean": "Nettoyage",
        "step_detect": "Détection",
        "step_enrich": "Enrichissement",
        "step_done": "Terminé",
        "kpi_total": "Doublons total",
        "kpi_exact": "Doublons exacts",
        "kpi_groups": "Groupes",
        "kpi_space": "Espace récupérable",
        "filter_depot": "Dépôt",
        "filter_extension": "Extension",
        "chart_top_ext": "Top Extensions (doublons)",
        "chart_status": "Répartition Statut",
        "chart_top_depot": "Top Dépôts (doublons)",
        "chart_top_group": "Top Groupes",
        "btn_export": "Exporter PDF",
        "btn_archive_selected": "Archiver la sélection",
        "btn_delete_selected": "Supprimer la sélection",
        "table_title": "Liste des doublons",
        "col_name": "Nom",
        "col_path": "Chemin",
        "col_size": "Taille",
        "col_status": "Statut",
        "col_to_delete": "À supprimer",
        "col_delete": "🗑️ Supprimer",
        "col_archive": "📦 Archiver",
        "selected_count": "sélectionné(s)",
        "modal_delete_title": "Confirmer la suppression",
        "modal_delete_body": "Le fichier suivant sera supprimé définitivement du disque :",
        "modal_archive_title": "Confirmer l'archivage",
        "modal_archive_body": "Le fichier suivant sera déplacé vers le dossier d'archive :",
        "modal_confirm": "Confirmer",
        "modal_cancel": "Annuler",
        "toast_deleted": "Fichier supprimé avec succès",
        "toast_archived": "Fichier archivé avec succès",
        "toast_error": "Erreur lors de l'opération",
        "no_duplicates": "Aucun doublon détecté 🎉",
        "theme_dark": "Sombre",
        "theme_light": "Clair",
        "lang_label": "FR",
    },
    "en": {
        "app_title": "Duplicate Scanner",
        "app_subtitle": "Duplicate-only analysis",
        "scanning_title": "Scan in progress",
        "scanning_subtitle": "Running the pipeline in the background…",
        "step_scan": "Scan",
        "step_clean": "Clean",
        "step_detect": "Detect",
        "step_enrich": "Enrich",
        "step_done": "Done",
        "kpi_total": "Total duplicates",
        "kpi_exact": "Exact duplicates",
        "kpi_groups": "Groups",
        "kpi_space": "Recoverable space",
        "filter_depot": "Repository",
        "filter_extension": "Extension",
        "chart_top_ext": "Top extensions (duplicates)",
        "chart_status": "Status breakdown",
        "chart_top_depot": "Top repositories (duplicates)",
        "chart_top_group": "Top groups",
        "btn_export": "Export PDF",
        "btn_archive_selected": "Archive selection",
        "btn_delete_selected": "Delete selection",
        "table_title": "Duplicate files",
        "col_name": "Name",
        "col_path": "Path",
        "col_size": "Size",
        "col_status": "Status",
        "col_to_delete": "To delete",
        "col_delete": "🗑️ Delete",
        "col_archive": "📦 Archive",
        "selected_count": "selected",
        "modal_delete_title": "Confirm deletion",
        "modal_delete_body": "The following file will be permanently deleted from disk:",
        "modal_archive_title": "Confirm archiving",
        "modal_archive_body": "The following file will be moved to the archive folder:",
        "modal_confirm": "Confirm",
        "modal_cancel": "Cancel",
        "toast_deleted": "File deleted successfully",
        "toast_archived": "File archived successfully",
        "toast_error": "An error occurred",
        "no_duplicates": "No duplicates detected 🎉",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "lang_label": "EN",
    },
}


def t(lang, key):
    """Récupère une traduction, avec repli sur le français puis sur la clé brute."""
    lang = lang if lang in TRANSLATIONS else "fr"
    return TRANSLATIONS[lang].get(key, TRANSLATIONS["fr"].get(key, key))


def detect_lang_from_header(accept_language_header):
    """
    Détecte la langue préférée à partir de l'en-tête HTTP Accept-Language
    envoyé automatiquement par le navigateur de l'utilisateur.
    Retourne 'fr' ou 'en'.
    """
    if not accept_language_header:
        return "fr"
    header = accept_language_header.lower()
    # Le navigateur envoie une liste pondérée, ex: "en-US,en;q=0.9,fr;q=0.8"
    # On regarde simplement quelle langue apparaît en premier.
    first_lang = header.split(",")[0].strip()
    if first_lang.startswith("fr"):
        return "fr"
    if first_lang.startswith("en"):
        return "en"
    # Pour toute autre langue du navigateur, on regarde si fr ou en apparaît avant l'autre
    fr_pos = header.find("fr")
    en_pos = header.find("en")
    if fr_pos == -1 and en_pos == -1:
        return "fr"
    if fr_pos == -1:
        return "en"
    if en_pos == -1:
        return "fr"
    return "fr" if fr_pos < en_pos else "en"