"""Validação manual opt-in com sites reais; não faz parte da suíte offline.

Sobe a aplicação com um histórico temporário (o histórico do usuário não é
tocado), preenche o formulário pelo Edge como um usuário faria e salva, para
cada site e modalidade: print da página de resultado, PDF, captura feita pela
aplicação e um resumo JSON. Requer internet e Edge instalado.

Uso:
    python tools/validar_sites_reais.py SAIDA --site grupo=URL [--site grupo=URL ...]
           [--modos static browser]
"""

import argparse
import json
import logging
import re
import tempfile
import threading
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from werkzeug.serving import make_server

from auditalgpd import create_app
from auditalgpd.reports import generate_pdf

MODOS = {"static": "simples", "browser": "avancada"}


def slug(url):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"^https?://(www\.)?", "", url.lower())).strip("-")[:40]


def visible_alerts(driver):
    return [a.text for a in driver.find_elements(By.CSS_SELECTOR, ".alert.error") if a.is_displayed() and a.text.strip()]


def full_page_screenshot(driver, path):
    height = driver.execute_script("return document.documentElement.scrollHeight")
    driver.set_window_size(1366, min(height + 120, 9000))
    time.sleep(0.4)
    driver.save_screenshot(str(path))
    driver.set_window_size(1366, 900)


def run_one(driver, base, app, out, group, url, mode):
    name = f"{group}-{slug(url)}-{MODOS[mode]}"
    row = {"grupo": group, "url": url, "modalidade": MODOS[mode], "arquivo_base": name}
    driver.get(base + "/")
    driver.find_element(By.ID, "url").send_keys(url)
    Select(driver.find_element(By.ID, "mode")).select_by_value(mode)
    # O rótulo estilizado cobre a caixa; o clique via JS equivale ao do usuário no rótulo.
    driver.execute_script("arguments[0].click()", driver.find_element(By.NAME, "authorized"))
    driver.execute_script("arguments[0].click()", driver.find_element(By.ID, "submit-audit"))
    started = time.monotonic()
    try:
        WebDriverWait(driver, 200, poll_frequency=1, ignored_exceptions=[StaleElementReferenceException]).until(
            lambda d: re.search(r"/auditorias/[^/]+$", d.current_url) or visible_alerts(d))
    except Exception as exc:  # noqa: BLE001 - registrar qualquer falha da UI
        row["erro"] = f"Tempo esgotado na interface: {type(exc).__name__}"
    row["tempo_total_s"] = round(time.monotonic() - started, 1)
    time.sleep(1)
    full_page_screenshot(driver, out / f"{name}.png")
    match = re.search(r"/auditorias/([^/]+)$", driver.current_url)
    if not match:
        row.setdefault("erro", " | ".join(visible_alerts(driver)) or "Resultado não gerado")
        return row
    audit = app.extensions["repository"].get(match.group(1))
    score = audit.score
    row.update({
        "url_final": audit.final_url, "duracao_coleta_ms": audit.duration_ms,
        "nota": score.get("grade"), "pontos": score.get("value"), "cobertura": score.get("coverage"),
        "identificados": score.get("identified"),
        "categorias": {c["name"]: c["percent"] for c in score.get("categories", [])},
        "verificacoes": {c.key: c.status for c in audit.checks},
        "cookies_antes_interacao": len(audit.browser.get("cookies", [])) if audit.browser else None,
    })
    pdf = generate_pdf(audit)
    (out / f"{name}.pdf").write_bytes(pdf.getvalue() if hasattr(pdf, "getvalue") else pdf)
    shot = audit.browser.get("screenshot") if audit.browser else None
    if shot:
        import base64
        (out / f"{name}-captura.png").write_bytes(base64.b64decode(shot) if isinstance(shot, str) else shot)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("saida", type=Path)
    parser.add_argument("--site", action="append", required=True, help="grupo=URL")
    parser.add_argument("--modos", nargs="+", default=["static", "browser"], choices=list(MODOS))
    args = parser.parse_args()
    out = args.saida.resolve()
    out.mkdir(parents=True, exist_ok=True)

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    instance = tempfile.mkdtemp(prefix="auditalgpd-validacao-")
    app = create_app(instance_path=instance)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    options = webdriver.EdgeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1366,900")
    options.add_argument(f"--user-data-dir={tempfile.mkdtemp(prefix='auditalgpd-ui-')}")
    driver = webdriver.Edge(options=options)
    results = []
    try:
        for item in args.site:
            group, url = item.split("=", 1)
            for mode in args.modos:
                print(f"> {group} {url} [{MODOS[mode]}]", flush=True)
                try:
                    row = run_one(driver, base, app, out, group, url, mode)
                except Exception as exc:  # noqa: BLE001 - seguir para o próximo site
                    row = {"grupo": group, "url": url, "modalidade": MODOS[mode], "erro": f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"}
                results.append(row)
                print("  ", {k: row.get(k) for k in ("nota", "pontos", "cobertura", "erro")}, flush=True)
                (out / "resultados.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        driver.quit()
        server.shutdown()


if __name__ == "__main__":
    main()
