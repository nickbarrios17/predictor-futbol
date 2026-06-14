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

# Dominios que bloquean scraping o no tienen contenido útil
BLOCKED_DOMAINS = [
    "duckduckgo.com", "google.com", "facebook.com",
    "twitter.com", "instagram.com", "tiktok.com",
    "youtube.com", "reddit.com",
]


def get_page_text(url: str, max_chars: int = 4000) -> str:
    """Descarga una página y devuelve solo el texto visible."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=12,
                         follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print(f"    ⚠️  No se pudo descargar {url[:60]}: {e}")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer",
                     "header", "aside", "iframe"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    # Limpiar líneas vacías múltiples
    lines  = [l.strip() for l in text.splitlines() if l.strip()]
    result = "\n".join(lines)
    print(f"    ✅  {url[:60]} → {len(result)} chars")
    return result[:max_chars]


def search_web(query: str, n: int = 3) -> list[str]:
    """
    Intenta varias estrategias de búsqueda en orden.
    Todas son gratuitas y sin API key.
    """
    print(f"  🔍 Buscando: '{query}'")

    # 1. DuckDuckGo HTML (más confiable)
    urls = _search_duckduckgo(query, n)
    if urls:
        print(f"  ✅ DuckDuckGo encontró {len(urls)} URLs")
        return urls

    # 2. DuckDuckGo Lite (versión más simple, menos bloqueada)
    urls = _search_duckduckgo_lite(query, n)
    if urls:
        print(f"  ✅ DuckDuckGo Lite encontró {len(urls)} URLs")
        return urls

    # 3. googlesearch-python como último recurso
    urls = _search_google_fallback(query, n)
    if urls:
        print(f"  ✅ Google encontró {len(urls)} URLs")
        return urls

    print("  ❌ Ninguna fuente de búsqueda funcionó")
    return []


def _is_valid_url(href: str) -> bool:
    """Filtra URLs inútiles o bloqueadas."""
    if not href or not href.startswith("http"):
        return False
    return not any(d in href for d in BLOCKED_DOMAINS)


def _search_duckduckgo(query: str, n: int) -> list[str]:
    """Scraping del HTML principal de DuckDuckGo."""
    try:
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "b": "", "kl": "es-es"},
            headers=HEADERS,
            timeout=12,
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup  = BeautifulSoup(resp.text, "html.parser")
        links = []

        # Selectores en orden de prioridad según versión del HTML
        for selector in [
            "a.result__a",           # links principales de resultados
            ".result__title a",      # título del resultado
            "h2 a",                  # títulos en h2
            ".web-result a",         # resultados web genéricos
        ]:
            for a in soup.select(selector):
                href = a.get("href", "")
                # DuckDuckGo a veces envuelve con redirect
                if "uddg=" in href:
                    from urllib.parse import unquote, urlparse, parse_qs
                    try:
                        parsed = urlparse(href)
                        href   = unquote(parse_qs(parsed.query).get("uddg", [""])[0])
                    except Exception:
                        pass
                if _is_valid_url(href) and href not in links:
                    links.append(href)
                if len(links) >= n:
                    return links

        return links
    except Exception as e:
        print(f"    DuckDuckGo HTML falló: {e}")
        return []


def _search_duckduckgo_lite(query: str, n: int) -> list[str]:
    """DuckDuckGo Lite: versión ultra-simple, más difícil de bloquear."""
    try:
        resp = httpx.get(
            "https://lite.duckduckgo.com/lite/",
            params={"q": query},
            headers=HEADERS,
            timeout=12,
            follow_redirects=True,
        )
        resp.raise_for_status()
        soup  = BeautifulSoup(resp.text, "html.parser")
        links = []

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if _is_valid_url(href) and href not in links:
                links.append(href)
            if len(links) >= n:
                break

        return links
    except Exception as e:
        print(f"    DuckDuckGo Lite falló: {e}")
        return []


def _search_google_fallback(query: str, n: int) -> list[str]:
    """googlesearch-python como último recurso."""
    try:
        from googlesearch import search
        return list(search(query, num_results=n,
                           lang="es", sleep_interval=2))
    except Exception as e:
        print(f"    Google fallback falló: {e}")
        return []


def fetch_multiple(urls: list[str], max_chars: int = 3000) -> str:
    """Descarga varias páginas y concatena el texto."""
    textos = []
    for url in urls:
        t = get_page_text(url, max_chars)
        if t:
            textos.append(t)
    return "\n\n--- FUENTE ---\n\n".join(textos)


def get_match_news(team_a: str, team_b: str,
                   competition: str = "",
                   n_urls: int = 3) -> str:
    """
    Busca noticias específicas de un partido.
    Construye la query con ambos equipos Y la competición.
    """
    # Query con competición incluida si la hay
    if competition:
        query = f"{team_a} vs {team_b} {competition} preview lineup news"
    else:
        query = f"{team_a} vs {team_b} match preview lineup news 2026"

    print(f"  📰 Query de noticias: '{query}'")
    urls = search_web(query, n=n_urls)

    if not urls:
        print("  ⚠️  Sin URLs encontradas para noticias")
        return ""

    texto = fetch_multiple(urls, max_chars=3000)
    print(f"  📄 Total noticias: {len(texto)} caracteres")
    return texto
