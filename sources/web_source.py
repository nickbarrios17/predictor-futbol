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
    """Descarga una página y devuelve solo el texto visible."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=12, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ⚠️  No se pudo descargar {url}: {e}")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)[:max_chars]


def search_web(query: str, n: int = 3) -> list[str]:
    """
    Busca URLs con DuckDuckGo HTML (sin API key, completamente gratis).
    Fallback a googlesearch si está instalado.
    """
    urls = _search_duckduckgo(query, n)
    if urls:
        return urls

    # Fallback: googlesearch-python
    try:
        from googlesearch import search
        return list(search(query, num_results=n, lang="es", sleep_interval=1))
    except Exception:
        pass

    return []


def _search_duckduckgo(query: str, n: int = 3) -> list[str]:
    """
    Scraping del HTML de DuckDuckGo. Sin API key, siempre gratis.
    Funciona en cualquier entorno incluyendo Streamlit Cloud.
    """
    try:
        resp = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS,
            timeout=10,
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.select("a.result__url"):
            href = a.get("href", "")
            if href.startswith("http") and "duckduckgo" not in href:
                links.append(href)
            if len(links) >= n:
                break

        # Fallback: buscar en todos los links si el selector no encontró nada
        if not links:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http") and "duckduckgo" not in href:
                    links.append(href)
                if len(links) >= n:
                    break

        return links
    except Exception as e:
        print(f"  ⚠️  DuckDuckGo falló: {e}")
        return []


def fetch_multiple(urls: list[str], max_chars: int = 3000) -> str:
    """Descarga varias páginas y concatena el texto."""
    textos = [get_page_text(u, max_chars) for u in urls]
    validos = [t for t in textos if t]
    return "\n\n--- FUENTE ---\n\n".join(validos)


def get_match_news(query: str, n_urls: int = 3) -> str:
    """Busca noticias de un partido y devuelve el texto combinado."""
    urls = search_web(query, n=n_urls)
    if not urls:
        return ""
    return fetch_multiple(urls)
