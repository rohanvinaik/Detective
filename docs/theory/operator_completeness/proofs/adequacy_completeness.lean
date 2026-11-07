import Mathlib

open Set

universe u
variable {R : Type u}

/-- **Footprint** of an output operator `p : R → R`: the set of values it changes.
(Paper §2, Def 2.2.) For adequacy this is the whole of `p` that matters (Prop 2.4). -/
def Mov (p : R → R) : Set R := {r | p r ≠ r}

/-- **ScoreAt** `I O F` — the family of footprints `F` is fully killed at reachable set `I`
and finite observed set `O`: every footprint meeting `I` (a *non-equivalent* mutant) also meets `O`
(is *killed*). This is `score = 1` for the family `F`. (Paper §2, Def 2.3, via Prop 2.4.) -/
def ScoreAt (I : Set R) (O : Finset R) (F : Set (Set R)) : Prop :=
  ∀ S ∈ F, (S ∩ I).Nonempty → ∃ b ∈ O, b ∈ S

/-- **Adequacy-completeness** (paper §3, Def 3.1). For every reachable `I` and finite observed `O ⊆ I`,
a full score against `Π` forces a full score against `Γ`. -/
def Complete (Pi Gamma : Set (Set R)) : Prop :=
  ∀ (I : Set R) (O : Finset R), (↑O : Set R) ⊆ I → ScoreAt I O Pi → ScoreAt I O Gamma

/-- **Theorem 3.2 (footprint characterization).** For a *finite* `Π`, adequacy-completeness for `Γ`
holds iff every target footprint is covered, at each point, by a `Π`-footprint contained in it. -/
theorem footprint_characterization (Pi Gamma : Set (Set R)) (hfin : Pi.Finite) :
    Complete Pi Gamma ↔ ∀ t ∈ Gamma, ∀ b ∈ t, ∃ s ∈ Pi, b ∈ s ∧ s ⊆ t := by
  constructor
  · -- Complete → condition (the constructive direction).
    -- Given a would-be failure (t, b), build a program (I, O) that kills all Π but survives g.
    intro hComp t htΓ b hbt
    by_contra hcon
    classical
    -- Every Π-footprint through b has an escape point outside t.
    have hesc : ∀ s ∈ Pi, b ∈ s → ∃ a, a ∈ s ∧ a ∉ t := by
      intro s hs hbs
      by_contra hno
      push_neg at hno
      exact hcon ⟨s, hs, hbs, fun a ha => hno a ha⟩
    -- A total escape function (dummy b where no escape is needed).
    set e : Set R → R := fun s => if h : ∃ a, a ∈ s ∧ a ∉ t then h.choose else b with he_def
    have he_mem : ∀ s, (∃ a, a ∈ s ∧ a ∉ t) → e s ∈ s ∧ e s ∉ t := by
      intro s h
      rw [he_def]
      simp only [dif_pos h]
      exact ⟨h.choose_spec.1, h.choose_spec.2⟩
    -- The observed set: one escape point per Π-footprint through b.
    set A : Finset R := (hfin.toFinset.filter (fun s => b ∈ s)).image e with hA_def
    have hA_not_t : ∀ x ∈ A, x ∉ t := by
      intro x hx
      simp only [hA_def, Finset.mem_image, Finset.mem_filter, Set.Finite.mem_toFinset] at hx
      obtain ⟨s, ⟨hsPi, hbs⟩, hex⟩ := hx
      have := (he_mem s (hesc s hsPi hbs)).2
      rwa [hex] at this
    have hA_hits : ∀ s ∈ Pi, b ∈ s → e s ∈ A ∧ e s ∈ s := by
      intro s hsPi hbs
      refine ⟨?_, (he_mem s (hesc s hsPi hbs)).1⟩
      simp only [hA_def, Finset.mem_image, Finset.mem_filter, Set.Finite.mem_toFinset]
      exact ⟨s, ⟨hsPi, hbs⟩, rfl⟩
    -- Reachable I = {b} ∪ A; observed O = A. Every non-equivalent Π-mutant dies here.
    have hScorePi : ScoreAt (insert b (↑A : Set R)) A Pi := by
      intro S hSPi hSne
      by_cases hbS : b ∈ S
      · obtain ⟨heA, heS⟩ := hA_hits S hSPi hbS
        exact ⟨e S, heA, heS⟩
      · obtain ⟨c, hcS, hcI⟩ := hSne
        rw [Set.mem_insert_iff] at hcI
        rcases hcI with hcb | hcA
        · exact absurd (hcb ▸ hcS) hbS
        · exact ⟨c, Finset.mem_coe.mp hcA, hcS⟩
    -- But the target g survives (its footprint meets I at b, misses O = A).
    obtain ⟨c, hcA, hct⟩ :=
      hComp (insert b (↑A : Set R)) A (Set.subset_insert _ _) hScorePi t htΓ
        ⟨b, hbt, Set.mem_insert _ _⟩
    exact hA_not_t c hcA hct
  · -- condition → Complete
    intro hcond I O hOI hPi t htΓ htI
    obtain ⟨b, hbt, hbI⟩ := htI
    obtain ⟨s, hsPi, hbs, hst⟩ := hcond t htΓ b hbt
    obtain ⟨c, hcO, hcs⟩ := hPi s hsPi ⟨b, hbs, hbI⟩
    exact ⟨c, hcO, hst hcs⟩

