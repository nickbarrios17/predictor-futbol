# model/match_context.py — v1.2
"""
Representa el contexto del partido a predecir.

Cambios v1.2:
  - lineup_status_a/b ahora afecta el lambda del partido a predecir,
    no solo el peso de partidos historicos. Antes la IA detectaba
    bajas/rotacion desde las noticias y esa info solo aparecia en el
    texto narrativo de Gemini, sin tocar las probabilidades del
    modelo estadistico.

Cambios v1.1:
  - H2H reducido de 20% a 5% (FIX Problema 3).
  - H2H solo se aplica si hay >= H2H_MIN_MATCHES partidos
    en los últimos H2H_MAX_YEARS años.
  - FIX Bug 2: sin redondeo interno en h2h_adjustment.
"""
from datetime import date, datetime
from config import (MATCH_INTENSITY, TEAM_MOTIVATION, LINEUP_WEIGHT,
                    H2H_WEIGHT, H2H_MIN_MATCHES, H2H_MAX_YEARS)


class MatchContext:

    def __init__(
        self,
        competition:      str   = "Unknown",
        stage:            str   = "league_normal",
        motivation_a:     str   = "normal",
        motivation_b:     str   = "normal",
        lineup_status_a:  str   = "unknown",
        lineup_status_b:  str   = "unknown",
        h2h_matches:      list  = None,
        is_second_leg:    bool  = False,
        first_leg_score:  tuple = None,
        notes:            str   = "",
        confidence:       str   = "low",
    ):
        self.competition     = competition
        self.stage           = stage
        self.motivation_a    = motivation_a
        self.motivation_b    = motivation_b
        self.lineup_status_a = lineup_status_a
        self.lineup_status_b = lineup_status_b
        self.h2h_matches     = h2h_matches or []
        self.is_second_leg   = is_second_leg
        self.first_leg_score = first_leg_score
        self.notes           = notes
        self.confidence      = confidence

    def intensity(self) -> float:
        return MATCH_INTENSITY.get(self.stage, 1.00)

    def motivation_factor(self, team: str) -> float:
        mot = self.motivation_a if team == "a" else self.motivation_b
        return TEAM_MOTIVATION.get(mot, 1.00)

    def lineup_factor(self, team: str) -> float:
        """
        Penaliza el lambda del equipo si las noticias indican que va
        a jugar rotado/con reservas. Si el estado es desconocido no
        se aplica ningun ajuste (factor 1.0) — no hay que penalizar
        por falta de informacion, que es el caso mas comun.
        """
        status = self.lineup_status_a if team == "a" else self.lineup_status_b
        if not status or status == "unknown":
            return 1.00
        return LINEUP_WEIGHT.get(status, 1.00)

    def second_leg_adjustment(self) -> tuple[float, float]:
        if not self.is_second_leg or not self.first_leg_score:
            return 1.0, 1.0
        ga, gb = self.first_leg_score
        diff   = ga - gb
        if   diff >=  2: return 0.88, 1.15
        elif diff ==  1: return 0.93, 1.08
        elif diff ==  0: return 1.00, 1.00
        elif diff == -1: return 1.08, 0.93
        else:            return 1.15, 0.88

    def _h2h_validos(self) -> list:
        """
        Filtra los partidos H2H por antigüedad.
        Solo usa los de los últimos H2H_MAX_YEARS años.
        """
        if not self.h2h_matches:
            return []

        cutoff = date.today().replace(
            year=date.today().year - H2H_MAX_YEARS
        )
        validos = []
        for m in self.h2h_matches:
            try:
                fecha_str = m.get("date", "")
                if fecha_str:
                    fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                else:
                    # Si no tiene fecha, asumir que es válido
                    validos.append(m)
                    continue
                if fecha >= cutoff:
                    validos.append(m)
            except (ValueError, TypeError):
                validos.append(m)

        return validos

    def h2h_adjustment(self, lam_a: float,
                        lam_b: float) -> tuple[float, float]:
        """
        FIX Problema 3:
        - Solo aplica si hay >= H2H_MIN_MATCHES partidos válidos.
        - Solo usa H2H de los últimos H2H_MAX_YEARS años.
        - Peso reducido de 20% a 5%.
        - Sin redondeo interno (Bug 2).
        """
        h2h = self._h2h_validos()

        if len(h2h) < H2H_MIN_MATCHES:
            # No hay suficientes H2H recientes → ignorar completamente
            if h2h:
                print(f"  ℹ️  H2H ignorado: {len(h2h)} partidos "
                      f"(mínimo {H2H_MIN_MATCHES})")
            return lam_a, lam_b

        avg_a = sum(m.get("goals_a", 0) for m in h2h) / len(h2h)
        avg_b = sum(m.get("goals_b", 0) for m in h2h) / len(h2h)

        w = H2H_WEIGHT   # 0.05
        lam_a_adj = (1 - w) * lam_a + w * avg_a
        lam_b_adj = (1 - w) * lam_b + w * avg_b

        print(f"  ℹ️  H2H aplicado: {len(h2h)} partidos | "
              f"peso: {w*100:.0f}% | "
              f"avg goles: {avg_a:.2f}-{avg_b:.2f}")

        # Sin redondear internamente (Bug 2)
        return lam_a_adj, lam_b_adj

    def summary(self) -> dict:
        h2h_validos = self._h2h_validos()
        return {
            "competition":    self.competition,
            "stage":          self.stage,
            "intensity":      self.intensity(),
            "motivation_a":   self.motivation_a,
            "motivation_b":   self.motivation_b,
            "lineup_status_a":self.lineup_status_a,
            "lineup_status_b":self.lineup_status_b,
            "second_leg":     self.is_second_leg,
            "h2h_total":      len(self.h2h_matches),
            "h2h_validos":    len(h2h_validos),
            "h2h_aplicado":   len(h2h_validos) >= H2H_MIN_MATCHES,
            "confidence":     self.confidence,
            "notes":          self.notes,
        }
