import json
from pathlib import Path


def extraer_username(item):
    """
    Obtiene el username de un elemento del JSON de Instagram.
    Prueba en orden: title -> value -> href.
    - following.json trae el nombre en 'title' y solo 'href' en string_list_data.
    - followers_X.json trae 'title' vacío y el nombre en 'value'.
    """
    username = (item.get("title") or "").strip()
    if username:
        return username

    for entrada in item.get("string_list_data", []):
        if not isinstance(entrada, dict):
            continue

        username = entrada.get("value")
        if not username:
            href = entrada.get("href", "")
            username = href.rstrip("/").split("/")[-1] if href else ""

        if username:
            return username

    return ""


def cargar_usernames(ruta_archivo, clave_relacion=None):
    """Carga los usernames desde un archivo JSON exportado por Instagram."""
    ruta_archivo = Path(ruta_archivo)
    if not ruta_archivo.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {ruta_archivo}")

    with ruta_archivo.open("r", encoding="utf-8") as f:
        datos = json.load(f)

    if clave_relacion and isinstance(datos, dict):
        datos = datos.get(clave_relacion, [])

    if not isinstance(datos, list):
        return set()

    usernames = set()
    for item in datos:
        if isinstance(item, dict):
            username = extraer_username(item)
            if username:
                usernames.add(username)

    return usernames


def cargar_followers(carpeta):
    """Une followers_1.json, followers_2.json, etc. (Instagram divide archivos grandes)."""
    archivos = sorted(carpeta.glob("followers_*.json"))
    if not archivos:
        raise FileNotFoundError(f"No encontré archivos followers_*.json en: {carpeta}")

    followers = set()
    for archivo in archivos:
        followers |= cargar_usernames(archivo)
    return followers


def main():
    carpeta = Path(__file__).resolve().parent / "followers_and_following"
    if not carpeta.exists():
        raise FileNotFoundError(f"No existe la carpeta: {carpeta}")

    followers = cargar_followers(carpeta)
    following = cargar_usernames(
        carpeta / "following.json", clave_relacion="relationships_following"
    )

    no_te_siguen = following - followers
    no_sigues = followers - following

    print(f"Sigues a {len(following)} cuentas.")
    print(f"Te siguen {len(followers)} cuentas.\n")

    print(f"🔻 No te siguen de vuelta ({len(no_te_siguen)}):")
    for user in sorted(no_te_siguen):
        print(f"  - {user}")

    print(f"\n🔺 Te siguen pero no los sigues ({len(no_sigues)}):")
    for user in sorted(no_sigues):
        print(f"  - {user}")


if __name__ == "__main__":
    main()