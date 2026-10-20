#!/usr/bin/env python3
"""
Baixa somente o SIM CID-10 do DataHub Brasil no Kaggle.

Requer:
  pip install kaggle
  ~/.kaggle/kaggle.json
ou variáveis KAGGLE_USERNAME / KAGGLE_KEY.
"""
from pathlib import Path
import os
import sys
import zipfile
import glob

DATASET_ID = "rafatrindade/brazilian-kaggle-datahub"
TARGET_BASENAME = "declaracoes_de_obito_cid10.parquet"
DEST = Path("data/raw")
OVERWRITE = False

def authenticate():
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError:
        sys.exit("Pacote 'kaggle' ausente. Rode: pip install -r requirements.txt")
    api = KaggleApi()
    try:
        api.authenticate()
    except Exception as e:
        sys.exit(
            "Falha na autenticação do Kaggle.\n"
            "Coloque kaggle.json em ~/.kaggle/kaggle.json ou defina "
            "KAGGLE_USERNAME/KAGGLE_KEY.\n"
            f"Erro original: {e}"
        )
    return api

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    api = authenticate()

    print(f"Listando arquivos de {DATASET_ID} ...")
    resp = api.dataset_list_files(DATASET_ID)
    available = [f.name for f in resp.files]

    matches = [n for n in available if Path(n).name == TARGET_BASENAME]
    if not matches:
        print("Arquivo-alvo não encontrado. Arquivos SIM disponíveis:")
        for n in sorted(x for x in available if "obito" in x.lower()):
            print("  ", n)
        sys.exit(2)
    if len(matches) > 1:
        print("Mais de um arquivo com o mesmo basename foi encontrado:")
        for n in matches:
            print("  ", n)
        sys.exit(3)

    remote_name = matches[0]
    dest_dir = DEST / Path(remote_name).parent
    dest_dir.mkdir(parents=True, exist_ok=True)
    final_path = DEST / remote_name

    if final_path.exists() and not OVERWRITE:
        print(f"Já existe: {final_path}")
        return

    print(f"Baixando {remote_name} ...")
    api.dataset_download_file(
        DATASET_ID,
        remote_name,
        path=str(dest_dir),
        force=OVERWRITE,
        quiet=False,
    )

    # Kaggle pode entregar o arquivo em ZIP.
    for z in glob.glob(str(DEST / "**" / "*.zip"), recursive=True):
        zpath = Path(z)
        try:
            with zipfile.ZipFile(zpath) as zf:
                zf.extractall(zpath.parent)
            zpath.unlink()
            print(f"Descompactado: {zpath}")
        except zipfile.BadZipFile:
            pass

    candidates = list(DEST.rglob(TARGET_BASENAME))
    if not candidates:
        sys.exit("Download terminou, mas o Parquet não foi localizado em data/raw.")
    print("Concluído:")
    for p in candidates:
        print(" ", p.resolve())

if __name__ == "__main__":
    main()