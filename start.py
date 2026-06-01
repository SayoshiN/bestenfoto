#!/usr/bin/env python3
"""
BestenFoto - Zapusk servera s ngrok
======================================
Ispolzovanie:
  python start.py           -> tolko lokalno (http://localhost:5000)
  python start.py --ngrok   -> zapustit s ngrok (publichnaya ssylka)
"""

import os
import sys
import subprocess
import time

BASE = os.path.dirname(os.path.abspath(__file__))

def check_ngrok():
    try:
        result = subprocess.run(['ngrok', 'version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def start_ngrok():
    print("\nZapusk ngrok...")
    proc = subprocess.Popen(
        ['ngrok', 'http', '5000'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(4)

    # Get public URL from ngrok API
    try:
        import urllib.request, json
        with urllib.request.urlopen('http://localhost:4040/api/tunnels') as r:
            data = json.loads(r.read())
            tunnels = data.get('tunnels', [])
            for t in tunnels:
                if t.get('proto') == 'https':
                    url = t['public_url']
                    print(f"\n{'='*50}")
                    print(f"  PUBLICHNAYA SSYLKA: {url}")
                    print(f"  Podelites etoy ssylkoy!")
                    print(f"{'='*50}\n")
                    return proc, url
    except Exception as e:
        print(f"  Ne udalos poluchit URL ngrok: {e}")
        print("  -> Otkroyte http://localhost:4040 v brauzere")
    return proc, None

def start_pyngrok():
    """Alternative: use pyngrok Python library"""
    try:
        from pyngrok import ngrok
        print("\nZapusk pyngrok...")
        public_url = ngrok.connect(5000, "http").public_url
        print(f"\n{'='*50}")
        print(f"  PUBLICHNAYA SSYLKA: {public_url}")
        print(f"  Podelites etoy ssylkoy!")
        print(f"{'='*50}\n")
        return public_url
    except ImportError:
        print("  pyngrok ne ustanovlen. Ustanovite: pip install pyngrok")
        return None
    except Exception as e:
        print(f"  Oshibka pyngrok: {e}")
        return None

def main():
    use_ngrok = '--ngrok' in sys.argv

    print("""
+======================================+
|     BestenFoto - Zapusk             |
+======================================+
""")

    if use_ngrok:
        # Try pyngrok first, then fallback to ngrok CLI
        url = start_pyngrok()
        if not url and check_ngrok():
            ngrok_proc, url = start_ngrok()
        elif not url:
            print("Ngrok ne nayden!")
            print("\nUstanovka ngrok:")
            print("   1. Pereydite na https://ngrok.com/download")
            print("   2. Skachayte i ustanovite ngrok")
            print("   3. Zapustite: ngrok config add-authtoken VASH_TOKEN")
            print("   4. Zanovo: python start.py --ngrok\n")
            print("   ILI: pip install pyngrok\n")
    else:
        print("  Sovet: python start.py --ngrok - dlya publichnoy ssylki\n")

    print("  Zapusk servera BestenFoto...")
    print("  Papka foto: static/photos/")
    print("  Baza dannykh: data/bestenfoto.db")
    print("  Lokalnyy adres: http://localhost:5000")
    print("  Statistika: http://localhost:5000/stats")
    print("  Admin: http://localhost:5000/admin")
    print("\n  Nazhmite Ctrl+C dlya ostanovki\n")

    os.chdir(BASE)
    os.system(f'{sys.executable} app.py')

if __name__ == '__main__':
    main()