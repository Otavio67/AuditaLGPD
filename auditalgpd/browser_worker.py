"""Processo filho: nunca imprime conteúdo de páginas ou credenciais."""

import base64
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit
from .browser_proxy import public_proxy
from .security import AuditError, normalize_url


DOM_SNAPSHOT = r"""
const root = document.documentElement.cloneNode(true);
const originals = document.documentElement.querySelectorAll('*');
const copies = root.querySelectorAll('*');
for (let i=0; i<Math.min(originals.length, 12000); i++) {
  const style = getComputedStyle(originals[i]);
  if (style.display === 'none' || style.visibility === 'hidden') copies[i].setAttribute('hidden', '');
}
root.querySelectorAll('script,style,noscript,template').forEach(x => x.remove());
root.querySelectorAll('input').forEach(x => x.removeAttribute('value'));
root.querySelectorAll('textarea,[contenteditable]').forEach(x => x.textContent = '');
return root.outerHTML;
"""


def cookie_inventory(cookies):
    """Allowlist: valores/tokens nunca cruzam a fronteira do coletor."""
    return [{"name": str(c.get("name", ""))[:120], "domain": str(c.get("domain", ""))[:253],
             "secure": bool(c.get("secure")), "httpOnly": bool(c.get("httpOnly")),
             "sameSite": str(c.get("sameSite", "não informado")), "session": bool(c.get("session", False))}
            for c in cookies[:100]]


def frame_loaders(tree):
    result = {tree["frame"]["id"]: tree["frame"].get("loaderId")}
    for child in tree.get("childFrames", []):
        result.update(frame_loaders(child))
    return result


def page_network(events, frames, frame_id):
    """Descarta cabeçalhos/corpos e separa navegação de tráfego do navegador."""
    domains, main = set(), None
    for entry in events:
        try:
            message = json.loads(entry["message"])["message"]
            params = message["params"]
            if message["method"] == "Network.requestWillBeSent":
                if params.get("frameId") not in frames or params.get("loaderId") != frames[params["frameId"]]:
                    continue
                parsed = urlsplit(params["request"]["url"])
                if parsed.scheme in {"http", "https"} and parsed.hostname:
                    domains.add(parsed.hostname.lower())
            if message["method"] == "Network.responseReceived" and params.get("type") == "Document" and params.get("frameId") == frame_id and params.get("loaderId") == frames[frame_id]:
                main = params["response"]
        except (ValueError, KeyError, TypeError):
            continue
    return sorted(domains)[:80], main


def page_cookies(cookies, domains):
    return [c for c in cookies if any(host == c.get("domain", "").lstrip(".") or
                                      host.endswith("." + c.get("domain", "").lstrip("."))
                                      for host in domains)]


def start_driver(webdriver, options, browser):
    """O portátil usa binários fixos, sem procurar/baixar drivers no PC."""
    binary = os.environ.get("AUDITALGPD_BROWSER_BINARY")
    driver_path = os.environ.get("AUDITALGPD_BROWSER_DRIVER")
    if binary or driver_path:
        if browser != "chrome" or not binary or not driver_path or not Path(binary).is_file() or not Path(driver_path).is_file():
            raise AuditError("O navegador incluído está incompleto. Extraia novamente toda a pasta do aplicativo.")
        from selenium.webdriver.chrome.service import Service
        options.binary_location = binary
        environment = dict(os.environ)
        for argument in list(options.arguments):
            if argument.startswith("--user-data-dir="):
                # O Shell não abre a página inicial com perfil explícito.
                # ChromeDriver cria seu próprio perfil dentro do mesmo temporário,
                # que o processo pai remove inclusive após timeout/encerramento.
                temporary = str(Path(argument.split("=", 1)[1]).parent)
                environment.update(TEMP=temporary, TMP=temporary, TMPDIR=temporary)
                options.arguments.remove(argument)
        return webdriver.Chrome(service=Service(executable_path=driver_path, env=environment,
                                                driver_path_env_key="AUDITALGPD_BROWSER_DRIVER"), options=options)
    return webdriver.Edge(options=options) if browser == "edge" else webdriver.Chrome(options=options)


