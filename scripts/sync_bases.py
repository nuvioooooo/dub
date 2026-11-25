#!/usr/bin/env python3
"""dublaj_kaynaklari.json içindeki "base" adreslerini kendi kendine günceller.

Her siteyi domain_guncelle.py ile kontrol eder (yönlendirmeleri takip eder, taşınmışsa yeni adresi bulur,
park/reklam sayfalarını ve kara listeyi reddeder), sonucu JSON'daki "base" alanlarına yazar.
Aynı siteyi kullanan provider'lar "domainKey" ile gruplanır (yoksa provider id'si kullanılır).
Site kontrol edilemezse eski adres korunur.
JSON kaynak kabul edilir: sonuçlar eklenti_domainleri.txt dosyasına da yansıtılır
(txt'de olmayan site eklenir, JSON'da olmayan site satırı silinir; yorum ve boş satırlara dokunulmaz).

Kullanım:  python3 scripts/sync_bases.py [--dry-run]
"""
import json, os, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG = os.environ.get("CONFIG_PATH", os.path.join(ROOT, "dublaj_kaynaklari.json"))
TXT = os.environ.get("TXT_PATH", os.path.join(ROOT, "eklenti_domainleri.txt"))

# JSON'daki domainKey, txt'de farklı adla duruyorsa burada eşleştirilir.
TXT_ALIASES = {
    "SelcukFlixDub": "SelcukFlix",
    "DiziGomDub": "DiziGom",
}


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


def sync_txt(groups, dry):
    """JSON'daki güncel adresleri eklenti_domainleri.txt'ye yazar. Değişen/eklenen sayısını döndürür."""
    from domain_guncelle import LINE_RE
    if not os.path.exists(TXT):
        print(f"UYARI: {TXT} yok, txt senkronu atlandı"); return 0
    raw = open(TXT, encoding="utf-8-sig", newline="").read()
    lines = raw.splitlines(keepends=True)
    eol = "\r\n" if "\r\n" in raw else "\n"
    wanted = {TXT_ALIASES.get(k, k) for k in groups}
    count, kept = 0, []
    for ln in lines:
        m = LINE_RE.match(ln.rstrip("\r\n"))
        if m and m.group("name").strip() not in wanted:
            print(f"  txt {m.group('name').strip()}: silindi (JSON'da yok)"); count += 1
        else:
            kept.append(ln)
    lines = kept
    index = {}
    for i, ln in enumerate(lines):
        m = LINE_RE.match(ln.rstrip("\r\n"))
        if m: index.setdefault(m.group("name").strip(), (i, m))
    for key, url in groups.items():
        name = TXT_ALIASES.get(key, key)
        if name in index:
            i, m = index[name]
            if m.group("url").rstrip("/") == url: continue
            end = lines[i][len(lines[i].rstrip("\r\n")):]
            lines[i] = f"{m.group('pre')}{m.group('name')}{m.group('sep')}{url}{m.group('rest')}{end}"
            print(f"  txt {name}: {m.group('url')} -> {url}")
        else:
            if lines and not lines[-1].endswith(("\n", "\r")): lines[-1] += eol
            lines.append(f"|{name}:{url}{eol}")
            print(f"  txt {name}: eklendi -> {url}")
        count += 1
    if count and not dry:
        with open(TXT, "w", encoding="utf-8", newline="") as f: f.write("".join(lines))
    return count


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

    if changed and not dry:
        with open(CONFIG, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2); f.write("\n")
        json.load(open(CONFIG, encoding="utf-8"))
        print(f"{len(changed)} provider güncellendi")
    elif changed:
        print(f"{len(changed)} değişiklik (dry-run, yazılmadı)")
    else:
        print("base değişikliği yok")

    # JSON (güncel hali) -> txt. JSON değişmese bile txt'deki eski değerleri düzeltir.
    final, _ = build_list(cfg)
    final = {k: v.rstrip("/") for k, v in final.items()}
    n = sync_txt(final, dry)
    print(f"txt: {n} satır {'(dry-run, yazılmadı)' if dry and n else 'güncellendi' if n else 'zaten güncel'}")


if __name__ == "__main__":
    main()
