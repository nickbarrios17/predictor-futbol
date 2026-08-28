import pandas as pd
import streamlit as st

from model.worldcup import (
    build_group_fixtures,
    build_match_models,
    load_strengths,
    match_summary_rows,
    simulate_group,
)


DEFAULT_GROUP = """Argentina
Mexico
Poland
Saudi Arabia"""


def render_worldcup_tab() -> None:
    st.markdown("### Simulador de grupo")
    st.caption("Carga 4 equipos, calcula todos los cruces y estima chances de clasificacion.")

    c1, c2, c3 = st.columns([2, 1, 1])
    teams_text = c1.text_area(
        "Equipos del grupo",
        value=DEFAULT_GROUP,
        height=140,
        help="Un equipo por linea.",
    )
    n_sims = c2.slider("Simulaciones", min_value=1000, max_value=20000, value=5000, step=1000)
    team_type = c3.selectbox(
        "Tipo",
        ["seleccion", "default", "club_top", "club_menor"],
        index=0,
    )

    competition = st.text_input("Competicion", value="FIFA World Cup")

    teams = _parse_teams(teams_text)
    if len(teams) != 4:
        st.info("Para simular un grupo mundialista carga exactamente 4 equipos.")
        return

    fixtures = build_group_fixtures(teams)
    st.markdown("#### Fixture generado")
    st.dataframe(
        pd.DataFrame(
            [{"Partido": f"{home} vs {away}"} for home, away in fixtures]
        ),
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Simular grupo", type="primary", use_container_width=True):
        with st.spinner("Calculando fuerzas y simulando el grupo..."):
            strengths, errors = load_strengths(teams, team_type=team_type, verbose=False)
            if errors:
                st.warning("Algunos equipos no pudieron cargarse: " + " | ".join(errors))

            missing = [team for team in teams if team not in strengths]
            if missing:
                st.error("No se puede simular sin historial para: " + ", ".join(missing))
                return

            models = build_match_models(fixtures, strengths, competition=competition)
            if len(models) != len(fixtures):
                st.error("No se pudieron calcular todos los partidos del grupo.")
                return

            group_result = simulate_group(teams, models, n_sims=n_sims)
            st.session_state["worldcup_group_result"] = group_result
            st.session_state["worldcup_match_rows"] = match_summary_rows(models)

    group_result = st.session_state.get("worldcup_group_result")
    match_rows = st.session_state.get("worldcup_match_rows")

    if group_result:
        st.divider()
        st.markdown(f"#### Tabla probabilistica ({group_result['n_sims']} simulaciones)")
        table_df = pd.DataFrame(group_result["table"])
        st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Clasifica %": st.column_config.ProgressColumn(
                    "Clasifica %",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
                "1ro %": st.column_config.ProgressColumn(
                    "1ro %",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
                "2do %": st.column_config.ProgressColumn(
                    "2do %",
                    min_value=0,
                    max_value=100,
                    format="%.1f%%",
                ),
            },
        )

        st.download_button(
            "Descargar tabla CSV",
            data=table_df.to_csv(index=False).encode("utf-8"),
            file_name="simulacion_grupo_mundial.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if match_rows:
        st.divider()
        st.markdown("#### Probabilidades por partido")
        matches_df = pd.DataFrame(match_rows)
        st.dataframe(matches_df, use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar partidos CSV",
            data=matches_df.to_csv(index=False).encode("utf-8"),
            file_name="probabilidades_partidos_grupo.csv",
            mime="text/csv",
            use_container_width=True,
        )


def _parse_teams(raw: str) -> list[str]:
    seen = set()
    teams = []
    for line in raw.splitlines():
        team = line.strip()
        key = team.lower()
        if team and key not in seen:
            teams.append(team)
            seen.add(key)
    return teams
