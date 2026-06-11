# data/fetcher.py
from sources.api_source import search_team, get_team_matches

def fetch_matches(team_name: str, team_type: str = "default") -> list[dict]:
    """
    Busca partidos en la API de SofaScore para un equipo dado.
    Incluye logs de debug para identificar problemas de conexión o falta de datos.
    """
    print(f"DEBUG: Consultando API para: {team_name}")
    
    # 1. Buscar equipos
    candidatos = search_team(team_name)
    
    if not candidatos:
        print(f"DEBUG: ¡Alerta! No se encontró ningún equipo llamado '{team_name}' en la API.")
        return []
    
    # 2. Tomamos el primer candidato (es el más relevante)
    equipo_encontrado = candidatos[0]
    id_encontrado = equipo_encontrado["id"]
    nombre_encontrado = equipo_encontrado["name"]
    
    print(f"DEBUG: Equipo '{team_name}' mapeado a '{nombre_encontrado}' con ID: {id_encontrado}")
    
    # 3. Obtener partidos
    matches = get_team_matches(id_encontrado)
    
    # 4. Validar cantidad de partidos
    if not matches:
        print(f"DEBUG: ¡Alerta! La API devolvió 0 partidos para el ID {id_encontrado}")
    else:
        print(f"DEBUG: Se obtuvieron {len(matches)} partidos válidos para el ID {id_encontrado}")
    
    return matches