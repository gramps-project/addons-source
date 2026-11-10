# DescendantsTimeline 1.0.0

Vue interactive de descendance intégrée aux graphiques de Gramps, sur une échelle chronologique.

- Couleurs par génération et conjoints en gris.
- Nœuds de mariage et représentation des remariages.
- Inférences temporelles et représentation des incertitudes lorsque les données le permettent.
- Navigation entre personnes, zoom et déplacement dans la chronologie.

Le calcul et l’affichage ne modifient pas les données généalogiques. Les commandes natives de Gramps, notamment la personne souche et les signets, peuvent enregistrer leurs réglages à la demande de l’utilisateur. Les dates inférées restent des estimations visuelles.

## Compatibilité

Cible Gramps 6.0.x. Le code fonctionnel de référence a été testé avec GrampsAIO 6.0.8 sous Windows, Python 3.14.4 et GTK 3.24. Linux, macOS et les autres versions 6.0.x restent à qualifier. Dépendances fournies par Gramps, Python, PyGObject/GTK 3 et Cairo. Aucun service distant nécessaire au calcul.

## Installation

Suivre INSTALL.md puis ouvrir une généalogie de test, choisir une personne et sélectionner Descendants Timeline dans les graphiques. La vue et son initialiseur d’icône sont déclarés dans un même fichier. Le paquet contient les icônes claire et sombre.

## Captures à fournir

Ajouter avant présentation publique des captures issues d’une généalogie synthétique montrant les générations, un remariage et une incertitude. Les captures ne sont pas incluses dans cette version préparée.

## Langues et licence

Les libellés du greffon sont disponibles en anglais et en français. Les autres textes de l’interface utilisent les traductions de Gramps. Licence GNU GPL version 2, texte intégral dans LICENSE et attribution dans NOTICE.
