
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

BASE = "https://basketball-data.billmill.org/nba/stats"

OUTPUT = Path("data")
OUTPUT.mkdir(exist_ok=True)

db = duckdb.connect()
db.execute("INSTALL httpfs; LOAD httpfs;")

query = f"""
WITH matchs AS (
    SELECT
        p.player_id,
        p.game_id,
        p.min,
        p.pts,
        p.fg3m,
        p.reb,
        p.ast,
        p.stl,
        p.blk,
        p.fgm,
        p.fga,
        p.ftm,
        p.fta,
        p.tov
    FROM read_parquet(
        '{BASE}/player_game_logs/season=2027/data.parquet'
    ) p
    JOIN read_parquet(
        '{BASE}/games/season=2027/data.parquet'
    ) g
      ON p.game_id = g.game_id
    WHERE g.game_type = 'regular_season'
),
totaux AS (
    SELECT
        player_id,
        COUNT(DISTINCT game_id) AS games_played,
        ROUND(SUM(min), 4) AS minutes,
        SUM(pts) AS points,
        SUM(fg3m) AS three_point_makes,
        SUM(reb) AS rebounds,
        SUM(ast) AS assists,
        SUM(stl) AS steals,
        SUM(blk) AS blocks,
        SUM(fgm) AS field_goals_made,
        SUM(fga) AS field_goal_attempts,
        SUM(ftm) AS free_throws_made,
        SUM(fta) AS free_throw_attempts,
        SUM(tov) AS turnovers
    FROM matchs
    GROUP BY player_id
)
SELECT
    s.name AS player_name,
    t.*
FROM totaux t
JOIN read_parquet(
    '{BASE}/player_seasons/season=2027/data.parquet'
) s
  ON t.player_id = s.player_id
ORDER BY t.points DESC
"""

result = db.execute(query)
headers = [col[0] for col in result.description]
rows = result.fetchall()

status = db.execute(f"""
    SELECT
        COUNT(*),
        CAST(MAX(game_date) AS VARCHAR)
    FROM read_parquet(
        '{BASE}/games/season=2027/data.parquet'
    )
    WHERE game_type = 'regular_season'
      AND game_date <= CURRENT_DATE
""").fetchone()

number_games, latest_date = status

if len(rows) < 100 or number_games < 10:
    raise ValueError("Statistiques NBA incomplètes")

if not latest_date:
    raise ValueError("Date NBA manquante")

ids = [str(row[1]) for row in rows]

if len(ids) != len(set(ids)):
    raise ValueError("Identifiants joueurs en double")

with open(
    OUTPUT / "nba_2027_9cat.csv",
    "w",
    newline="",
    encoding="utf-8"
) as f:
    writer = csv.writer(f)
    writer.writerow(headers)
    writer.writerows(rows)

metadata = {
    "season": 2027,
    "max_game_date": latest_date,
    "games_count": number_games,
    "players_count": len(rows),
    "generated_at_utc": datetime.now(
        timezone.utc
    ).isoformat()
}

with open(
    OUTPUT / "status.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(metadata, f, indent=2)

print("EXPORT NBA RÉUSSI")
print(metadata)
