import os
import re

directory = 'packages/content_factory/orchestration'

def fix_logger(match):
    func = match.group(1)
    args = match.group(2)
    
    # Split into the message and the kwargs
    parts = args.split(',', 1)
    if len(parts) == 2 and '=' in parts[1]:
        msg = parts[0].strip()
        kwargs_str = parts[1].strip()
        
        # Turn f"msg", k=v into f"msg | k={v}..."
        if msg.startswith('f"'):
            msg = msg[2:-1]  # remove f" and "
        elif msg.startswith("f'"):
            msg = msg[2:-1]
        elif msg.startswith('"'):
            msg = msg[1:-1]
        elif msg.startswith("'"):
            msg = msg[1:-1]
            
        # Parse kwargs_str into formatted strings
        kwarg_items = [k.strip() for k in kwargs_str.split(',')]
        formatted_kwargs = []
        for item in kwarg_items:
            if '=' in item:
                k, v = item.split('=', 1)
                k = k.strip()
                v = v.strip()
                formatted_kwargs.append(f"{k}={{{v}}}")

        new_msg = f'f"{msg} | {" ".join(formatted_kwargs)}"'
        return f"logger.{func}({new_msg})"
    
    return match.group(0)

for root, _, files in os.walk(directory):
    for f in files:
        if not f.endswith('.py'): continue
        path = os.path.join(root, f)
        
        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()
            
        new_content = re.sub(r'logger\.([a-z]+)\((.*?)\)', fix_logger, content)
        
        if new_content != content:
            with open(path, 'w', encoding='utf-8') as file:
                file.write(new_content)
            print(f'Fixed {path}')
