# model/match_context.py
"""
Representa el contexto del partido que se quiere predecir.
Calcula los multiplicadores que ajustan los lambdas finales.
"""
from config import MATCH_INTENSITY, TEAM_MOTIVATION, H2H_WEIGHT


class MatchContext:

    def __init__(
        self,
        competition:      str   = "Unknown",
        stage:            str   = "league_normal",
        motivation_a:     str   = "normal",
        motivation_b:     str   = "normal",
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

    def second_leg_adjustment(self) -> tuple[float, float]:
        """
        En partidos de vuelta ajusta los lambdas según
        el resultado de la ida.
        """
        if not self.is_second_leg or not self.first_leg_score:
            return 1.0, 1.0

        ga, gb = self.first_leg_score
        diff   = ga - gb

        # Cuanto más grande la diferencia, más extremo el ajuste
        if   diff >=  2: return 0.88, 1.15
        elif diff ==  1: return 0.93, 1.08
        elif diff ==  0: return 1.00, 1.00
        elif diff == -1: return 1.08, 0.93
        else:            return 1.15, 0.88

    def h2h_adjustment(self, lam_a: float,
                        lam_b: float) -> tuple[float, float]:
        """
        Mezcla los lambdas con el historial H2H.
        80% forma reciente + 20% H2H.
        """
        if not self.h2h_matches:
            return lam_a, lam_b

        avg_a = sum(m["goals_a"] for m in self.h2h_matches) \
                / len(self.h2h_matches)
        avg_b = sum(m["goals_b"] for m in self.h2h_matches) \
                / len(self.h2h_matches)

        w = H2H_WEIGHT
        return (
            round((1 - w) * lam_a + w * avg_a, 3),
            round((1 - w) * lam_b + w * avg_b, 3),
        )

    def summary(self) -> dict:
        return {
            "competition":  self.competition,
            "stage":        self.stage,
            "intensity":    self.intensity(),
            "motivation_a": self.motivation_a,
            "motivation_b": self.motivation_b,
            "second_leg":   self.is_second_leg,
            "h2h_matches":  len(self.h2h_matches),
            "confidence":   self.confidence,
            "notes":        self.notes,
        }