def collect(config):
    from selenium import webdriver
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException, WebDriverException
    browser = config.get("browser", "edge")
    if browser not in {"edge", "chrome"}:
        raise AuditError("Escolha Edge ou Chrome nas configurações locais.")
    options = webdriver.EdgeOptions() if browser == "edge" else webdriver.ChromeOptions()
    options.set_capability("ms:loggingPrefs" if browser == "edge" else "goog:loggingPrefs", {"performance": "ALL"})
    options.page_load_strategy = "eager"
    for argument in ["--headless=new", "--window-size=1365,900", "--disable-background-networking", "--disable-sync",
                     "--no-first-run", "--disable-default-apps", "--disable-quic", "--disable-extensions",
                     "--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--proxy-bypass-list=<-loopback>",
                     "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost", "--user-data-dir=" + config["profile"]]:
        options.add_argument(argument)
    options.add_experimental_option("prefs", {"credentials_enable_service": False, "profile.password_manager_enabled": False,
                                              "profile.default_content_setting_values.notifications": 2,
                                              "profile.default_content_setting_values.geolocation": 2,
                                              "download_restrictions": 3})
    timeout = min(55, config["timeout"])
    with public_proxy(lifetime=timeout) as proxy:
        options.add_argument(f"--proxy-server=http://127.0.0.1:{proxy.server_port}")
        driver = None
        try:
            driver = start_driver(webdriver, options, browser)
            driver.set_page_load_timeout(min(25, timeout))
            driver.set_script_timeout(5)
            driver.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "deny"})
            driver.execute_cdp_cmd("Network.clearBrowserCookies", {})
            driver.get_log("performance")
            try:
                driver.get(config["url"])
                WebDriverWait(driver, 8).until(lambda d: d.execute_script("return document.readyState") == "complete")
            except TimeoutException as exc:
                raise AuditError("A página não concluiu o carregamento no prazo. Conteúdo parcial não recebeu nota.") from exc
            final = normalize_url(driver.current_url)
            origin = config.get("origin")
            if origin and (final.scheme, final.host, final.port) != tuple(origin):
                raise AuditError("A política foi redirecionada para outra origem.")
            # Janela de observação limitada para inserções assíncronas após load.
            end = time.monotonic() + 3
            while time.monotonic() < end:
                time.sleep(.2)
            tree = driver.execute_cdp_cmd("Page.getFrameTree", {})["frameTree"]
            frame_id = tree["frame"]["id"]
            domains, response = page_network(driver.get_log("performance"), frame_loaders(tree), frame_id)
            if not response or not 200 <= response.get("status", 0) < 300:
                raise AuditError("A navegação não retornou uma página HTML com resposta HTTP de sucesso. Nenhuma nota foi inferida de uma página de erro.")
            if response.get("mimeType", "").lower() not in {"text/html", "application/xhtml+xml"}:
                raise AuditError("O navegador não recebeu uma página HTML.")
            html = driver.execute_script(DOM_SNAPSHOT)
            if not html or len(html.encode("utf-8")) > 2_000_000:
                raise AuditError("O DOM está vazio ou ultrapassa 2 MB.")
            # O navegador mantém a validação TLS padrão; erros de certificado interrompem get().
            if driver.title.lower().startswith(("privacy error", "erro de privacidade")):
                raise AuditError("O navegador não validou a conexão da página.")
            cookies = page_cookies(driver.execute_cdp_cmd("Storage.getCookies", {}).get("cookies", []), domains)
            screenshot = driver.get_screenshot_as_png()
            return {"url": final.url, "html": html, "tls_verified": final.scheme == "https",
                    "browser": {"name": browser, "version": driver.capabilities.get("browserVersion", ""),
                                "cookies": cookie_inventory(cookies), "domains": domains, "http_status": response["status"],
                                "blocked": proxy.blocked, "observation_seconds": 3,
                                "screenshot": base64.b64encode(screenshot).decode("ascii") if len(screenshot) <= 1_000_000 else ""}}
        except WebDriverException as exc:
            if os.environ.get("AUDITALGPD_BROWSER_BINARY"):
                raise AuditError("Não foi possível abrir o navegador incluído. Verifique se toda a pasta foi extraída e se o Windows permite executar seus componentes.") from exc
            raise AuditError("Não foi possível executar o navegador. Verifique o navegador instalado e o driver; a primeira execução precisa de internet para obtê-lo.") from exc
        finally:
            if driver:
                driver.quit()


def main():
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = collect(config)
    except AuditError as exc:
        result = {"error": str(exc)}
    except ImportError:
        result = {"error": "A análise avançada precisa dos componentes locais. Conclua a instalação descrita no guia do projeto."}
    except Exception:
        result = {"error": "O coletor dinâmico falhou. Nenhuma conclusão foi inferida para a página."}
    Path(config["output"]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
