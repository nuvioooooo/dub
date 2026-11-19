#!/usr/bin/env python3
"""dublaj_kaynaklari.json içindeki "base" adreslerini kendi kendine günceller.

Her siteyi domain_guncelle.py ile kontrol eder (yönlendirmeleri takip eder, taşınmışsa yeni adresi bulur,
park/reklam sayfalarını ve kara listeyi reddeder), sonucu JSON'daki "base" alanlarına yazar.
Aynı siteyi kullanan provider'lar "domainKey" ile gruplanır (yoksa provider id'si kullanılır).
Site kontrol edilemezse eski adres korunur.

Kullanım:  python3 scripts/sync_bases.py [--dry-run]
"""
import json, os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG = os.environ.get("CONFIG_PATH", os.path.join(ROOT, "dublaj_kaynaklari.json"))


def group_key(p):
    return p.get("domainKey") or p["id"]


def build_list(cfg):
    groups = {}
    for p in cfg["providers"]:
        groups.setdefault(group_key(p), p["base"].rstrip("/"))
    return groups, "".join(f"|{k}:{v}\n" for k, v in groups.items())


def apply_list(cfg, list_text):
    new = {}
    for ln in list_text.splitlines():
        if ln.startswith("|") and ":" in ln:
            name, url = ln[1:].split(":", 1)
            new[name.strip()] = url.strip()
    changed = []
    for p in cfg["providers"]:
        url = new.get(group_key(p), "").rstrip("/")
        if re.fullmatch(r"https://[a-z0-9.-]+\.[a-z]{2,}(:\d+)?", url, re.I) and url != p["base"].rstrip("/"):
            changed.append((p["id"], p["base"], url)); p["base"] = url
    return changed


def main():
    dry = "--dry-run" in sys.argv
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    groups, text = build_list(cfg)

    tmpdir = tempfile.mkdtemp()
    listfile = os.path.join(tmpdir, "liste.txt")
    open(listfile, "w", encoding="utf-8", newline="\n").write(text)
    os.environ["FILE_PATH"] = listfile
    os.environ.setdefault("BLACKLIST_PATH", os.path.join(ROOT, "domain_blacklist.txt"))
    sys.path.insert(0, HERE)
    import domain_guncelle as dg
    dg.MIN_CHANGE_LIMIT = max(2, len(groups) // 2)   # az siteyle de "toplu değişiklik" korumasını çalıştır

    rc = dg.main()
    if rc != 0: sys.exit(rc)

    changed = apply_list(cfg, open(listfile, encoding="utf-8").read())
    for pid, old, new in changed: print(f"  {pid}: {old} -> {new}")
    if not changed: print("base değişikliği yok"); return
    if dry: print(f"{len(changed)} değişiklik (dry-run, yazılmadı)"); return
    with open(CONFIG, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2); f.write("\n")
    json.load(open(CONFIG, encoding="utf-8"))
    print(f"{len(changed)} provider güncellendi")


if __name__ == "__main__":
    main()
