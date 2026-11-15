# Poster Style Transfer

Use this command to analyze a reference poster and create an original poster concept in its visual system.

First, locate and read the canonical `SKILL.md` for the `poster-style-transfer` skill. Treat it as the source of truth. Use its linked reference files when needed.

Follow these rules:

1. Extract poster grammar, not poster content.
2. Choose the appropriate mode:
   - Direct generation
   - Style Spec only
   - Variable template
3. Identify the reference poster's layout, typography, hero mechanism, color relationships, graphic language, and finish.
4. Separate:
   - Hard lock: high-impact design rules to preserve
   - Soft lock: adaptable visual details
   - Must replace: people, logos, wording, products, characters, scenery, and proprietary symbols
5. Build a new, original content system for the user's theme.
6. Never reproduce reference logos, exact wording, recognizable people, proprietary characters, or unique illustrations.
7. For direct generation, validate composition, text accuracy, originality, and visual-system fidelity before returning the result.
8. If the user has not provided a usable poster reference, ask for one.

Return the result in the format required by the selected mode in `SKILL.md`.
