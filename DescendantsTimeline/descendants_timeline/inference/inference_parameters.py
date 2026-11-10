"""Paramètres généalogiques du moteur d'inférence.

Ces valeurs définissent des seuils de plausibilité utilisés
uniquement par les contraintes SOFT.

Elles ne représentent ni des limites biologiques absolues,
ni une validation juridique des événements généalogiques.
"""

# Âge minimum plausible au mariage.
# Valeur uniforme en V1, indépendamment du genre et de la période.
MIN_MARRIAGE_AGE_YEARS = 12

# Longévité maximale plausible utilisée pour borner les estimations.
# Il ne s'agit pas d'une limite biologique absolue.
MAX_PLAUSIBLE_LIFESPAN_YEARS = 125