/-- **Corollary 4.1 (value-guard basis).** `Π` is absolutely complete (complete for *all* footprints)
iff it contains every singleton `{b}` — the value guards. -/
theorem absolute_iff_guards (Pi : Set (Set R)) (hfin : Pi.Finite) :
    Complete Pi (Set.univ) ↔ ∀ b : R, ({b} : Set R) ∈ Pi := by
  rw [footprint_characterization Pi Set.univ hfin]
  constructor
  · intro h b
    obtain ⟨s, hsPi, hbs, hsb⟩ := h {b} (Set.mem_univ _) b rfl
    rwa [Set.eq_of_subset_of_subset hsb (Set.singleton_subset_iff.mpr hbs)] at hsPi
  · intro h t _ b hbt
    exact ⟨{b}, h b, rfl, Set.singleton_subset_iff.mpr hbt⟩

/-- **Theorem 4.5 (the ceiling).** A full score against *all* footprints holds iff the suite observes
every reachable output: `ScoreAt I O univ ↔ I ⊆ O`. -/
theorem ceiling (I : Set R) (O : Finset R) :
    ScoreAt I O (Set.univ) ↔ I ⊆ (↑O : Set R) := by
  constructor
  · intro h b hbI
    obtain ⟨c, hcO, hcb⟩ := h {b} (Set.mem_univ _) ⟨b, rfl, hbI⟩
    rw [Set.mem_singleton_iff] at hcb
    exact hcb ▸ (Finset.mem_coe.mpr hcO)
  · intro h S _ hSI
    obtain ⟨b, hbS, hbI⟩ := hSI
    exact ⟨b, Finset.mem_coe.mp (h hbI), hbS⟩

/-- **A value-guard family is sufficient for every target** (a consequence of Corollary 4.1), in particular
for the higher-order mutants `⟨Π⟩`. This is NOT a coupling result: it holds because such a family already
covers every footprint, so composition is irrelevant. For other regimes coupling is not entailed
(Proposition 6.1, `coupling_fails`). -/
theorem coupling (Pi Gamma : Set (Set R)) (hfin : Pi.Finite) (hguards : ∀ b : R, ({b} : Set R) ∈ Pi) :
    Complete Pi Gamma := by
  rw [footprint_characterization Pi Gamma hfin]
  intro t _ b hbt
  exact ⟨{b}, hguards b, rfl, Set.singleton_subset_iff.mpr hbt⟩

/-- **Proposition 7.1 (program-independent subsumption).** Every observed set that kills `p`'s mutant
also kills `g`'s, iff footprints are contained: `Mov p ⊆ Mov g`. -/
theorem subsumes_iff_subset (p g : R → R) :
    (∀ O : Finset R, (∃ b ∈ O, b ∈ Mov p) → (∃ b ∈ O, b ∈ Mov g)) ↔ Mov p ⊆ Mov g := by
  constructor
  · intro h r hr
    obtain ⟨c, hc, hcg⟩ := h {r} ⟨r, Finset.mem_singleton_self r, hr⟩
    rw [Finset.mem_singleton] at hc
    exact hc ▸ hcg
  · intro hsub O ⟨b, hbO, hbp⟩
    exact ⟨b, hbO, hsub hbp⟩

/-- **Proposition 7.2 (detection factors through the footprint).**
`Det(p ∘ f) = f⁻¹(Mov p)`, so it depends on `f` only through the reachable partition. -/
theorem det_factors (p : R → R) {D : Type*} (f : D → R) :
    {x | p (f x) ≠ f x} = f ⁻¹' (Mov p) := rfl

