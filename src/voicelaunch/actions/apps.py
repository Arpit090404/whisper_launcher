import json, os, subprocess
from pathlib import Path
CMD=["powershell","-NoProfile","-NonInteractive","-Command","[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"]
def build_index(cache: Path) -> dict:
    out=subprocess.run(CMD,capture_output=True,text=True,encoding="utf-8",creationflags=0x08000000).stdout; data=json.loads(out); data=[data] if isinstance(data,dict) else data; result={a["Name"].strip().lower():a["AppID"] for a in data if "uninstall" not in a["Name"].lower()}; cache.write_text(json.dumps(result),encoding="utf-8"); return result
def launch(app_id): os.startfile("shell:AppsFolder\\"+app_id)
