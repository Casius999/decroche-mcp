---
name: decroche
description: >-
  Rend un CV impossible à écarter — par l'ATS (parseur) ET le recruteur/screener LLM 2026 — honnêtement.
  USE WHENEVER the user wants to beat the ATS, pass résumé screening, tailor a CV to a job offer, fix a
  CV that keeps getting rejected/ghosted, optimize a resume for 2026 ATS + AI/LLM screeners, get an
  "unrejectable" CV, or asks "pourquoi mon CV est rejeté / recalé", "optimiser mon CV pour les ATS",
  "adapter mon CV à cette offre", "CV qui passe les robots", "make my CV ATS-proof", "why does my resume
  get rejected", "tailor my résumé to this job". Drives the decroche-mcp tools (cv_*, ats_*, match_*,
  market_*) through a 4-phase honest-optimization workflow. Triggers in FR and EN.
---

# decroche — CV impossible à écarter (honnête)

## Thèse (pourquoi ce skill existe)
En 2026 un CV affronte **deux lecteurs** : un **parseur ATS** (structure) ET un **screener LLM**
(Workday Illuminate, Greenhouse AI, iCIMS Copilot, Ashby, ou un recruteur qui colle le CV dans
ChatGPT/Claude). Battre l'un ne suffit pas. Ce skill optimise pour **les deux**, **par le mérite réel** —
jamais par la triche (détectée en 2026 → disqualification).

