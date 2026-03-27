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
- `{existing_person_tags}`
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

## Aktuelle Praxisregeln

Im produktiven Stand haben sich diese Regeln bewaehrt:

- Korrespondenz bevorzugt als Aussteller oder Absender bestimmen, nicht als Empfaenger
- keine Jahreszahlen, Adressen oder Orte als generische Tags
- Personennamen nur wiederverwenden, wenn:
  - der Name bereits als Tag existiert
  - der Name exakt so im OCR-Inhalt vorkommt
- Rechnungen als Titel moeglichst knapp und sachlich halten
- juristische Dokumente mit klaren Typbegriffen wie `Beschluss`, `Gerichtsbeschluss`, `Bescheid`

## Wichtiger Modellhinweis

- die Prompt-Datei allein reicht fuer `Qwen 3.5` nicht
- der Hook setzt fuer `qwen3.5:*` zusaetzlich `think=false`, damit JSON-Extraktion nicht in langen Thinking-Ausgaben stecken bleibt
