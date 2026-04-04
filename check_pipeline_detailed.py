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
    print('\nStage Status:')
    for k, v in data.get('stage_status', {}).items():
        print(f'  {k}: {v}')
    print('\nStage Outputs:')
    outputs = data.get('stage_outputs', {})
    if outputs:
        for k, v in outputs.items():
            if isinstance(v, dict):
                print(f'  {k}: {len(v)} keys - {list(v.keys())[:5]}')
            elif isinstance(v, list):
                print(f'  {k}: list with {len(v)} items')
            else:
                print(f'  {k}: {type(v).__name__}')
    else:
        print('  (no outputs yet)')
    print('\nError Message:', data.get('error_message', '(none)'))
    print('\nFull JSON (first 500 chars):')
    print(json.dumps(data, indent=2)[:500])
conn.close()
