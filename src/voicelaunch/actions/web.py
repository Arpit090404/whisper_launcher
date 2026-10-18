import subprocess, webbrowser, winreg
from urllib.parse import quote_plus
def chrome_path():
    for root in (winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(root,r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as k: return winreg.QueryValue(k,None)
        except OSError: pass
    return None
def open_url(url):
    chrome=chrome_path(); subprocess.Popen([chrome,url]) if chrome else webbrowser.open(url)
def google(query): open_url("https://www.google.com/search?q="+quote_plus(query))
