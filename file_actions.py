"""
Actions réelles sur le système de fichiers : suppression et archivage.
Toute action est journalisée et protégée contre les erreurs (fichier déjà
déplacé, permissions, etc.) afin de ne jamais faire planter l'application.
"""

import os
import shutil
from datetime import datetime

ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archive_doublons")


def ensure_archive_dir():
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    return ARCHIVE_DIR


def delete_file(path):
    """Supprime définitivement un fichier du disque. Retourne (ok, message)."""
    try:
        if not os.path.exists(path):
            return False, "not_found"
        os.remove(path)
        return True, "deleted"
    except PermissionError:
        return False, "permission_denied"
    except OSError as e:
        return False, str(e)


def archive_file(path):
    """
    Déplace un fichier vers le dossier d'archive, en préservant un suffixe
    horodaté pour éviter toute collision de noms.
    Retourne (ok, message, nouveau_chemin_ou_None).
    """
    try:
        if not os.path.exists(path):
            return False, "not_found", None

        archive_dir = ensure_archive_dir()
        base_name = os.path.basename(path)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        name, ext = os.path.splitext(base_name)
        dest_name = f"{name}__{timestamp}{ext}"
        dest_path = os.path.join(archive_dir, dest_name)

        shutil.move(path, dest_path)
        return True, "archived", dest_path
    except PermissionError:
        return False, "permission_denied", None
    except OSError as e:
        return False, str(e), None