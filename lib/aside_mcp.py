import json, subprocess, sys
sys.stdout.reconfigure(encoding='utf-8')

exe = r'C:\Users\PC\AppData\Local\Aside\CLI\versions\1.26.1015.732\aside.exe'
p = subprocess.Popen([exe, 'mcp'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8')
def rpc(i, method, params):
    p.stdin.write(json.dumps({'jsonrpc':'2.0','id':i,'method':method,'params':params})+'\n'); p.stdin.flush()
    while True:
        line = p.stdout.readline()
        if not line: raise RuntimeError('MCP closed')
        msg=json.loads(line)
        if msg.get('id')==i: return msg
try:
    rpc(1,'initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'codex-research','version':'1'}})
    p.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n'); p.stdin.flush()
    if len(sys.argv)==1: result=rpc(2,'tools/list',{})
    else:
        with open(sys.argv[1],encoding='utf-8-sig') as f: args=json.load(f)
        result=rpc(2,'tools/call',{'name':'repl','arguments':args})
    print(json.dumps(result,ensure_ascii=False))
    from pathlib import Path
    out=Path('project/j001/09_작업기록/03_로그/aside_evidence.jsonl')
    with out.open('a',encoding='utf-8') as f: f.write(json.dumps(result,ensure_ascii=False)+'\n')
finally:
    p.terminate()
