# backtesting/metrics.py — v2.0
"""
Cálculo de métricas de evaluación del modelo.

Métricas implementadas:
  - Accuracy 1X2
  - Brier Score (calibración probabilística)
  - Log Loss (penaliza confianza incorrecta)
  - Accuracy Over 2.5
  - Accuracy BTTS
  - Accuracy marcador exacto
  - Precisión por tipo de resultado (home/draw/away)
"""
import math
from typing import Optional


def calcular_metricas(
    prob_home:   float,
    prob_draw:   float,
    prob_away:   float,
    over25_prob: float,
    btts_prob:   float,
    real_home:   int,
    real_away:   int,
    top_scores:  list = None,
) -> dict:
    """
    Calcula todas las métricas para una predicción vs resultado real.

    Las probabilidades vienen en % (0-100).
    """
    # Convertir a 0-1
    p_h = prob_home / 100
    p_d = prob_draw / 100
    p_a = prob_away / 100
    p_o = over25_prob / 100
    p_b = btts_prob   / 100

    # Resultado real
    if real_home > real_away:   actual = "home"
    elif real_home < real_away: actual = "away"
    else:                       actual = "draw"

    # Resultado predicho (máxima probabilidad)
    if prob_home >= prob_draw and prob_home >= prob_away:
        predicted = "home"
    elif prob_away >= prob_home and prob_away >= prob_draw:
        predicted = "away"
    else:
        predicted = "draw"

    # ── 1. Brier Score ─────────────────────────────────────────
    # Mide la calibración: qué tan cerca estuvieron las
    # probabilidades del resultado real.
    # Rango normalizado: 0 (perfecto) a 0.667 (peor posible).
    # Referencia: modelo sin info = 0.333 (33% a cada resultado).
    o_h = 1.0 if actual == "home" else 0.0
    o_d = 1.0 if actual == "draw" else 0.0
    o_a = 1.0 if actual == "away" else 0.0
    brier = ((p_h - o_h)**2 + (p_d - o_d)**2 + (p_a - o_a)**2) / 3

    # ── 2. Log Loss ────────────────────────────────────────────
    # Penaliza más cuando el modelo estaba confiado y se equivocó.
    # Menor = mejor. Referencia: modelo sin info = 1.099
    eps = 1e-9
    if actual == "home":   p_correct = p_h
    elif actual == "draw": p_correct = p_d
    else:                  p_correct = p_a
    log_loss_val = -math.log(max(p_correct, eps))

    # ── 3. Resultado 1X2 correcto ──────────────────────────────
    result_correct = predicted == actual

    # ── 4. Marcador exacto ─────────────────────────────────────
    score_correct = False
    if top_scores:
        top_score = top_scores[0][0]  # "2-1"
        try:
            ph_pred, pa_pred = top_score.split("-")
            score_correct = (int(ph_pred) == real_home and
                             int(pa_pred) == real_away)
        except (ValueError, AttributeError):
            pass

    # ── 5. Over 2.5 ───────────────────────────────────────────
    total_goles = real_home + real_away
    real_over25 = total_goles > 2.5
    pred_over25 = p_o >= 0.50
    over25_correct = real_over25 == pred_over25

    # ── 6. BTTS ───────────────────────────────────────────────
    real_btts = real_home > 0 and real_away > 0
    pred_btts = p_b >= 0.50
    btts_correct = real_btts == pred_btts

    return {
        "actual_result":    actual,
        "predicted_result": predicted,
        "result_correct":   result_correct,
        "score_correct":    score_correct,
        "over25_correct":   over25_correct,
        "btts_correct":     btts_correct,
        "brier_score":      round(brier,        4),
        "log_loss":         round(log_loss_val, 4),
        "total_goles":      total_goles,
        "real_over25":      real_over25,
        "real_btts":        real_btts,
    }


