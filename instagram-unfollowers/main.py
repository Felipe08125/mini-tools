import json

def cargar_usernames(ruta_archivo, clave_relacion=None):
    """
    Carga los usernames desde un archivo JSON exportado por Instagram.
    - followers_1.json suele ser una lista directa.
    - following.json suele venir dentro de 'relationships_following'.
    """
    with open(ruta_archivo, "r", encoding="utf-8") as f:
        datos = json.load(f)

    # Si el JSON viene envuelto en una clave (como 'following')
    if clave_relacion and isinstance(datos, dict):
        datos = datos.get(clave_relacion, [])

    usernames = set()
    for item in datos:
        for entrada in item.get("string_list_data", []):
            username = entrada.get("value")
            if not username:
                href = entrada.get("href", "")
                username = href.rstrip("/").split("/")[-1]
            if username:
                usernames.add(username)

    return usernames


followers = cargar_usernames("followers_1.json")
following = cargar_usernames("following.json", clave_relacion="relationships_following")

followers_n=len(followers)
following_n=len(following)

# Personas que sigues pero no te siguen de vuelta
no_te_siguen = following - followers
nts=len(no_te_siguen)

# Personas que te siguen pero tú no sigues
no_sigues = followers - following
ns=len(no_sigues)

print(f"Sigues a {following_n} cuentas.")
print(f"Te siguen {followers_n} cuentas.\n")

print(f"🔻 No te siguen de vuelta ({nts}):")
for user in sorted(no_te_siguen):
    print(f"  - {user}")

print(f"\n🔺 Te siguen pero no los sigues ({ns}):")
for user in sorted(no_sigues):
    print(f"  - {user}")