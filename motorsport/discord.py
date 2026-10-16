import requests

def notify(webhook, changes, failures, dry_run=False):
    if not webhook or (not changes and not failures):
        return
    header = "🧪 Motorsport calendar — DRY RUN" if dry_run else "🏁 Motorsport calendar — synchronizace"
    lines = [header, f"Nové/změněné události: {len(changes)} | Chyby: {len(failures)}"]
    if changes:
        lines += ["", "**Změny:**"] + changes[:35]
    if failures:
        lines += ["", "**Chyby:**"] + ["⚠️ " + f for f in failures[:20]]
    if len(changes) > 35:
        lines.append(f"… a dalších {len(changes)-35} změn")
    payload = {"content": "\n".join(lines)[:1950], "allowed_mentions": {"parse": []}}
    reply = requests.post(webhook, json=payload, timeout=20)
    reply.raise_for_status()