def resumen_metricas(resultados: list[dict],
                      label: str = "") -> dict:
    """
    Calcula las métricas agregadas de una lista de predicciones.
    """
    if not resultados:
        return {"error": "Sin resultados"}

    n = len(resultados)

    acc_1x2   = sum(1 for r in resultados if r["result_correct"])  / n
    acc_score = sum(1 for r in resultados if r["score_correct"])   / n
    acc_over  = sum(1 for r in resultados if r["over25_correct"])  / n
    acc_btts  = sum(1 for r in resultados if r["btts_correct"])    / n
    avg_brier = sum(r["brier_score"] for r in resultados) / n
    avg_logls = sum(r["log_loss"]    for r in resultados) / n

    # Precisión por tipo de resultado predicho
    home_preds = [r for r in resultados if r["predicted_result"] == "home"]
    draw_preds = [r for r in resultados if r["predicted_result"] == "draw"]
    away_preds = [r for r in resultados if r["predicted_result"] == "away"]

    prec_home = (sum(1 for r in home_preds if r["result_correct"]) /
                 len(home_preds) * 100) if home_preds else 0
    prec_draw = (sum(1 for r in draw_preds if r["result_correct"]) /
                 len(draw_preds) * 100) if draw_preds else 0
    prec_away = (sum(1 for r in away_preds if r["result_correct"]) /
                 len(away_preds) * 100) if away_preds else 0

    # Distribución de resultados reales
    real_home = sum(1 for r in resultados if r["actual_result"] == "home")
    real_draw = sum(1 for r in resultados if r["actual_result"] == "draw")
    real_away = sum(1 for r in resultados if r["actual_result"] == "away")

    resumen = {
        "label":              label or "Backtesting",
        "total_partidos":     n,
        # Accuracy
        "accuracy_1x2":       round(acc_1x2   * 100, 1),
        "accuracy_score":     round(acc_score  * 100, 1),
        "accuracy_over25":    round(acc_over   * 100, 1),
        "accuracy_btts":      round(acc_btts   * 100, 1),
        # Calibración
        "avg_brier_score":    round(avg_brier, 4),
        "avg_log_loss":       round(avg_logls, 4),
        # Referencia para interpretar
        "brier_referencia":   0.333,   # modelo sin información
        "logloss_referencia": 1.099,   # modelo sin información
        # Precisión por tipo
        "precision_home":     round(prec_home, 1),
        "precision_draw":     round(prec_draw, 1),
        "precision_away":     round(prec_away, 1),
        "n_pred_home":        len(home_preds),
        "n_pred_draw":        len(draw_preds),
        "n_pred_away":        len(away_preds),
        # Distribución real
        "real_home_pct":      round(real_home / n * 100, 1),
        "real_draw_pct":      round(real_draw / n * 100, 1),
        "real_away_pct":      round(real_away / n * 100, 1),
        # Detalle por partido
        "detalle":            resultados,
    }

    return resumen


def resumen_baselines(resultados: list[dict]) -> dict:
    """Resume los baselines guardados dentro de cada resultado de backtesting."""
    nombres = sorted({
        nombre
        for r in resultados
        for nombre in (r.get("baselines") or {}).keys()
    })
    resumen = {}
    for nombre in nombres:
        rows = [
            r["baselines"][nombre]
            for r in resultados
            if nombre in (r.get("baselines") or {})
        ]
        if rows:
            resumen[nombre] = resumen_metricas(rows, label=nombre)
    return resumen


def resumen_calibracion(
    resultados: list[dict],
    bins: list[tuple[int, int]] = None,
) -> list[dict]:
    """
    Agrupa predicciones por confianza del resultado elegido.

    Para cada partido toma la probabilidad del resultado predicho
    y compara esa confianza media contra el porcentaje real de aciertos.
    """
    bins = bins or [(0, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 101)]
    rows = []

    for low, high in bins:
        bucket = []
        for r in resultados:
            conf = _confidence_for_prediction(r)
            if conf is None:
                continue
            upper_ok = conf < high if high < 101 else conf <= 100
            if conf >= low and upper_ok:
                bucket.append((conf, bool(r.get("result_correct"))))

        if not bucket:
            continue

        n = len(bucket)
        avg_conf = sum(conf for conf, _ in bucket) / n
        hit_rate = sum(1 for _, ok in bucket if ok) / n * 100
        diff = hit_rate - avg_conf

        rows.append({
            "rango": f"{low}-{high if high < 101 else 100}%",
            "n": n,
            "confianza_media": round(avg_conf, 1),
            "acierto_real": round(hit_rate, 1),
            "diferencia": round(diff, 1),
            "estado": _calibration_status(diff),
        })

    return rows


def _confidence_for_prediction(row: dict) -> float | None:
    pred = row.get("predicted_result")
    if pred == "home":
        return row.get("prob_home")
    if pred == "draw":
        return row.get("prob_draw")
    if pred == "away":
        return row.get("prob_away")
    return None


def _calibration_status(diff: float) -> str:
    if diff <= -10:
        return "Sobreconfiado"
    if diff >= 10:
        return "Conservador"
    return "Razonable"


def comparar_versiones(metricas_v1: dict, metricas_v2: dict) -> dict:
    """
    Compara las métricas de dos versiones del modelo.
    Positivo = v2 mejoró, negativo = v2 empeoró.
    """
    if "error" in metricas_v1 or "error" in metricas_v2:
        return {"error": "Datos insuficientes para comparar"}

    campos = ["accuracy_1x2", "accuracy_over25", "accuracy_btts"]
    mejoras = {}
    for campo in campos:
        delta = metricas_v2.get(campo, 0) - metricas_v1.get(campo, 0)
        mejoras[campo] = round(delta, 1)

    # Brier y LogLoss: menor es mejor → delta negativo es bueno
    delta_brier = metricas_v2.get("avg_brier_score", 0) - metricas_v1.get("avg_brier_score", 0)
    delta_log   = metricas_v2.get("avg_log_loss",   0) - metricas_v1.get("avg_log_loss",   0)
    mejoras["avg_brier_score"] = round(delta_brier, 4)
    mejoras["avg_log_loss"]    = round(delta_log,   4)

    return {
        "v1_label":   metricas_v1.get("label", "v1"),
        "v2_label":   metricas_v2.get("label", "v2"),
        "diferencias": mejoras,
        "v2_mejor_en": [k for k, v in mejoras.items()
                         if (v > 0 if k.startswith("acc") else v < 0)],
        "v2_peor_en":  [k for k, v in mejoras.items()
                         if (v < 0 if k.startswith("acc") else v > 0)],
    }
