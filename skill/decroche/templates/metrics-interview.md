# Interview « métriques » — extraire les VRAIS chiffres

Quand `cv_xyz_scaffold` renvoie `missing_metric_prompt` (Y absent), pose ces questions au candidat pour
remplir le **Y** honnêtement. But : transformer un devoir vague en accomplissement chiffré **réel**.

## Pour chaque bullet sans métrique, demander :
1. **Ampleur** — combien ? (utilisateurs, clients, €/$, lignes, tickets, requêtes, taille d'équipe, périmètre)
2. **Variation** — de combien ça a changé ? (avant → après, %, ×, points). « Tu te souviens de l'ordre de grandeur ? »
3. **Temps** — en combien de temps ? (délai réduit, livraison en N semaines, fréquence)
4. **Échelle/portée** — sur quel volume / quelle base ? (région, segment, % du CA, nb de pays)
5. **Résultat business** — et donc ? (revenu, coût évité, churn, NPS, conversion, SLA, incident)
6. **Preuve** — un lien/artefact existe ? (dashboard, rapport, repo, presse, attestation, référence)

## Cadrage honnête
- Si le candidat n'a qu'un **ordre de grandeur** : formuler « ~ », « plus de », « réduit d'environ » — honnête.
- Si **aucun chiffre fiable** : garder une formulation qualitative précise (action + objet + impact) **sans** chiffre. Ne pas inventer.
- Privilégier les chiffres **vérifiables** ou défendables en entretien (le candidat doit pouvoir les expliquer).

## Exemple
Avant : « Responsable de l'amélioration de la performance du site. »
Q : ampleur ? → « ~2 M visiteurs/mois » · variation ? → « LCP 4,1 s → 1,9 s » · comment ? → « lazy-loading + CDN »
Après (XYZ, réel) : « Réduit le LCP de 4,1 s à 1,9 s sur un site à ~2 M visiteurs/mois en déployant lazy-loading et un CDN. »