## Bornes d'intégrité (NON négociables)
- ❌ JAMAIS de texte blanc/caché, bourrage de mots-clés, injection de prompt anti-screener, métriques inventées.
- ✅ Mots-clés alignés sur des **compétences réelles** ; chiffres **réels** (demandés au candidat) ; preuves vérifiables.
- Quand une métrique manque : **demande-la au candidat** (voir `templates/metrics-interview.md`). N'invente jamais.
- `match_keyword_gap` distingue `addable_honestly` (compétence présente mais non formulée → resurface) de
  `genuinely_missing` (absente → ne pas fabriquer ; suggère de l'acquérir, pas de mentir).

## Prérequis
Serveur MCP `decroche-mcp` connecté. Outils disponibles (noms montés) :
`cv_parse`, `cv_xyz_scaffold`, `cv_verify_claims`, `cv_render` ·
`ats_parse_sim`, `ats_redflag_scan`, `ats_screener_brief`, `ats_score_report` ·
`match_score`, `match_keyword_gap` · `market_get`, `market_set`, `market_available`.
Inspecte le schéma live de chaque outil pour les paramètres exacts ; ci-dessous = l'ordre + l'intention.

---

## Workflow — 4 phases

### Phase 0 — Cadrage
1. Demande : le **fichier CV** (chemin), l'**offre** (texte ou URL), le **marché cible** (FR/US/UK/CA).
2. `market_set` sur le marché cible (sinon `market_get` = défaut FR). `market_available` liste les profils.
3. `cv_parse` le CV → JSON Resume + sections + `parse_confidence` + warnings.
   - Si `parse_confidence` bas ou warning `scanned_or_empty` → le CV est mal extractible : signale-le, demande une version texte/Word avant d'aller plus loin.

### Phase 1 — Diagnostic 360° (les deux lecteurs)
Lance en parallèle mental, puis synthétise :
- `ats_parse_sim(cv, ats_id)` pour le(s) ATS cible(s) (ou `generic` + `workday` par défaut) → **score parsabilité**, champs perdus, **casses** (2 colonnes, tableaux, contact en en-tête, dates, titres non-canoniques) avec remédiation.
- `ats_redflag_scan` → signaux repérés en 10 s (bullets sans chiffre, voix passive, trous, job-hopping, longueur, buzzwords, photo/infos perso non conformes au marché…).
- `match_score(cv, offre)` → score /100 + couverture exigence par exigence + `missing_must` + fit séniorité.
- `match_keyword_gap(cv, offre, n=5)` → top mots-clés manquants, chacun `addable_honestly` vs `genuinely_missing`.
- `ats_screener_brief(cv, offre, ats_id)` → **kit de simulation** (le CV *tel que la machine le voit* + rubrique + exigences). **Puis TOI (Claude), joue le screener LLM 2026** sur `machine_view_text` selon la rubrique (voir `references/screener-simulation.md`). **Donne une fourchette** (ex. 6–7/10), pas un point — 3 LLM ne s'accordent qu'à 14 %.

**Livrable Phase 1** (clair, actionnable) : score match /100 · 3 red flags vus en 10 s · 5 mots-clés manquants (addable vs missing) · casses ATS par fournisseur · *comment le screener LLM te lit* (forces/risques).

### Phase 2 — Réécriture honnête XYZ
1. `cv_xyz_scaffold(cv)` → squelette par bullet : verbe, X, Y présent ?, Z, `weak_verb`, `missing_metric_prompt`.
2. Réécris chaque bullet en **XYZ** — « Accompli **X**, mesuré par **Y**, en faisant **Z** » :
   - Verbe d'action fort ; supprime voix passive et verbes faibles (`responsible for`, `worked on`…).
   - **Y manquant → demande le vrai chiffre** au candidat (`templates/metrics-interview.md`). Jamais d'invention.
   - Intègre **naturellement** les mots-clés `addable_honestly` (densité raisonnable, anti-bourrage).
   - Corrige les red flags de Phase 1 (longueur, dates `Mois AAAA`, photo/infos selon marché).
3. `cv_verify_claims(cv)` → pour chaque affirmation forte, ajoute/sollicite une **preuve** (lien repo/portfolio, rapport, attestation, référence). Inattaquable = **prouvable**.

### Phase 3 — Anti-algo + anti-scroll (et preuve)
1. `cv_render(cv, market_id, out_dir)` → **(a)** `.docx` **ATS-safe** + **(b)** HTML « stop-scroll » localisé (+ PDF si dispo) + **(c)** JSON Resume / texte maître.
2. **Preuve ATS** : `cv_render` retourne `ats_safe_proof: dict[ats_id → parsability_score]` — scores du round-trip `ats_parse_sim` sur le `.docx` généré, intégrés dans le `Render` renvoyé. Vérifie parsabilité ↑ et **zéro casse** structurelle (pas d'outil séparé `ats_render`).
3. `ats_score_report(cv, offer_text, ats_id)` → `ScoreReport` avec `parsability` (0-100), `match` (0-100 si offre fournie), `screener_readiness` ∈ **low | medium | high**, `redflag_count`, et `delta` (si avant/après demandé). Montre le gain.
4. Re-joue le screener LLM (Phase 1) sur le nouveau `machine_view_text` → confirme l'amélioration.

**Livrable final** : 2 fichiers (ATS-safe + humain), le rapport avant/après, et la liste des preuves à fournir.

### Phase 4 — Extension (hors P1, à venir)
Pipeline complet `decroche` 360° : sourcing multi-plateforme + intel recruteur + candidature *apply-at-source* (gated) + entretien + négociation + analytics. Modules P2-P5 — annonce-les comme prochaines étapes si l'utilisateur veut aller au-delà du CV.

---

## Règles d'or
- Toujours **les deux lecteurs** (ATS + LLM). Un CV qui passe l'ATS mais lu pauvrement par le LLM échoue.
- **Substance > cosmétique** : impact chiffré prouvé > mise en forme.
- **Honnêteté = stratégie** : en 2026 la triche est détectée et bannie ; le mérite réel, bien formulé, gagne.
- Score screener LLM = **fourchette + incertitude**, jamais une vérité absolue.
- Adapte au **marché** (`market_get`) : photo/âge/longueur/orthographe/dates diffèrent FR vs US/UK/CA.

## Références
- `references/screener-simulation.md` — comment jouer fidèlement le screener LLM 2026 sur le kit.
- `references/honesty-guardrails.md` — la frontière honnête/triche, en détail.
- `templates/metrics-interview.md` — questions pour extraire les vrais chiffres (remplir Y honnêtement).
