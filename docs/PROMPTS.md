# Prompting

Der Hook liest standardmaessig:

```text
/opt/paperless/ai_enrich_prompt.txt
```

Alternativ kann ein anderer Pfad gesetzt werden:

```dotenv
PAPERLESS_AI_PROMPT_FILE=/pfad/zur/promptdatei.txt
```

## Platzhalter

Die Prompt-Datei kann folgende Platzhalter verwenden:

- `{title}`
- `{original}`
- `{correspondent}`
- `{doc_type}`
- `{tags}`
- `{content}`

## Wichtiger Punkt

Wenn im Prompt JSON-Beispiele enthalten sind, muessen geschweifte Klammern fuer `str.format(...)` escaped werden:

```text
{{
  "title": "..."
}}
```

## Praxis

Sinnvolle Anpassungen:

- Personennamen als Tags staerker unterbinden
- juristische Dokumenttypen klarer priorisieren
- Tags auf feste interne Taxonomie begrenzen
- medizinische oder behoerdliche Dokumente separat gewichten
