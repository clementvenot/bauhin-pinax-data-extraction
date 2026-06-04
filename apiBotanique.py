import requests

def rechercher_plante(nom_plante):
    """
    Recherche une plante via l'API GBIF.

    :param nom_plante: Nom de la plante à rechercher (str)
    :return: Résultat JSON de la requête
    """
    url = "https://api.gbif.org/v1/species/search"

    params = {
        "q": nom_plante
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as e:
        print("Erreur lors de l'appel API :", e)
        return None

# Exemple d'utilisation
if __name__ == "__main__":
    resultat = rechercher_plante("Ornithogalum ")
    print(resultat)

    if resultat:
        for plante in resultat.get("results", []):
            print(plante.get("scientificName"))