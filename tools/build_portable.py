"""Monta o ZIP Windows x64 a partir de fontes permitidas e downloads fixados.

Execute com um Python que tenha pip. Nenhum ambiente virtual, histórico, .env
ou perfil do computador de desenvolvimento entra no pacote.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = {
    "python-3.13.16-embed-amd64.zip": (
        "https://www.python.org/ftp/python/3.13.16/python-3.13.16-embed-amd64.zip",
        "97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297", "runtime"),
    "chrome-headless-shell-win64.zip": (
        "https://storage.googleapis.com/chrome-for-testing-public/155.0.8059.84/win64/chrome-headless-shell-win64.zip",
        "5ca590a4968864e219ea25ccd134597ef8898a733a4698c07fc3e8b2c480fef4", "browser"),
    "chromedriver-win64.zip": (
        "https://storage.googleapis.com/chrome-for-testing-public/155.0.8059.84/win64/chromedriver-win64.zip",
        "0e629a3ef7f2be8562b857253053ebb0f871f55240f80124cd31974380ad1f3a", "browser"),
}


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    base = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            if not (base / entry.filename).resolve().is_relative_to(base):
                raise ValueError("Caminho inválido no arquivo baixado.")
        package.extractall(destination)


def build(cache, output):
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    bundle = output / "AuditaLGPD-Portable"
    archive = output / "AuditaLGPD-Portable-Windows-x64.zip"
    if bundle.exists() or archive.exists():
        raise SystemExit("Escolha uma pasta de saída nova; o gerador não apaga pacotes anteriores.")
    bundle.mkdir()
    for filename, (url, expected, folder) in ARTIFACTS.items():
        path = cache / filename
        if not path.exists():
            print("Baixando " + filename, flush=True)
            urllib.request.urlretrieve(url, path)
        if sha256(path) != expected:
            raise SystemExit("Checksum divergente: " + filename + ". Nenhum componente foi executado.")
        extract(path, bundle / folder)

    wheels = cache / "wheels-cp313-win64"
    wheels.mkdir(exist_ok=True)
    target_args = ["--python-version", "3.13", "--platform", "win_amd64", "--implementation", "cp", "--abi", "cp313", "--only-binary=:all:"]
    pins = ["-r", str(REPO / "requirements-lock.txt"), "colorama==0.4.6"]
    subprocess.run([sys.executable, "-m", "pip", "--isolated", "download", *target_args, *pins,
                    "--index-url", "https://pypi.org/simple", "--dest", str(wheels)], check=True)
    subprocess.run([sys.executable, "-m", "pip", "--isolated", "install", *target_args, *pins,
                    "--no-index", "--find-links", str(wheels), "--no-compile", "--no-warn-script-location",
                    "--target", str(bundle / "runtime/Lib/site-packages")], check=True)
    # Entry points do pip apontam para o Python do gerador. O portátil só usa
    # seu launcher e não distribui esses executáveis auxiliares sem utilidade.
    scripts = bundle / "runtime/Lib/site-packages/bin"
    if scripts.exists():
        assert scripts.resolve().is_relative_to(bundle.resolve())
        shutil.rmtree(scripts)
    (bundle / "runtime/python313._pth").write_text("python313.zip\n.\nLib/site-packages\n../app\n", encoding="ascii")

    source = REPO / "auditalgpd"
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if not path.is_file() or "__pycache__" in relative.parts:
            continue
        if path.suffix not in {".py", ".html", ".css", ".js"}:
            continue
        target = bundle / "app/auditalgpd" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    shutil.copyfile(REPO / "tools/portable/INICIAR.cmd", bundle / "INICIAR.cmd")
    shutil.copyfile(REPO / "tools/portable/LEIA-ME.txt", bundle / "LEIA-ME.txt")
    shutil.copyfile(REPO / "LICENSE", bundle / "LICENSE-AuditaLGPD.txt")
    shutil.copyfile(REPO / "requirements-lock.txt", bundle / "requirements-lock.txt")
    (bundle / "dados").mkdir()
    (bundle / "LICENCAS.txt").write_text(
        "AuditaLGPD: LICENSE-AuditaLGPD.txt (MIT).\n"
        "Python: runtime/LICENSE.txt.\n"
        "Bibliotecas Python: licenças e avisos mantidos em runtime/Lib/site-packages, nos respectivos *.dist-info e pacotes.\n"
        "Navegador Chromium Headless Shell: browser/chrome-headless-shell-win64/LICENSE.headless_shell e ABOUT.\n"
        "ChromeDriver: browser/chromedriver-win64/LICENSE.chromedriver e THIRD_PARTY_NOTICES.chromedriver.\n"
        "Fontes Vera: runtime/Lib/site-packages/reportlab/fonts/bitstream-vera-license.txt.\n"
        "Estes componentes possuem suas próprias licenças; a licença MIT do aplicativo não as substitui.\n",
        encoding="utf-8")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    manifest = {
        "application": "AuditaLGPD", "version": "0.2.0-portable.1", "platform": "Windows 10/11 x64",
        "built_at": datetime.now(timezone.utc).isoformat(), "source_revision": revision,
        "python": "3.13.16", "browser": "Chromium Headless Shell 155.0.8059.84",
        "artifacts": {name: {"url": url, "sha256": digest} for name, (url, digest, _) in ARTIFACTS.items()},
        "wheels": {p.name: sha256(p) for p in sorted(wheels.glob("*.whl"))},
        "files": {p.relative_to(bundle).as_posix(): sha256(p) for p in sorted(bundle.rglob("*")) if p.is_file()},
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Compactando pacote...", flush=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(output))
        package.writestr("AuditaLGPD-Portable/dados/", "")
    checksum = sha256(archive)
    archive.with_suffix(".zip.sha256").write_text(checksum + "  " + archive.name + "\n", encoding="ascii")
    print(f"Pacote criado: {archive}\nSHA256: {checksum}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=REPO / "build/downloads")
    parser.add_argument("--output", type=Path, default=REPO / "dist")
    options = parser.parse_args()
    build(options.cache.resolve(), options.output.resolve())
