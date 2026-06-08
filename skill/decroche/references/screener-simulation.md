<!-- voir aussi references/pipeline.md pour le workflow rechercher→postuler (P2-P5) -->
# Simuler le screener LLM 2026 (fidèlement)

`ats_screener_brief` te donne un **kit** : `machine_view_text` (le CV tel que la machine le lit APRÈS
parsing ATS — pas la jolie version), `rubric` (critères), `requirements` (exigences de l'offre).
Ton rôle : jouer le screener LLM **honnêtement et sévèrement**, comme Workday Illuminate / Greenhouse AI
/ un recruteur qui colle le CV dans un LLM.

## Méthode
1. **Lis uniquement `machine_view_text`**, pas le CV original. Si une info a été perdue au parsing,
   le screener ne la voit pas — pénalise comme le ferait la machine.
2. Pour chaque exigence (`requirements`) : cherche une **preuve citable** dans le texte (phrase précise).
   - Présente + chiffrée → fort. Présente sans preuve → moyen. Absente → manquante.
   - Ne déduis pas généreusement : un screener LLM 2026 (type Ashby) exige une **citation**, pas une supposition.
3. Évalue selon la `rubric` : pertinence titre/séniorité, couverture compétences avec **évidence**,
   impact quantifié, cohérence du parcours, signaux génériques/IA (« responsible for », listes d'outils sans contexte).

## Sortie
- **Fourchette** (ex. 6–7/10), **jamais un point** : 3 modèles LLM ne s'accordent que sur ~14 % des tops,
  ±2,5 rangs de variance. Donne la fourchette + le facteur d'incertitude.
- Verdict par exigence : `meets` / `partial` / `unknown(insufficient evidence)` / `missing`.
- 3 raisons concrètes qui plomberaient le score + 3 leviers honnêtes pour le remonter.

## Ce qui plaît au lecteur LLM (honnête)
- Phrases-preuves autoportantes : « Réduit le churn de 18 % en … » > « amélioration de la rétention ».
- Variété sémantique (plusieurs formulations d'un même concept) > répétition de mots-clés.
- Récit cohérent. Outils **démontrés en contexte** > liste d'outils.

## Ce qui plombe
- Phrasé générique (« responsible for / worked on / en charge de »), listes sans preuve, langage de template
  identique à des millions de CV IA (repéré en 30-60 s), bourrage.
