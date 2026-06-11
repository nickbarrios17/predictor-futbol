# sources/web_source.py
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def get_page_text(url: str, max_chars: int = 4000) -> str:
    """
    Descarga una página y devuelve solo el texto visible,
    sin etiquetas HTML ni scripts.
    """
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=12,
                         follow_redirects=True)
        resp.raise_for_status()
    except Exception:
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav",
                     "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # Limitar para no gastar demasiado en tokens de la IA
    return text[:max_chars]


def search_web(query: str, n: int = 3) -> list[str]:
    """
    Busca en Google y devuelve las primeras N URLs.
    Usa googlesearch-python que es completamente gratis.
    """
    try:
        from googlesearch import search
        return list(search(query, num_results=n, lang="es",
                           sleep_interval=1))
    except Exception:
        return []


def fetch_multiple(urls: list[str],
                   max_chars: int = 3000) -> str:
    """
    Descarga varias páginas y concatena el texto.
    Útil para pasarle a la IA más de una fuente.
    """
    textos = []
    for url in urls:
        text = get_page_text(url, max_chars=max_chars)
        if text:
            textos.append(text)
    return "\n\n--- FUENTE ---\n\n".join(textos)