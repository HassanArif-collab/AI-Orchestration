import sqlite3
import json

conn = sqlite3.connect('packages/data/pipeline.db')
cursor = conn.execute('SELECT run_id, state_json FROM pipeline_runs ORDER BY updated_at DESC LIMIT 1')
row = cursor.fetchone()
if row:
    print('Run ID:', row[0][:20], '...')
    data = json.loads(row[1])
    print('Status:', data.get('status'))
    print('Current Stage:', data.get('current_stage'))
    print('Stage Status:', data.get('stage_status'))
    print('Stage Outputs keys:', list(data.get('stage_outputs', {}).keys()))
conn.close()
