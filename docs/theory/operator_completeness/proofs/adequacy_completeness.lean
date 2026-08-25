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

/-- **Theorem 4.4 (the ceiling).** A full score against *all* footprints holds iff the suite observes
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

/-- **Theorem 6.1 (completeness ⇒ coupling).** A family containing every value guard is complete for
*any* target — in particular for higher-order mutants. The coupling effect as a corollary. -/
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

/-- **Corollary 4.2 (extreme mutation is complete iff `n = 2`).** The Descartes constant family
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
theorem certify_lb (I : Set R) (O : Finset R) (hIfin : I.Finite)
    (h : ScoreAt I O (Set.univ)) : I.ncard ≤ O.card := by
  have hsub : I ⊆ (↑O : Set R) := (ceiling I O).mp h
  have h2 : I.ncard ≤ (↑O : Set R).ncard := Set.ncard_le_ncard hsub O.finite_toSet
  simpa using h2

/-- **Theorem 8.1 (minimum certifying suite), achievability.** A suite of exactly `|I|` values certifies
full output coverage: `σ(f) = |f(D)|`. -/
theorem certify_ub (I : Set R) (hIfin : I.Finite) :
    ∃ O : Finset R, ScoreAt I O (Set.univ) ∧ O.card = I.ncard := by
  refine ⟨hIfin.toFinset, ?_, ?_⟩
  · rw [ceiling, hIfin.coe_toFinset]
  · haveI : Fintype ↥I := hIfin.fintype
    rw [Set.ncard_eq_toFinset_card' I]
    congr 1
    apply Finset.coe_injective
    rw [hIfin.coe_toFinset, Set.coe_toFinset]

/-! ### The program ↔ footprint bridge (§11.1): completeness stated over real programs and suites. -/

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
