# hqf-pdf-site — règles locales

Ce fichier **prévaut** sur les règles Python/Django globales quand les deux se
contredisent. Le reste des règles globales s'applique.

## Ce qu'est ce dépôt

Site Django : inscription, compte, clés d'API, facturation du service de rendu
PDF. Dépôt **séparé** du moteur (`hqf-pdf`) et du serveur (`hqf-pdf-server`).

**Le site écrit le TOML que le serveur lit.** C'est le pont entre les deux : un
compte du site produit une clé d'API et une entrée client côté serveur.

**Aucune licence publiée.** Ne pas ajouter de `LICENSE`.

## Version de Python

**Python 3.14.** Django 6.x supporte 3.12 / 3.13 / 3.14.

**Python 3.15 : ne pas y passer.** Bêta au 2026-07-17, finale prévue le
2026-10-01, aucun Django ne la supporte encore. À réévaluer quand une version
de Django l'annonce.

## Typage — INTERDIT par défaut

**Aucune annotation** sur les signatures, les variables locales, les attributs
ni les constantes. Le code est lisible sans.

**Exception unique** : là où Python *force* l'annotation pour fonctionner —
`dataclass`, `NamedTuple`, `TypedDict`, `Protocol`, `singledispatch`,
FastAPI/Pydantic, resolvers Django stricts. Dans ce cas seulement, annoter
**et** ajouter un commentaire inline disant *pourquoi* c'est requis ici.

Quand une annotation est requise : **syntaxe native** — `list[int]`,
`X | None`, génériques PEP 695. **Jamais** `List`, `Dict`, `Optional`, `Union`,
`TypeVar` de `typing`.

**Pas de `from __future__ import annotations`.**

**Pas de mypy, pas de pyright.** Ce ne sont pas des dépendances du projet.

## Outillage

Formatage et lint : `black` (88), `isort` (profil `black`), `ruff`, `pylint`,
`pycodestyle`.

`pycodestyle` est le **seul** linter tiers embarqué dans PyCharm ; ses autres
inspections sont propriétaires et aucun paquet pip ne les reproduit. D'où :
`.idea/inspectionProfiles/Project_Default.xml` est **versionné**, pour que
l'IDE signale ce que signalent les linters — et rien de plus.

`./inspect.sh` lance l'inspection PyCharm headless : c'est la seule fidélité
réelle à ce que voit l'IDE. **Refuse de tourner si PyCharm est ouvert** (il
verrouille le projet).

## Style

- PEP 8. Black fait foi sur le formatage : zéro discussion de style.
- **Docstrings Google sur le public** — c'est LE contrat (arguments, retour,
  exceptions, effets de bord).
- **Commentaires** : le lecteur est un dev intermédiaire à expert. Paraphraser
  le code est du bruit. Un commentaire n'est autorisé que pour un **pourquoi
  non évident**, un **invariant subtil**, une **référence de ticket** ou un
  **piège**. Interdit : justifier une correction, faire du changelog, comparer
  à l'approche écartée, s'auto-justifier.
- **EAFP > LBYL.** Le code défensif contre l'impossible est **interdit** :
  *let it crash*, la trace dit la vérité.
- **YAGNI.** Pas d'abstraction spéculative. `flat > layered`.
- Variable de boucle inutilisée → `__` (double underscore), jamais `_` qui
  collide avec `gettext as _`.
- Pas d'auto-compliment dans le code, les commentaires ni les commits.

## ORM

- `get(pk=…)` plutôt qu'une chaîne de `filter().first()`.
- **Pas de `select_related` préemptif** : on l'ajoute quand la requête le
  demande, pas « au cas où ».
- `bulk_create` / `bulk_update` plutôt qu'une boucle de `save()`.
- **Annoncer le nombre de requêtes SQL** que fait un bout de code. « Je ne sais
  pas » = le code n'est pas prêt.

## i18n

FR + EN dès le premier commit. Règles globales applicables :

- Jamais de HTML dans une chaîne traduisible : les balises sortent du
  `gettext`, on coupe en plusieurs `trans`.
- Jamais d'espaces de mise en forme ni d'indentation dans un `msgid`.
- Le crochet `_("[…]")` délimite **une unité de traduction** — une phrase
  cohérente, pas une ligne physique.
- Templates : `{# #}` / `{% comment %}`, jamais `<!-- -->` (fuit au client).

## Front

Bootstrap 5.3 (+ son bundle JS) et htmx. Templates Django rendus **côté
serveur**, pas de SPA, responsive.

**CDN d'abord, repli local** sur les assets. Le repli couvre la panne du CDN,
**pas** le RGPD : dans le cas nominal l'IP du visiteur part chez le tiers
(cf. LG München, 2022, Google Fonts). Décision prise en connaissance de cause,
**ne pas y revenir**.

## Facturation

- **EUR uniquement.** Là où une conversion USD devra se brancher : un `# TODO`
  à l'endroit exact, pas une abstraction devinée d'avance.
- Forfait mensuel, plus **hors-forfait avec avertissement**.
- **Prévu mais pas construit** : échelle de prépaiement 6/12 mois, paliers
  (premium/gold). Ne pas les bâtir tant qu'ils ne sont pas demandés.
- **Paiement par virement IBAN.** Pas de Stripe ni de Paddle.

## Configuration

Motif : `TOML_CONFIG_FILE` en variable d'environnement, sinon
`~/.config/hqf_pdf_site.toml`. `tomllib.load` à l'import de `settings.py`,
chaque section lue par `.get()` **et validée**. En cas d'erreur :
`bad_config_file(msg)` imprime le message, le chemin du fichier et le contenu
de `install/config_template.toml` sur stderr, puis `exit(1)`.

Le fichier réel n'est **jamais** versionné ; `install/config_template.toml`
l'est.

## Git

- Branche `snake_case` par sujet, petits commits atomiques, `git push` après
  **chaque** commit.
- **Pas de rebase. Pas de PR.**
- **Jamais merger sans la parole du user.** (La délégation de merge en fin
  d'étape est une règle propre aux projets Rust ; elle ne s'applique **pas**
  ici.)
- Commits en `olivier.pons@gmail.com` — le gitconfig global ne doit pas
  contaminer ce dépôt.
- Zéro mention d'un assistant : pas de trailer `Co-Authored-By`, rien.

## Tests

`pytest-django`, `factory-boy`. **Un correctif sans test qui échouait avant le
correctif n'est pas un correctif.**
