import numpy as np
from data.fetcher import fetch_matches
from datetime import datetime

def predecir(equipo_a, equipo_b, sede, competencia, tipo_equipo):
    # Obtener datos brutos
    matches_a = fetch_matches(equipo_a, tipo_equipo)
    matches_b = fetch_matches(equipo_b, tipo_equipo)

    def analizar_equipo(matches):
        audit_log = []
        hoy = datetime.now()
        # Pesos: Mayor importancia para torneos oficiales
        pesos_comp = {"Friendly": 0.7, "Nations League": 1.1, "World Cup": 1.3, "Qualifiers": 1.2, "Continental": 1.2}
        
        scores_ponderados = []
        concededs_ponderados = []
        pesos_totales = []

        for m in matches:
            # 1. Filtro: Excluir clubes
            if "Club" in m['competition'] or "Club" in m['team_home']:
                audit_log.append({"Partido": f"{m['team_home']} vs {m['team_away']}", "Estado": "DESCARTADO", "Razón": "Es partido de clubes"})
                continue
            
            # 2. Ponderación por importancia
            imp = next((v for k, v in pesos_comp.items() if k in m['competition']), 1.0)
            
            # 3. Decaimiento Temporal (0.99 elevado a los días transcurridos)
            dias = (hoy - datetime.strptime(m['date'], "%Y-%m-%d")).days
            time_decay = 0.99 ** dias
            total_weight = imp * time_decay
            
            # 4. Acumular
            scores_ponderados.append(m['goals_home'] * total_weight)
            concededs_ponderados.append(m['goals_away'] * total_weight)
            pesos_totales.append(total_weight)
            
            audit_log.append({
                "Partido": f"{m['team_home']} vs {m['team_away']}", 
                "Estado": "USADO", 
                "Peso": round(total_weight, 3)
            })

        # Evitar división por cero si no hay partidos válidos
        if not pesos_totales: return 0, 0, audit_log
        
        return np.sum(scores_ponderados) / np.sum(pesos_totales), np.sum(concededs_ponderados) / np.sum(pesos_totales), audit_log

    # Ejecutar análisis
    atk_a, def_a, log_a = analizar_equipo(matches_a)
    atk_b, def_b, log_b = analizar_equipo(matches_b)

    # Ajuste localía
    if sede == "local_a": atk_a *= 1.15; atk_b *= 0.90
    elif sede == "local_b": atk_a *= 0.90; atk_b *= 1.15

    # Lambdas Poisson
    lambda_a = (atk_a + def_b) / 2
    lambda_b = (atk_b + def_a) / 2

    # Simulación
    n = 10000
    goles_a = np.random.poisson(lambda_a, n)
    goles_b = np.random.poisson(lambda_b, n)
    
    marcadores, counts = np.unique(list(zip(goles_a, goles_b)), axis=0, return_counts=True)
    top_indices = np.argsort(counts)[-5:][::-1]
    
    return {
        "victoria_a": round(np.mean(goles_a > goles_b) * 100, 1),
        "empate": round(np.mean(goles_a == goles_b) * 100, 1),
        "victoria_b": round(np.mean(goles_a < goles_b) * 100, 1),
        "lambda_a": round(lambda_a, 2),
        "lambda_b": round(lambda_b, 2),
        "marcadores_probables": [{"Marcador": f"{marcadores[i][0]}-{marcadores[i][1]}", 
                                 "Probabilidad": f"{(counts[i]/n)*100:.1f}%"} for i in top_indices],
        "audit_a": log_a,
        "audit_b": log_b
    }