/-- **Corollary 4.3 (extreme mutation is sufficient iff `n = 2`).** The Descartes constant family
(footprints `{c}ᶜ`) is absolutely complete iff the codomain has exactly two values. -/
theorem constants_iff_card_two [Fintype R] [DecidableEq R] [Nonempty R] :
    Complete {S : Set R | ∃ c : R, S = ({c}ᶜ : Set R)} (Set.univ) ↔ Fintype.card R = 2 := by
  have hfin : {S : Set R | ∃ c : R, S = ({c}ᶜ : Set R)}.Finite := Set.toFinite _
  rw [absolute_iff_guards _ hfin]
  simp only [Set.mem_setOf_eq]
  constructor
  · intro h
    obtain ⟨b⟩ := (inferInstance : Nonempty R)
    obtain ⟨c, hc⟩ := h b
    have hbc : b ≠ c := by
      have hb : b ∈ ({c}ᶜ : Set R) := by rw [← hc]; rfl
      simpa using hb
    have huniv : (Finset.univ : Finset R) = {b, c} := by
      ext x
      simp only [Finset.mem_univ, Finset.mem_insert, Finset.mem_singleton, true_iff]
      by_cases hxc : x = c
      · exact Or.inr hxc
      · refine Or.inl ?_
        have hx : x ∈ ({c}ᶜ : Set R) := by simpa using hxc
        rw [← hc] at hx
        simpa using hx
    rw [← Finset.card_univ, huniv, Finset.card_pair hbc]
  · intro hcard b
    rw [← Finset.card_univ] at hcard
    obtain ⟨a, a', haa', huniv⟩ := Finset.card_eq_two.mp hcard
    have hall : ∀ x : R, x = a ∨ x = a' := by
      intro x
      have hx : x ∈ ({a, a'} : Finset R) := huniv ▸ Finset.mem_univ x
      simpa [Finset.mem_insert, Finset.mem_singleton] using hx
    rcases hall b with hba | hba
    · refine ⟨a', ?_⟩
      subst hba
      ext x
      simp only [Set.mem_singleton_iff, Set.mem_compl_iff]
      constructor
      · rintro rfl; exact haa'
      · intro hx; rcases hall x with h1 | h2
        · exact h1
        · exact absurd h2 hx
    · refine ⟨a, ?_⟩
      subst hba
      ext x
      simp only [Set.mem_singleton_iff, Set.mem_compl_iff]
      constructor
      · rintro rfl; exact fun h => haa' h.symm
      · intro hx; rcases hall x with h1 | h2
        · exact absurd h1 hx
        · exact h2

/-- **Theorem 8.1 (minimum certifying suite), lower bound.** Any suite certifying full output coverage
observes at least `|I|` distinct values. -/
theorem certify_lb (I : Set R) (O : Finset R)
    (h : ScoreAt I O (Set.univ)) : I.ncard ≤ O.card := by
  have hsub : I ⊆ (↑O : Set R) := (ceiling I O).mp h
  have h2 : I.ncard ≤ (↑O : Set R).ncard := Set.ncard_le_ncard hsub O.finite_toSet
  simpa using h2

/-- **Theorem 8.1 (minimum certifying suite), achievability, observed-set level.** Observing exactly `|I|`
values certifies full output coverage. The program-level form, which builds the suite, is `prog_certify_ub`. -/
theorem certify_ub (I : Set R) (hIfin : I.Finite) :
    ∃ O : Finset R, ScoreAt I O (Set.univ) ∧ O.card = I.ncard := by
  refine ⟨hIfin.toFinset, ?_, ?_⟩
  · rw [ceiling, hIfin.coe_toFinset]
  · haveI : Fintype ↥I := hIfin.fintype
    rw [Set.ncard_eq_toFinset_card' I]
    congr 1
    apply Finset.coe_injective
    rw [hIfin.coe_toFinset, Set.coe_toFinset]

/-! ### The program ↔ footprint bridge (§2–§3): sufficiency stated over real programs and suites. -/

/-- **Program-level score.** A suite `T : Finset D` gives `score = 1` against operator family `Π` on
program `f : D → R` iff every non-equivalent mutant `p ∘ f` (footprint meets the reachable set) is killed
(some test in `T` exposes it). -/
def ProgScore (Pi : Set (R → R)) {D : Type*} (f : D → R) (T : Finset D) : Prop :=
  ∀ p ∈ Pi, (Mov p ∩ Set.range f).Nonempty → ∃ x ∈ T, p (f x) ≠ f x

/-- **Program-level adequacy-completeness.** Over *every* program `f : D → R` and *every* finite suite
`T`, a full `Π`-score forces a full `Γ`-score. This is Def 3.1 stated directly on programs and suites. -/
def ProgComplete (Pi Gamma : Set (R → R)) : Prop :=
  ∀ (D : Type u) (f : D → R) (T : Finset D), ProgScore Pi f T → ProgScore Gamma f T

/-- **Prop 2.4 (the reduction), formal.** Program-level score against `Π` equals the footprint-level score
`ScoreAt` at the reachable set `range f` and observed set `f '' T`, on the footprint family `Mov '' Π`. -/
theorem progScore_iff_scoreAt [DecidableEq R] (Pi : Set (R → R)) {D : Type*} (f : D → R) (T : Finset D) :
    ProgScore Pi f T ↔ ScoreAt (Set.range f) (T.image f) (Mov '' Pi) := by
  constructor
  · intro h S hS hSne
    obtain ⟨p, hpPi, rfl⟩ := hS
    obtain ⟨x, hxT, hxp⟩ := h p hpPi hSne
    exact ⟨f x, Finset.mem_image_of_mem f hxT, hxp⟩
  · intro h p hpPi hne
    obtain ⟨b, hbO, hbp⟩ := h (Mov p) ⟨p, hpPi, rfl⟩ hne
    obtain ⟨x, hxT, rfl⟩ := Finset.mem_image.mp hbO
    exact ⟨x, hxT, hbp⟩

/-- **Realizability.** Every reachable/observed pair `(I, O)` with `O ⊆ I` and `I` nonempty is realized by
a genuine program `f : R → R` and suite `T = O`: `range f = I`, `O.image f = O`. -/
theorem realizable [DecidableEq R] (I : Set R) (hI : I.Nonempty) (O : Finset R) (hOI : (↑O : Set R) ⊆ I) :
    ∃ f : R → R, Set.range f = I ∧ O.image f = O := by
  classical
  obtain ⟨i₀, hi₀⟩ := hI
  refine ⟨fun x => if x ∈ I then x else i₀, ?_, ?_⟩
  · ext y
    constructor
    · rintro ⟨x, rfl⟩
      by_cases hx : x ∈ I <;> simp [hx, hi₀]
    · intro hy
      exact ⟨y, by simp [hy]⟩
  · have heq : O.image (fun x => if x ∈ I then x else i₀) = O.image id := by
      apply Finset.image_congr
      intro x hx
      have hxI : x ∈ I := hOI hx
      simp [hxI]
    rw [heq, Finset.image_id]

/-- **The bridge.** Program-level completeness of operator families equals footprint-level completeness of
their footprint families. -/
theorem progComplete_iff_complete [DecidableEq R] (Pi Gamma : Set (R → R)) :
    ProgComplete Pi Gamma ↔ Complete (Mov '' Pi) (Mov '' Gamma) := by
  constructor
  · intro h I O hOI hsc
    rcases I.eq_empty_or_nonempty with hIe | hIne
    · intro S _ hSne
      obtain ⟨b, _, hbI⟩ := hSne
      rw [hIe] at hbI
      exact ((Set.mem_empty_iff_false b).mp hbI).elim
    · obtain ⟨f, hrange, himage⟩ := realizable I hIne O hOI
      have hpc := h R f O
      rw [progScore_iff_scoreAt, progScore_iff_scoreAt, hrange, himage] at hpc
      exact hpc hsc
  · intro h D f T hsc
    rw [progScore_iff_scoreAt] at hsc ⊢
    refine h (Set.range f) (T.image f) ?_ hsc
    rw [Finset.coe_image]
    exact Set.image_subset_range f _

/-- **Theorem 3.2, over programs.** The program-level characterization: for a finite operator family,
adequacy-completeness holds iff every target footprint is covered by contained `Π`-footprints. -/
theorem progComplete_characterization [DecidableEq R] (Pi Gamma : Set (R → R)) (hfin : Pi.Finite) :
    ProgComplete Pi Gamma ↔ ∀ g ∈ Gamma, ∀ b ∈ Mov g, ∃ p ∈ Pi, b ∈ Mov p ∧ Mov p ⊆ Mov g := by
  rw [progComplete_iff_complete, footprint_characterization _ _ (hfin.image Mov)]
  constructor
  · intro h g hg b hb
    obtain ⟨S, hS, hbS, hSsub⟩ := h (Mov g) ⟨g, hg, rfl⟩ b hb
    obtain ⟨p, hpPi, rfl⟩ := hS
    exact ⟨p, hpPi, hbS, hSsub⟩
  · intro h t ht b hb
    obtain ⟨g, hg, rfl⟩ := ht
    obtain ⟨p, hpPi, hbp, hsub⟩ := h g hg b hb
    exact ⟨Mov p, ⟨p, hpPi, rfl⟩, hbp, hsub⟩

/-- **Proposition 6.1 (coupling fails for output mutation).** A first-order family can score 1 while a
non-equivalent *higher-order* mutant (a composition) survives. Witness on `Fin 3`: `a : 0 ↦ 1, 1 ↦ 0, 2 ↦ 1`,
reachable set `I = {0,2}`, observed set `O = {0}`. Then `Mov a = ⊤` (so `a ∘ f` is killed at `0`), while
`Mov (a ∘ a) = {2}` meets `I` (non-equivalent) and misses `O` (unkilled). So killing every first-order
`{a}`-mutant does not entail killing the higher-order mutant `a ∘ a`. -/
theorem coupling_fails :
    ∃ (a : Fin 3 → Fin 3) (I : Set (Fin 3)) (O : Finset (Fin 3)),
      ScoreAt I O (Mov '' {a}) ∧
      ¬ ScoreAt I O (Mov '' ({a, a ∘ a} : Set (Fin 3 → Fin 3))) := by
  refine ⟨![1, 0, 1], {0, 2}, {0}, ?_, ?_⟩
  · rintro S ⟨p, hp, rfl⟩ _
    rw [Set.mem_singleton_iff] at hp; subst hp
    refine ⟨0, Finset.mem_singleton_self 0, ?_⟩
    simp only [Mov, Set.mem_setOf_eq]; decide
  · intro h
    obtain ⟨b, hbO, hb⟩ := h (Mov (![1, 0, 1] ∘ ![1, 0, 1]))
      (Set.mem_image_of_mem _ (Set.mem_insert_iff.mpr (Or.inr rfl)))
      ⟨2, by simp only [Set.mem_inter_iff, Mov, Set.mem_setOf_eq]; exact ⟨by decide, by decide⟩⟩
    rw [Finset.mem_singleton] at hbO; subst hbO
    simp only [Mov, Set.mem_setOf_eq] at hb; revert hb; decide

/-! ### Theorem 3.2b and §9 (beyond the exact oracle). Proofs closed by Wayfinder → Aristotle,
Lean-verified (`sorries_remaining: 0`); axiom-audited in `Audit.lean`. Not hand-authored. -/

/-- **Theorem 3.2b (footprint characterization, general `Π`).** For arbitrary `Π` and `Γ`,
adequacy-completeness holds iff for every target footprint `t`, point `b ∈ t`, and finite `F` disjoint
from `t`, some `Π`-footprint contains `b` while avoiding `F`. (Paper §3, Theorem 3.2b.) -/
theorem footprint_characterization_general (Pi Gamma : Set (Set R)) :
    Complete Pi Gamma ↔
      ∀ t ∈ Gamma, ∀ b ∈ t, ∀ F : Finset R, Disjoint (↑F : Set R) t →
        ∃ s ∈ Pi, b ∈ s ∧ Disjoint s (↑F : Set R) := by
  constructor
  · intro hC t ht b hb F hF
    by_contra hcon
    push_neg at hcon
    have hscore : ScoreAt (insert b (↑F : Set R)) F Pi := by
      intro s hs hne
      by_cases hbs : b ∈ s
      · obtain ⟨x, hxs, hxF⟩ := Set.not_disjoint_iff.mp (hcon s hs hbs)
        exact ⟨x, by simpa using hxF, hxs⟩
      · obtain ⟨x, hxs, hxI⟩ := hne
        rcases hxI with rfl | hxF
        · exact absurd hxs hbs
        · exact ⟨x, by simpa using hxF, hxs⟩
    have hG := hC (insert b (↑F : Set R)) F (fun x hx => Set.mem_insert_of_mem _ hx) hscore
    obtain ⟨y, hyF, hyt⟩ := hG t ht ⟨b, hb, Set.mem_insert _ _⟩
    exact (Set.disjoint_left.mp hF (by simpa using hyF)) hyt
  · intro h I O hOI hPi t ht hne
    by_contra hcon
    push_neg at hcon
    have hdisj : Disjoint (↑O : Set R) t := by
      rw [Set.disjoint_left]
      intro x hx hxt
      exact hcon x (by simpa using hx) hxt
    obtain ⟨b, hbt, hbI⟩ := hne
    obtain ⟨s, hs, hbs, hsO⟩ := h t ht b hbt O hdisj
    obtain ⟨y, hyO, hys⟩ := hPi s hs ⟨b, hbs, hbI⟩
    exact (Set.disjoint_left.mp hsO hys) (by simpa using hyO)

/-- **Definition 9.2 (oracle-relative detection set).** An oracle `ω : R → Ω` records what the suite's
assertions observe; `DetW ω p` is the set of values whose image `ω` distinguishes after applying `p`.
The exact oracle is `ω = id`, recovering `Mov` (Prop 9.3). (Paper §9, Def 9.2.) -/
def DetW {Ω : Type*} (ω : R → Ω) (p : R → R) : Set R := {r | ω (p r) ≠ ω r}

/-- **Proposition 9.3 (the ceiling is oracle-independent for a non-constant oracle).** If `ω` is
non-constant then for every `b` there is an operator with `DetW ω p = {b}`. (Paper §9, Prop 9.3.) -/
theorem detW_singleton_of_nonconstant {Ω : Type*} (ω : R → Ω)
    (hω : ∃ r₁ r₂ : R, ω r₁ ≠ ω r₂) (b : R) :
    ∃ p : R → R, DetW ω p = {b} := by
  classical
  obtain ⟨r₁, r₂, h⟩ := hω
  have hc : ∃ c : R, ω c ≠ ω b := by
    by_contra hcon
    push_neg at hcon
    exact h ((hcon r₁).trans (hcon r₂).symm)
  obtain ⟨c, hcb⟩ := hc
  refine ⟨fun r => if r = b then c else r, ?_⟩
  ext r
  by_cases hr : r = b <;> simp [DetW, hr, hcb]

/-- **Constants under a weak oracle (Remark 9.3b).** The constant operator's detection set is the
complement of the `ω`-class of `c`: `DetW ω (return c) = {r | ω c ≠ ω r}`. (Paper §9, Remark 9.3b.) -/
theorem detW_const {Ω : Type*} (ω : R → Ω) (c : R) :
    DetW ω (fun _ => c) = {r | ω c ≠ ω r} := rfl

/-- **Proposition 9.4, narrow form (ω-non-equivalent pseudo-testedness).** For a covered method (`O ≠ ∅`), the constant
mutant `return c` survives against `T` under `ω` while being non-`ω`-equivalent iff every observed output
is `ω`-indistinguishable from `c` while some reachable output is not:
`O ⊆ ω⁻¹(ω c)` and `I ⊄ ω⁻¹(ω c)`. (Paper §9, Prop 9.4.) -/
theorem pseudo_tested_iff {Ω : Type*} (ω : R → Ω) (c : R) (I : Set R) (O : Finset R) :
    (DetW ω (fun _ => c) ∩ (↑O : Set R) = ∅ ∧ (DetW ω (fun _ => c) ∩ I).Nonempty) ↔
      ((↑O : Set R) ⊆ ω ⁻¹' {ω c} ∧ ¬ I ⊆ ω ⁻¹' {ω c}) := by
  simp only [DetW, Set.eq_empty_iff_forall_notMem, Set.mem_inter_iff, Set.mem_setOf_eq,
    Set.nonempty_def, Set.subset_def, Set.mem_preimage, Set.mem_singleton_iff, not_forall]
  constructor
  · rintro ⟨h1, x, hx, hxI⟩
    refine ⟨fun r hr => ?_, x, hxI, fun h => hx h.symm⟩
    by_contra h
    exact h1 r ⟨fun h' => h h'.symm, hr⟩
  · rintro ⟨h1, x, hxI, hx⟩
    exact ⟨fun r ⟨hne, hr⟩ => hne (h1 r hr).symm, x, fun h => hx h.symm, hxI⟩

/-- **Proposition 9.4 (pseudo-testedness, mixed oracle).** The constant
`return c` is *pseudo-tested* — non-equivalent under the EXACT oracle (`Mov ∩ I ≠ ∅`) yet ω-undetected on the
observed set (`DetW ω ∩ O = ∅`) — iff every observed output is ω-indistinguishable from `c` while some
reachable output genuinely differs. The non-equivalence conjunct uses `Mov`, not `DetW`: the paradigm
pseudo-tested method is ω-*equivalent* (its returned value no assertion inspects), the case the narrow
`pseudo_tested_iff` above excludes. Closed by Wayfinder → Aristotle (`sorries_remaining: 0`; axioms
`[propext, Classical.choice, Quot.sound]`); not hand-authored. (Paper §9, Proposition 9.4.) -/
theorem pseudo_tested_mixed_iff {Ω : Type*} (ω : R → Ω) (c : R) (I : Set R) (O : Finset R) :
    (DetW ω (fun _ => c) ∩ (↑O : Set R) = ∅ ∧ (Mov (fun _ => c) ∩ I).Nonempty) ↔
      ((↑O : Set R) ⊆ ω ⁻¹' {ω c} ∧ ¬ I ⊆ ({c} : Set R)) := by
  rw [Set.eq_empty_iff_forall_notMem, Set.not_subset]
  constructor
  · rintro ⟨h1, r, hr1, hr2⟩
    refine ⟨fun x hx => ?_, r, hr2, fun h => hr1 (Set.mem_singleton_iff.mp h).symm⟩
    by_contra hne
    exact h1 x ⟨fun h => hne (by simpa using h.symm), hx⟩
  · rintro ⟨h1, r, hr, hrc⟩
    refine ⟨?_, r, fun h => hrc (Set.mem_singleton_iff.mpr h.symm), hr⟩
    rintro x ⟨hx1, hx2⟩
    exact hx1 (by simpa using (h1 hx2).symm)

/-! ### Remark 2.5 formal, the absolute corollaries lifted to operators, and the infinite-impossibility. -/

/-- **Remark 2.5 (every subset is a footprint).** For `[Nontrivial R]`, every `S : Set R` equals `Mov p`
for some output operator `p`: a fixed-point-free swap-to-`a` map restricted to `S` (no `|R|`-cycle is
needed, which would fail for uncountable `R`). -/
theorem mov_surjective [Nontrivial R] (S : Set R) : ∃ p : R → R, Mov p = S := by
  classical
  obtain ⟨a, b, hab⟩ := exists_pair_ne R
  refine ⟨fun x => if x ∈ S then (if x = a then b else a) else x, ?_⟩
  ext x
  simp only [Mov, Set.mem_setOf_eq]
  constructor
  · intro hne
    by_contra hxS
    exact hne (if_neg hxS)
  · intro hxS
    rw [if_pos hxS]
    by_cases hxa : x = a
    · rw [if_pos hxa, hxa]; exact hab.symm
    · rw [if_neg hxa]; exact Ne.symm hxa

/-- `Mov` maps the family of *all* operators onto the family of *all* footprints. -/
theorem mov_image_univ [Nontrivial R] : Mov '' (Set.univ : Set (R → R)) = Set.univ := by
  ext S
  simp only [Set.mem_image, Set.mem_univ, true_and, iff_true]
  exact mov_surjective S

/-- **Cor 4.1, over operators.** A finite operator family is absolutely (program-level) complete iff it
contains a value guard — an operator with singleton footprint `{b}` — for every `b`. -/
theorem progComplete_absolute_iff_guards [Nontrivial R] [DecidableEq R] (Pi : Set (R → R)) (hfin : Pi.Finite) :
    ProgComplete Pi Set.univ ↔ ∀ b : R, ∃ p ∈ Pi, Mov p = ({b} : Set R) := by
  rw [progComplete_iff_complete, mov_image_univ, absolute_iff_guards _ (hfin.image Mov)]
  constructor
  · intro h b; exact h b
  · intro h b; exact h b

/-- **The value-guard consequence, over operators.** A finite operator family with a value guard for every
value is sufficient for *any* operator target (Corollary 4.1; not a coupling result, see Proposition 6.1). -/
theorem progComplete_coupling [DecidableEq R] (Pi Gamma : Set (R → R)) (hfin : Pi.Finite)
    (hguards : ∀ b : R, ∃ p ∈ Pi, Mov p = ({b} : Set R)) : ProgComplete Pi Gamma := by
  rw [progComplete_iff_complete]
  exact coupling _ _ (hfin.image Mov) (fun b => hguards b)

/-- **The infinite-impossibility (footprint level).** On an infinite codomain, no finite footprint family
is absolutely complete: absolute completeness demands a distinct singleton footprint per value. -/
theorem complete_univ_infinite [Infinite R] (Pi : Set (Set R)) (hfin : Pi.Finite) :
    ¬ Complete Pi Set.univ := by
  rw [absolute_iff_guards Pi hfin]
  intro h
  have hinj : Function.Injective (fun b : R => ({b} : Set R)) := fun x y hxy => by simpa using hxy
  have hsub : Set.range (fun b : R => ({b} : Set R)) ⊆ Pi := by rintro _ ⟨b, rfl⟩; exact h b
  exact absurd hfin ((Set.infinite_range_of_injective hinj).mono hsub)

/-- **Corollary 4.2 (infinite-impossibility, over operators).** On an infinite codomain, **no finite
output-operator family is absolutely adequacy-complete.** This is the ceiling with teeth: absolute
output-mutation completeness is not merely expensive on large types — for a finite operator family it is
*impossible*; only relative completeness for a chosen target class remains meaningful. -/
theorem progComplete_univ_infinite [Nontrivial R] [Infinite R] [DecidableEq R] (Pi : Set (R → R)) (hfin : Pi.Finite) :
    ¬ ProgComplete Pi Set.univ := by
  rw [progComplete_iff_complete, mov_image_univ]
  exact complete_univ_infinite _ (hfin.image Mov)

/-- **Theorem 8.1, infinite companion.** If the reachable set is infinite, *no finite suite* achieves an
absolute score of 1: certification requires observing every reachable output, impossible for a finite suite. -/
theorem certify_infinite (I : Set R) (hI : I.Infinite) (O : Finset R) :
    ¬ ScoreAt I O (Set.univ) := by
  intro h
  exact hI (O.finite_toSet.subset ((ceiling I O).mp h))

/-! Audit counterexamples: semantic equivalence and finite observation are distinct. -/

/-- A surviving Boolean guard can have an unreachable footprint, with no coverage gap. -/
theorem surviving_guard_without_gap :
    ScoreAt ({false} : Set Bool) {false} {{true}} ∧
      ¬ ∃ b ∈ ({false} : Finset Bool), b ∈ ({true} : Set Bool) := by
  simp [ScoreAt, Set.nonempty_def]

/-- A proper sub-footprint meeting one point does not cover every target point. -/
theorem one_subfootprint_is_insufficient :
    ¬ Complete ({({0} : Set Nat)} : Set (Set Nat)) {({0, 1} : Set Nat)} := by
  rw [footprint_characterization _ _ (Set.finite_singleton _)]
  simp only [Set.mem_singleton_iff, forall_eq, Set.mem_insert_iff]
  intro h
  have bad := h 1 (by simp)
  simp at bad

/-- Full score against an empty-footprint regime is vacuous, even with no observations. -/
theorem empty_footprints_score_without_observations (I : Set R) :
    ScoreAt I ∅ {∅} := by
  simp [ScoreAt, Set.nonempty_def]

/-! ### Program-level suite construction, the mixed-oracle ceiling, constants under a weak oracle,
and the three-valued constant counterexample. -/

/-- **Theorem 8.1, program level, achievability.** If a program has finitely many outputs, a suite of
exactly `|f(D)|` tests (one preimage per reachable output) achieves an absolute score of one. -/
theorem prog_certify_ub {D : Type*} (f : D → R) (hfin : (Set.range f).Finite) :
    ∃ T : Finset D, ProgScore Set.univ f T ∧ T.card = (Set.range f).ncard := by
  have hsurj : Set.SurjOn f Set.univ (Set.range f) := by
    rw [← Set.image_univ]; exact Set.surjOn_image f Set.univ
  obtain ⟨s, -, hbij⟩ := Set.surjOn_iff_exists_bijOn_subset.mp hsurj
  have hsfin : s.Finite := Set.Finite.of_finite_image (hbij.image_eq ▸ hfin) hbij.injOn
  refine ⟨hsfin.toFinset, ?_, ?_⟩
  · intro p _ hne
    obtain ⟨b, hbp, hbI⟩ := hne
    obtain ⟨x, hxs, rfl⟩ := hbij.surjOn hbI
    exact ⟨x, hsfin.mem_toFinset.mpr hxs, hbp⟩
  · rw [← hbij.image_eq, hbij.injOn.ncard_image, Set.ncard_eq_toFinset_card s hsfin]

/-- **Theorem 8.1, program level, lower bound.** Any suite achieving an absolute score of one has at
least `|f(D)|` tests. -/
theorem prog_certify_lb [Nontrivial R] [DecidableEq R] {D : Type*} (f : D → R) (T : Finset D)
    (h : ProgScore Set.univ f T) : (Set.range f).ncard ≤ T.card := by
  rw [progScore_iff_scoreAt, mov_image_univ, ceiling] at h
  calc (Set.range f).ncard ≤ (↑(T.image f) : Set R).ncard := Set.ncard_le_ncard h (Finset.finite_toSet _)
    _ = (T.image f).card := Set.ncard_coe_finset _
    _ ≤ T.card := Finset.card_image_le

/-- **Mixed score** (Proposition 9.4b): a mutant counts as non-equivalent when it changes a reachable
returned value (the exact oracle) and as killed when the suite's oracle `ω` notices on an observed value. -/
def MixedScoreAt {Ω : Type*} (ω : R → Ω) (I : Set R) (O : Finset R) (Pi : Set (R → R)) : Prop :=
  ∀ p ∈ Pi, (Mov p ∩ I).Nonempty → ∃ b ∈ O, ω (p b) ≠ ω b

/-- **Proposition 9.4b (the mixed ceiling).** The absolute mixed score is one iff the suite observes every
reachable output and the oracle separates every reachable value from every other value. -/
theorem mixed_ceiling [Nontrivial R] {Ω : Type*} (ω : R → Ω) (I : Set R) (O : Finset R) :
    MixedScoreAt ω I O Set.univ ↔ I ⊆ (↑O : Set R) ∧ ∀ b ∈ I, ∀ b' : R, ω b' = ω b → b' = b := by
  classical
  constructor
  · intro h
    refine ⟨fun b hb => ?_, fun b hb b' hb' => ?_⟩
    · obtain ⟨c, hc⟩ := exists_ne b
      obtain ⟨x, hxO, hx⟩ := h (fun r => if r = b then c else r) (Set.mem_univ _)
        ⟨b, by simp [Mov, hc], hb⟩
      by_cases hxb : x = b
      · subst hxb; exact Finset.mem_coe.mpr hxO
      · simp [hxb] at hx
    · by_contra hne
      obtain ⟨x, hxO, hx⟩ := h (fun r => if r = b then b' else r) (Set.mem_univ _)
        ⟨b, by simp [Mov, hne], hb⟩
      by_cases hxb : x = b
      · subst hxb; simp only [if_true] at hx; exact hx hb'
      · simp [hxb] at hx
  · rintro ⟨hIO, hsep⟩ p _ ⟨b, hbp, hbI⟩
    exact ⟨b, Finset.mem_coe.mp (hIO hbI), fun h => hbp (hsep b hbI (p b) h)⟩

/-- Under a nonconstant oracle every set of values is some operator's detection set (the oracle-relative
form of Remark 2.5). -/
theorem detW_surjective {Ω : Type*} (ω : R → Ω) (hω : ∃ r₁ r₂ : R, ω r₁ ≠ ω r₂) (S : Set R) :
    ∃ p : R → R, DetW ω p = S := by
  classical
  obtain ⟨r₁, r₂, h⟩ := hω
  have hc : ∀ r : R, ∃ c : R, ω c ≠ ω r := by
    intro r
    by_contra hcon
    push_neg at hcon
    exact h ((hcon r₁).trans (hcon r₂).symm)
  choose c hcr using hc
  refine ⟨fun r => if r ∈ S then c r else r, ?_⟩
  ext r
  by_cases hr : r ∈ S <;> simp [DetW, hr, hcr]

/-- Constants under a nonconstant oracle: every value has a constant whose detection set is exactly that
value iff the return type has two elements. -/
theorem constant_guards_omega_iff_card_two [Fintype R] {Ω : Type*} (ω : R → Ω)
    (hω : ∃ r₁ r₂ : R, ω r₁ ≠ ω r₂) :
    (∀ b : R, ∃ c : R, DetW ω (fun _ => c) = {b}) ↔ Fintype.card R = 2 := by
  classical
  obtain ⟨r₁, r₂, h12⟩ := hω
  have hne12 : r₁ ≠ r₂ := fun h => h12 (h ▸ rfl)
  constructor
  · intro h
    have hall : ∀ x : R, x = r₁ ∨ x = r₂ := by
      intro x
      by_contra hx
      push_neg at hx
      obtain ⟨c, hc⟩ := h x
      have e1 : ω c = ω r₁ := by
        by_contra hne
        have : r₁ ∈ DetW ω (fun _ => c) := hne
        rw [hc] at this; exact hx.1 this.symm
      have e2 : ω c = ω r₂ := by
        by_contra hne
        have : r₂ ∈ DetW ω (fun _ => c) := hne
        rw [hc] at this; exact hx.2 this.symm
      exact h12 (e1.symm.trans e2)
    rw [← Finset.card_univ, Finset.card_eq_two]
    refine ⟨r₁, r₂, hne12, ?_⟩
    ext x
    simp only [Finset.mem_univ, Finset.mem_insert, Finset.mem_singleton, true_iff]
    exact hall x
  · intro hcard b
    obtain ⟨a, a', haa', huniv⟩ := Finset.card_eq_two.mp hcard
    have hall : ∀ x : R, x = a ∨ x = a' := by
      intro x
      have hx : x ∈ ({a, a'} : Finset R) := huniv ▸ Finset.mem_univ x
      simpa [Finset.mem_insert, Finset.mem_singleton] using hx
    have hsep : ω a ≠ ω a' := by
      intro he
      rcases hall r₁ with h1 | h1 <;> rcases hall r₂ with h2 | h2 <;> subst h1 <;> subst h2 <;>
        first | exact h12 rfl | exact h12 he | exact h12 he.symm
    rcases hall b with rfl | rfl
    · refine ⟨a', ?_⟩
      ext r
      rcases hall r with rfl | rfl
      · simp [DetW, hsep.symm]
      · simp [DetW, haa'.symm]
    · refine ⟨a, ?_⟩
      ext r
      rcases hall r with rfl | rfl
      · simp [DetW, haa']
      · simp [DetW, hsep]

/-- **Remark 9.3b (constants under a weak oracle).** For a nonconstant oracle, the constant regime is
absolutely `ω`-sufficient (sufficient, over detection sets, for every operator) iff `|R| = 2`. -/
theorem constants_omega_iff_card_two [Fintype R] {Ω : Type*} (ω : R → Ω)
    (hω : ∃ r₁ r₂ : R, ω r₁ ≠ ω r₂) :
    Complete (DetW ω '' {p : R → R | ∃ c : R, p = fun _ => c}) (DetW ω '' Set.univ) ↔
      Fintype.card R = 2 := by
  have huniv : DetW ω '' (Set.univ : Set (R → R)) = Set.univ := by
    ext S
    simp only [Set.mem_image, Set.mem_univ, true_and, iff_true]
    exact detW_surjective ω hω S
  rw [huniv, absolute_iff_guards _ (Set.toFinite _), ← constant_guards_omega_iff_card_two ω hω]
  constructor
  · intro h b
    obtain ⟨p, ⟨c, rfl⟩, hp⟩ := h b
    exact ⟨c, hp⟩
  · intro h b
    obtain ⟨c, hc⟩ := h b
    exact ⟨fun _ => c, ⟨c, rfl⟩, hc⟩

/-- **Example 4.4, formal.** On three values, a suite observing `{0, 1}` of a program reaching all three
kills every constant mutant, while the guard on `2` (non-equivalent) survives. -/
theorem constants_insufficient_on_three :
    ScoreAt (Set.univ : Set (Fin 3)) {0, 1} ((fun c : Fin 3 => ({c}ᶜ : Set (Fin 3))) '' Set.univ) ∧
      ¬ ScoreAt (Set.univ : Set (Fin 3)) {0, 1} {{2}} := by
  refine ⟨?_, ?_⟩
  · rintro S ⟨c, -, rfl⟩ -
    fin_cases c
    · exact ⟨1, by decide, by simp⟩
    · exact ⟨0, by decide, by simp⟩
    · exact ⟨0, by decide, by simp⟩
  · intro h
    obtain ⟨b, hbO, hb⟩ := h {2} rfl ⟨2, rfl, trivial⟩
    rw [Set.mem_singleton_iff] at hb
    subst hb
    revert hbO; decide

/-- **Proposition 5.1 (the exact reach of a partial guard regime).** The value guards on a finite set `G`
of values are sufficient for exactly the targets whose footprints lie inside `G`. -/
theorem partial_guards_reach (G : Finset R) (Gamma : Set (Set R)) :
    Complete ((fun r => ({r} : Set R)) '' (↑G : Set R)) Gamma ↔ ∀ t ∈ Gamma, t ⊆ (↑G : Set R) := by
  rw [footprint_characterization _ _ ((G.finite_toSet).image _)]
  constructor
  · intro h t ht b hb
    obtain ⟨s, ⟨r, hrG, rfl⟩, hbs, -⟩ := h t ht b hb
    rw [Set.mem_singleton_iff] at hbs
    exact hbs ▸ hrG
  · intro h t ht b hb
    exact ⟨{b}, ⟨b, h t ht hb, rfl⟩, rfl, Set.singleton_subset_iff.mpr hb⟩

/-- **Remark 3.3 (composition is the wrong closure), formal.** On `Fin 3` with reachable and observed set
`{0}`: `a` and `b` each move `0` (both mutants are killed at `0`), yet their composite `b ∘ a` fixes `0`, so
its footprint misses the reachable set and the composite mutant is equivalent. -/
theorem composition_shrinks_footprint :
    ∃ a b : Fin 3 → Fin 3, (0 : Fin 3) ∈ Mov a ∧ (0 : Fin 3) ∈ Mov b ∧ (0 : Fin 3) ∉ Mov (b ∘ a) := by
  refine ⟨![1, 1, 2], ![2, 0, 2], ?_, ?_, ?_⟩ <;> simp only [Mov, Set.mem_setOf_eq] <;> decide
