# Propositions — refonte commerciale de la home + architecture « possibilités → exemples » + plan SEO

Document de propositions **à valider**. Rien ici n'est construit dans le code : ce sont des décisions
commerciales et éditoriales qui appartiennent au user. Les correctifs techniques non ambigus (fuite de
commentaire, thème clair/sombre) sont, eux, déjà livrés sur la branche `fix_comment_leak_and_theme`.

Rappel des faits figés (ne pas réinventer) :

- Prix connu et **décidé** : offre « Illimité » à **79 €/mois**. Tout autre palier = `À DÉFINIR`.
- Paiement hybride : Stripe (SaaS / petits montants) + virement IBAN (grosses licences définitives).
- SEO = priorité n°1 absolue (seul levier d'acquisition).
- i18n mono-domaine, canonique `www.hqf-pdf.com`, langues `fr` / `en`.
- Le modèle `billing.Plan` sait déjà exprimer un multi-paliers : `monthly_price`, `included_pages`,
  `included_requests` (`None` = illimité), `overage_page_price`, `overage_request_price`. La grille
  tarifaire proposée ci-dessous se mappe donc **directement** sur des lignes `Plan` existantes, sans
  nouveau modèle.

---

## 1. Catalogue des capacités vendables (source de vérité)

Liste exhaustive de ce que hqf-pdf sait faire, à exposer sur la home sous forme de cartes cliquables.
Chaque capacité mène à sa page d'exemple (section 3). Regroupées en familles pour la lisibilité SEO.

**Famille « Texte & mise en page »**
- Génération de PDF depuis une requête (cœur du service)
- Texte riche : runs stylés, gras/italique, soulignement
- Flux de texte multi-colonnes, césure et coupure de lignes
- Tableaux : bordures, marges, padding réglables par côté

**Famille « Documents interactifs »**
- Formulaires AcroForm : cases à cocher, listes déroulantes, boutons radio, champ de signature
- Liens (internes et externes)
- Signets (table des matières navigable)
- Étiquettes de page

**Famille « Images & couleur »**
- Insertion d'images
- Gestion de la couleur

**Famille « Codes-barres »**
- Code 128, QR Code, EAN-13, UPC-A, EAN-8

**Famille « Conformité & archivage »**
- PDF/A-3 (archivage long terme)
- Factur-X (facture électronique, échéances françaises 2026/2027)

**Famille « Intégration »**
- Utilisable en Rust **et** en Python (bindings), Linux / Windows / macOS
- API HTTP : on envoie une requête de rendu, on récupère le PDF

> Décision user : ordre d'affichage des familles (impact SEO — la première famille pèse le plus),
> et wording commercial de chaque carte.

---

## 2. Structure de pages proposée

Arborescence i18n (préfixe `/fr/` ou `/en/`), toutes indexables, contenu serveur-rendu (pas de JS
bloquant pour le contenu principal) :

```
/                         Home (vitrine complète — section 3)
/features/                Index des capacités (le catalogue en pleine page)
/features/<slug>/         Une page par capacité, avec exemple concret + rendu
/pricing/                 Grille tarifaire détaillée (résumé sur la home)
/docs/ (ou /api/)         Démarrage rapide : compte → clé → requête (existe déjà en germe)
/faq/                     FAQ (alimente le JSON-LD FAQPage)
```

Pages transverses déjà présentes à conserver : `signup`, `login`, `dashboard`, `subscribe`,
conditions d'abonnement.

> Décision user : slugs définitifs (`/features/` vs `/fonctionnalites/` — attention, en mono-domaine
> i18n le slug est souvent gardé identique et seul le préfixe de langue change ; recommandation :
> garder les slugs en anglais pour la stabilité des URL, le contenu étant traduit).

---

## 3. Sections de la home (dans l'ordre d'affichage proposé)

1. **Hero orienté SEO**
   - `<h1>` unique portant le bénéfice + le mot-clé principal (ex. « Générer des PDF par API :
     tableaux, Factur-X, formulaires »). Le `<h1>` actuel (« Générez vos PDF depuis votre
     application ») est bon mais peut être enrichi des mots-clés porteurs.
   - Sous-titre : une phrase de proposition de valeur.
   - 2 CTA : « Créer un compte » (primaire) + « Voir les possibilités » (ancre vers le catalogue).

2. **Bandeau de confiance / conformité** (court)
   - Factur-X, PDF/A-3, Rust + Python, multi-OS. Rassure et charge en mots-clés.

3. **Catalogue de capacités cliquables** (le manque n°1 signalé)
   - Grille de cartes, une par capacité (section 1), groupées par famille avec un `<h2>` par famille.
   - Chaque carte = titre `<h3>` + une ligne descriptive + lien vers `/features/<slug>/`.
   - HTML sémantique, texte réel indexable (pas d'icônes seules).

4. **Comment ça marche** (les 3 étapes actuelles — à conserver, mais après le catalogue, pas seul)
   - Créer un compte → récupérer la clé API → envoyer une requête.

5. **Aperçus d'exemples** (« cliquer sur une possibilité pour voir l'exemple »)
   - 3 à 6 vignettes de rendus concrets (miniature PNG du PDF + lien vers la page d'exemple).
   - Recommandation technique : générer les miniatures côté serveur et les servir en statique
     (pas d'iframe PDF lourde sur la home). Un vrai rendu cliquable vit sur `/features/<slug>/`.

6. **Grille tarifaire résumée** (section 4) + lien vers `/pricing/`.

7. **FAQ** (section 5) — alimente le JSON-LD.

8. **CTA final** + footer.

> Décision user : nombre de vignettes d'exemples en home, et lesquelles mettre en avant.

---

## 4. Grille tarifaire (placeholders explicites)

Une seule valeur est figée. Tout le reste est `À DÉFINIR` et **doit être tranché par le user** avant
mise en ligne. Mapping direct sur `billing.Plan`.

| Palier                | Prix mensuel | Pages incluses | Requêtes incl. | Surcoût / page | Cible                          |
|-----------------------|--------------|----------------|----------------|----------------|--------------------------------|
| Gratuit / Découverte  | `À DÉFINIR`  | `À DÉFINIR`    | `À DÉFINIR`    | `À DÉFINIR`    | essai, PDF filigranés          |
| Intermédiaire(s)      | `À DÉFINIR`  | `À DÉFINIR`    | `À DÉFINIR`    | `À DÉFINIR`    | `À DÉFINIR` (combien de paliers ?) |
| **Illimité**          | **79 €/mois**| illimité       | illimité       | —              | usage intensif SaaS            |
| Licence définitive    | sur devis (IBAN) | —          | —              | —              | grosses licences perpétuelles  |

Placeholders `À DÉFINIR` à trancher :

- `À DÉFINIR` : existence et contenu d'un palier **Gratuit** (le mémo produit évoque un tier gratuit
  filigrané comme lead commercial — à confirmer comme offre publique).
- `À DÉFINIR` : nombre de paliers intermédiaires entre gratuit et Illimité, et leurs prix/quotas.
- `À DÉFINIR` : prix et modalités de la licence perpétuelle (virement IBAN).
- `À DÉFINIR` : TTC/HT affiché (le site annonce déjà « montants en euros, HT »).
- `À DÉFINIR` : ce que couvre exactement « Illimité » (pages ET requêtes illimitées ? fair-use ?).

> Rappel produit : l'anti-fraude est un lead commercial, pas un blocage brut — le wording du palier
> gratuit doit orienter le prospect intensif vers l'offre payante, pas le culpabiliser.

---

## 5. FAQ (pour le contenu + le JSON-LD FAQPage)

Questions proposées (réponses à rédiger/valider par le user) :

- Ai-je besoin d'installer une bibliothèque PDF de mon côté ? → Non, tout passe par l'API.
- Quels langages / systèmes sont supportés ? → Rust, Python ; Linux, Windows, macOS.
- Puis-je générer des factures électroniques conformes (Factur-X) ? → Oui.
- Comment paie-t-on ? → Stripe pour l'abonnement, virement IBAN pour les licences définitives.
- Que se passe-t-il si je dépasse mon quota ? → Le rendu continue, le surplus est facturé, on est
  prévenu avant.
- Mes données / polices sont-elles isolées ? → Oui (magasin de polices par client).
- Existe-t-il un essai gratuit ? → `À DÉFINIR`.

---

## 6. Plan SEO concret

**Balises par page**
- `<title>` unique et travaillé par page (60 car. max), mot-clé en tête. Le `{% block title %}`
  existe déjà : le remplir spécifiquement sur chaque page, jamais le titre générique.
- `<meta name="description">` unique par page (150–160 car.) — **manquante aujourd'hui**, à ajouter
  dans `base.html` via un `{% block meta_description %}`.
- Un seul `<h1>` par page, hiérarchie `<h2>`/`<h3>` respectée (le catalogue impose cette rigueur).

**Open Graph / Twitter Cards**
- `og:title`, `og:description`, `og:type=website`, `og:url` (canonique), `og:image` (visuel dédié),
  `og:locale` + `og:locale:alternate`. À ajouter en blocs surchargeable dans `base.html`.

**Données structurées (JSON-LD)** — un `<script type="application/ld+json">` par type :
- `SoftwareApplication` (ou `Product`) sur la home et `/pricing/` : nom, description,
  `applicationCategory`, `offers` (les paliers, dont Illimité 79 €/mois), `operatingSystem`
  (Linux/Windows/macOS).
- `FAQPage` sur `/faq/` (et éventuellement le bloc FAQ de la home), à partir de la section 5.
- `BreadcrumbStructuredData` sur les pages `/features/<slug>/`.

**Canonique + hreflang (i18n mono-domaine)**
- `<link rel="canonical">` absolu par page, sur `www.hqf-pdf.com`.
- `<link rel="alternate" hreflang="fr">` / `hreflang="en">` / `hreflang="x-default">` pointant vers
  les variantes de langue de la **même** page. Générables depuis `LANGUAGES` + `request.path`.

**Sitemap + robots**
- `django.contrib.sitemaps` : une sitemap listant home, `/features/`, chaque `/features/<slug>/`,
  `/pricing/`, `/faq/`, avec les alternances hreflang. `robots.txt` pointant la sitemap.
- Ces deux endpoints restent **hors** `i18n_patterns` (comme `i18n/` et `billing/` aujourd'hui).

**Performance / indexabilité**
- Contenu principal en HTML serveur (déjà le cas). Le thème est piloté par un snippet inline
  minuscule (déjà livré) : aucun impact SEO.
- Miniatures d'exemples en images statiques optimisées avec `alt` descriptif ; lazy-loading sauf
  hero.

---

## 7. Récapitulatif des décisions qui appartiennent au user

1. **Prix** : palier gratuit (oui/non + contenu), nombre et prix des paliers intermédiaires, prix
   de la licence perpétuelle, définition exacte d'« Illimité », affichage HT/TTC.
2. **Wording commercial** : `<h1>` du hero, phrase de valeur, titres des cartes de capacités,
   réponses de la FAQ, textes des CTA.
3. **Visuels** : miniatures de rendus d'exemples à produire, image Open Graph, éventuelle
   iconographie des familles.
4. **Arborescence** : slugs définitifs des pages `/features/`, `/pricing/`, `/faq/` (recommandation :
   slugs en anglais, contenu traduit).
5. **Priorisation SEO** : ordre d'affichage des familles de capacités (la première pèse le plus).
6. **Contenu à ne pas exposer** : rappel règle repo — zéro mention de l'éditeur/produit payant
   remplacé nulle part dans les textes commerciaux.

---

## 8. Ce qui est déjà livré (hors propositions)

Branche `fix_comment_leak_and_theme` :
- Correction de la fuite de commentaire multiligne `{# #}` (Django ne reconnaît `{# #}` que sur une
  seule ligne ; un `{#` suivi d'un saut de ligne fuit en clair dans le HTML servi). Basculé en
  `{% comment %}`.
- Thème clair **et** sombre : `data-bs-theme` de Bootstrap 5.3 piloté par un snippet inline
  anti-FOUC, respect de `prefers-color-scheme`, toggle persistant en `localStorage` dans la navbar.
  Chaîne d'aria-label traduite fr/en.
