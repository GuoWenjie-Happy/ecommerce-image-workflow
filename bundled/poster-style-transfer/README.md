# Poster Style Transfer

An open Agent Skill for extracting poster design systems and transferring them to original poster concepts.

## What it does

This skill analyzes a reference poster as a reusable visual system rather than copying its content. It helps you:

- Extract a structured Poster Style Spec
- Identify layout, typography, color, hero, and texture rules
- Separate hard locks, soft locks, and content that must be replaced
- Create original poster concepts in the same visual system
- Build reusable variable-based generation prompts

## Core principle

> Extract poster grammar, not poster content.

The goal is to preserve the reference poster's design logic while replacing its people, characters, logos, wording, products, scenery, and theme-specific symbols.

## Modes

### Direct generation

Use a reference poster and a new theme to create an original poster guided by the extracted design system.

### Style Spec only

Analyze and document a poster's reusable production constraints without generating a new image.

### Variable template

Create a reusable prompt template with editable variables for theme, titles, hero subject, props, palette, date, location, and aspect ratio.

## Installation

### Codex

Clone the complete skill directory:

```bash
git clone https://github.com/jiemianduan/poster-style-transfer.git \
  ~/.codex/skills/poster-style-transfer
```

Then invoke:

```text
$poster-style-transfer
```

### Cursor

1. Clone the repository into an accessible project folder:

```bash
git clone https://github.com/jiemianduan/poster-style-transfer.git \
  .agents/skills/poster-style-transfer
```

2. Copy the Cursor adapter:

```bash
mkdir -p .cursor/commands
cp .agents/skills/poster-style-transfer/adapters/cursor/poster-style-transfer.md \
  .cursor/commands/poster-style-transfer.md
```

3. Use `/poster-style-transfer` in Cursor Chat.

### Gemini CLI

1. Clone the repository into an accessible project folder:

```bash
git clone https://github.com/jiemianduan/poster-style-transfer.git \
  .agents/skills/poster-style-transfer
```

2. Copy the Gemini CLI adapter:

```bash
mkdir -p .gemini/commands
cp .agents/skills/poster-style-transfer/adapters/gemini-cli/poster-style-transfer.toml \
  .gemini/commands/poster-style-transfer.toml
```

3. Use:

```text
/poster-style-transfer <your poster brief>
```

### Other Agent Skills-compatible runtimes

Use the complete `poster-style-transfer` directory, including `SKILL.md` and `references/`, following your agent's own skill installation convention.

## Repository structure

```text
.
├── SKILL.md                         # Main workflow and operating rules
├── adapters/
│   ├── cursor/
│   │   └── poster-style-transfer.md # Cursor command adapter
│   └── gemini-cli/
│       └── poster-style-transfer.toml # Gemini CLI command adapter
├── agents/
│   └── openai.yaml                  # Codex skill metadata
└── references/
    ├── poster-archetypes.md         # Poster classification guide
    ├── poster-style-spec.md         # Reusable style-spec schema
    └── fidelity-rubric.md           # Quality and fidelity evaluation rubric
```

## Responsible use

- Use reference posters as design-system references, not as content to reproduce.
- Replace reference people, logos, wording, products, characters, and proprietary symbols.
- Do not create pixel-for-pixel reconstructions or trace unique illustrations.
- Confirm that you have the right to use any reference image you provide.
- Do not present invented event details, endorsements, or official information as factual.

## Contributing

Issues and pull requests are welcome. For substantial changes, please open an issue first to discuss the proposed direction.

## License

This project is licensed under the MIT License.
