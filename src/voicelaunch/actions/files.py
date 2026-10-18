import os, shutil, subprocess
from pathlib import Path
from ..matching import rank_paths
def search(query, folders, config):
    f=config["files"]; cli=shutil.which(f["everything_cli_path"]) or f["everything_cli_path"]
    try:
        cmd=[cli,"-n",str(f["max_results"]),"/ad" if folders else "/a-d",*query.split()]; out=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",timeout=3,creationflags=0x08000000).stdout.splitlines()
    except (OSError,subprocess.TimeoutExpired): out=_fallback(query,folders,f)
    excludes=[x.lower() for x in f["exclude_substrings"]]; out=[p for p in out if not any(x in p.lower() for x in excludes)]
    ranked=rank_paths(query,out,str(Path.home())); return ranked[0][0] if ranked and ranked[0][1]>=config["matching"]["file_min_score"] else None
def _fallback(query, folders, cfg):
    words=query.lower().split(); found=[]
    for root in cfg["fallback_dirs"]:
        root=Path(root).expanduser()
        if not root.exists(): continue
        for current, dirs, files in os.walk(root):
            if len(Path(current).relative_to(root).parts)>=cfg["fallback_max_depth"]: dirs[:]=[]
            choices=dirs if folders else files
            for name in choices:
                if all(w in name.lower() for w in words): found.append(str(Path(current)/name))
    return found
def reveal(path): subprocess.Popen(["explorer.exe",f"/select,{path}"])
