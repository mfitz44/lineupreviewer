import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from datetime import datetime

st.set_page_config(page_title="Lineup Review App", layout="wide")
st.title("Fairway Theory: Lineup Review")

# Sidebar inputs
st.sidebar.header("Upload Inputs")
scorecard_file = st.sidebar.file_uploader("Upload GTO Scorecard CSV", type="csv")
lineup_files = st.sidebar.file_uploader("Upload Lineup Build CSVs", type="csv", accept_multiple_files=True)

if scorecard_file and lineup_files:
    # Load GTO scorecard
    scorecard = pd.read_csv(scorecard_file)
    scorecard.columns = scorecard.columns.str.strip()

    # Define equal-width salary buckets (4 tiers)
    min_sal = scorecard['Salary'].min()
    max_sal = scorecard['Salary'].max()
    bins = np.linspace(min_sal, max_sal, 5)  # 4 equal intervals
    labels = ['Q1 (Low)', 'Q2', 'Q3', 'Q4 (High)']
    scorecard['Tier'] = pd.cut(scorecard['Salary'], bins=bins, labels=labels, include_lowest=True)

    # Load lineup builds
    builds = {}
    all_lineups = []
    for uploaded in lineup_files:
        df = pd.read_csv(uploaded)
        builds[uploaded.name] = df
        for row in df.itertuples(index=False, name=None):
            all_lineups.append(tuple(row))

    total_lineups = len(all_lineups)

    # Exposure calculation
    flat_players = [player for lineup in all_lineups for player in lineup]
    exp_counts = pd.Series(flat_players).value_counts()
    exposures = exp_counts / total_lineups
    exposures_df = exposures.to_frame(name='Average Exposure')

    # Overlap matrix
    lineup_sets = {name: {tuple(sorted(lineup)) for lineup in builds[name].itertuples(index=False, name=None)} for name in builds}
    overlap = pd.DataFrame(index=builds.keys(), columns=builds.keys(), dtype=int)
    for a in lineup_sets:
        for b in lineup_sets:
            overlap.loc[a, b] = len(lineup_sets[a] & lineup_sets[b])

    # Salary tier breakdown
    tier_map = scorecard.set_index('Name')['Tier'].to_dict()
    tier_records = []
    for lineup in all_lineups:
        counts = {tier: 0 for tier in labels}
        for player in lineup:
            tier = tier_map.get(player)
            if tier:
                counts[tier] += 1
        tier_records.append(counts)
    tier_df = pd.DataFrame(tier_records)
    comp_dist = tier_df.apply(pd.Series.value_counts).fillna(0).sort_index()
    avg_tiers = tier_df.mean().to_frame(name='Avg Count')

    # Display
    st.subheader("Player Exposure")
    st.dataframe(exposures_df)

    st.subheader("Lineup Overlap Matrix")
    st.dataframe(overlap)

    st.subheader("Salary Tier Composition Distribution")
    st.dataframe(comp_dist)

    st.subheader("Average Players per Tier")
    st.dataframe(avg_tiers)

    # Co-occurrence heatmap (top 10)
    top10 = exposures.nlargest(10).index.tolist()
    co_mat = pd.DataFrame(index=top10, columns=top10, dtype=int)
    for p1 in top10:
        for p2 in top10:
            co_mat.loc[p1, p2] = sum(1 for ln in all_lineups if p1 in ln and p2 in ln)
    st.subheader("Co-occurrence Heatmap (Top 10)")
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(co_mat.values)
    ax.set_xticks(range(len(top10)))
    ax.set_xticklabels(top10, rotation=90)
    ax.set_yticks(range(len(top10)))
    ax.set_yticklabels(top10)
    plt.colorbar(im, ax=ax)
    st.pyplot(fig)

    # Downloadable report
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        exposures_df.to_excel(writer, sheet_name='Exposures')
        overlap.to_excel(writer, sheet_name='Overlap')
        comp_dist.to_excel(writer, sheet_name='TierDist')
        avg_tiers.to_excel(writer, sheet_name='AvgTiers')
        co_mat.to_excel(writer, sheet_name='Cooccurrence')
    buffer.seek(0)
    fname = f"lineup_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    st.download_button("Download Review Report", buffer, file_name=fname,
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
