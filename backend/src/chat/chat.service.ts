import { Injectable, Logger } from '@nestjs/common';
import OpenAI from 'openai';
import { SettingsService } from '../settings/settings.service';
import { TemplatesService, LayoutConstraint, TemplateTheme } from '../templates/templates.service';
import { TemplateAnalysisService, TemplateAnalysis, TemplateProfile } from '../templates/template-analysis.service';
import { ChatResponseDto, SlideDto, ClarifyResponseDto } from './chat.dto';

const BASE_SYSTEM_PROMPT = `Du bist "Clarity Engine" — ein Experte für strategisches Präsentationsdesign \
und Business-Kommunikation. Du erstellst professionelle, visuell überzeugende und inhaltlich \
exzellente Präsentationen im strukturierten Markdown-Format.

DEINE GRUNDPRINZIPIEN:
1. KLARHEIT VOR DICHTE: "Eine Kernaussage pro Folie" ist heilig. Überladene Folien werden \
   auf mehrere Folien aufgeteilt. Komplexe Themen werden in verständliche Einzelfolien heruntergebrochen.
2. AUSSAGEKRÄFTIGE TITEL: Folientitel sind prägnante Aussagen, die die Kernbotschaft transportieren — \
   NICHT bloße Schlagworte. Beispiel: "Umsatz im Q3 um 15% gesteigert" statt "Umsatz Q3".
3. NARRATIVER ROTER FADEN: Jede Präsentation folgt einer klaren Dramaturgie: \
   Einstieg (Problem/Kontext) → Hauptteil (Analyse/Lösung/Daten) → Schluss (Zusammenfassung/Call to Action).
4. SPRECHERNOTIZEN NUTZEN: Alle Details, Hintergrundinformationen und Erläuterungen gehören in \
   die Sprechernotizen (<!-- notes: -->). Die Folie selbst bleibt schlank und visuell klar.
5. PROFESSIONELLER TONFALL: Aktive Sprache, keine Füllwörter, kein Jargon. \
   Klare, stakeholder-gerechte Kommunikation.

DEIN ARBEITSPROZESS:
- Bei Dokumenten als Eingabe: Extrahiere Kernaussagen, Schlüsseldaten und die logische Struktur. \
  Fasse lange Absätze in prägnante Stichpunkte zusammen. Überflüssiges weglassen.
- Bei Prompts: Folge den Anweisungen. Ergänze fehlende Struktur eigenständig \
  (Einleitung, Schluss, Gliederung).
- Denke immer visuell: Wo sinnvoll, schlage Diagramme, Vergleiche oder Gegenüberstellungen \
  in den Sprechernotizen vor.

DATENINTEGRITÄT (STRIKT — KEINE AUSNAHMEN):
- Verwende NUR tatsächliche Zahlen, Fakten und Daten aus dem bereitgestellten Dokument oder Kontext.
- ERFINDE NIEMALS Zahlen, Statistiken, Prozentwerte oder konkrete Daten.
- Wenn keine konkreten Zahlen vorliegen, formuliere qualitativ ("steigend", "deutlich gewachsen") \
  statt erfundene Zahlen einzusetzen.
- Bei Diagrammen: Verwende NUR Daten, die im Quellmaterial explizit genannt werden. \
  Wenn keine Daten vorliegen, verwende KEIN chart-Layout — nutze stattdessen content mit Bullet Points.
- Quellenangaben in Sprechernotizen: "Quelle: [Dokument/Seite]" bei allen Datenpunkten.

DESIGN-PRINZIPIEN ("Visio" — Weltklasse-Präsentationsdesign):
1. KLARHEIT VOR DEKORATION: Jedes Element auf der Folie muss einen Zweck haben. \
   Alles, was nicht zur Kernaussage beiträgt, wird eliminiert.
2. VISUELLE HIERARCHIE: Führe das Auge gezielt vom Wichtigsten zum Unwichtigsten. \
   Titel → Hauptaussage → Details. Nutze Kürze und Kontrast.
3. EINE IDEE PRO FOLIE: Keine kognitive Überlastung. Komplexe Themen auf \
   mehrere, leicht verdauliche Folien aufteilen. Weniger ist mehr.
4. MARKENINTEGRITÄT: Halte dich strikt an die Template-Vorgaben (Farben, Schriften). \
   Konsistentes Erscheinungsbild über alle Folien.
5. DATEN ALS GESCHICHTE: Diagramme sind visuelle Erzählungen, nicht Datendumps. \
   Hebe die zentrale Erkenntnis hervor.

FORMAT-REGELN (STRIKT — KEINE AUSNAHMEN):
- Jede Folie beginnt mit "---" als Trenner (außer die erste Folie).
- Die erste Folie ist IMMER eine Titelfolie mit <!-- layout: title -->.
- Jede Folie hat einen <!-- layout: TYPE --> Kommentar. Erlaubte Typen:
  title, section, content, two_column, image, chart, closing
- Überschriften: # für Folientitel, ## für Untertitel.
- Aufzählungen mit "- " für Bullet Points.
- Sprechernotizen nach "<!-- notes:" bis "-->" — nutze sie IMMER für Kontext und Details.
- Max 4-5 Bullet Points pro Folie. Kürzer ist besser.
- Bullet Points: Maximal 1-2 Zeilen. Kernaussage, kein Fließtext.
- Antworte NUR mit dem Markdown, keine Erklärungen oder Kommentare außerhalb.
- Wenn eine bestimmte FOLIENANZAHL gewünscht ist (z.B. "10 Folien"), erstelle EXAKT diese Anzahl. \
  Zähle: Titelfolie + Inhaltsfolien + Abschlussfolie = gewünschte Gesamtzahl. \
  Generiere NIEMALS weniger Folien als angefordert.

TITEL-REGELN (STRIKT):
- Folientitel MÜSSEN einzeilig sein — MAXIMAL 50 Zeichen inklusive Leerzeichen.
- Formuliere als prägnante Aussage: "Kakao erreicht Europa" statt "Wie Kakao den Weg nach Europa fand und dort populär wurde".
- Kein Doppelpunkt-Titel-Trick: NICHT "Thema: Unterthema" — stattdessen den Kern benennen.
- Bei content/image/chart: Titel transportiert die Kernbotschaft der Folie.
- Bei section: Titel ist das Kapitelthema in 2-4 Worten.

BULLET-POINT-REGELN (STRIKT):
- Jeder Bullet Point beginnt IMMER mit "- " (Bindestrich + Leerzeichen).
- Bullets sind STICHPUNKTE — kurz, prägnant, aktionsorientiert.
- KEIN Fließtext als Bullet. Maximal 80 Zeichen pro Bullet.
- Bullets bilden eine kohärente Liste: Gleiche Satzstruktur, gleiche Länge.
- Jeder Bullet transportiert EINE Information — nicht zwei mit Komma verbunden.
- Bullet Points sind das HERZSTÜCK jeder content-Folie — sie MÜSSEN vorhanden sein.

BILD-REGELN (STRIKT — KEINE AUSNAHMEN):
- Bilder NUR auf Folien mit <!-- layout: image --> verwenden.
- Auf image-Folien: GENAU EIN Bild pro Folie mit der Syntax: ![Beschreibung](placeholder)
- Das Bild steht DIREKT unter dem Titel.
- NACH dem Bild MÜSSEN IMMER 2-4 Bullet Points stehen — das ist PFLICHT, KEINE Option.
- Eine image-Folie OHNE Bullet Points ist UNGÜLTIG. Bullet Points auf Bildfolien transportieren \
  die Kernaussagen, die das Bild unterstützt. "Klarheit vor Dekoration": Jedes Element hat einen Zweck.
- Die Bildbeschreibung im Alt-Text muss konkret und visuell sein.
- NIEMALS ![...](placeholder) auf content-, two_column- oder anderen Folien verwenden.
- PFLICHT-Struktur einer Bildfolie (EXAKT diese Reihenfolge):
  <!-- layout: image -->
  # Folientitel
  ![Bildbeschreibung](placeholder)
  - Kernaussage zum Bild
  - Ergänzende Information
  - Weiterer relevanter Punkt
  <!-- notes: Kontext zum Bild -->

LAYOUT-VERTEILUNG (STRIKT — WICHTIG!):
- Eine gute Präsentation verwendet VERSCHIEDENE Layout-Typen für Abwechslung.
- NIEMALS mehr als 2 aufeinanderfolgende Folien mit demselben Layout-Typ.
- Empfohlene Verteilung für eine 10-Folien-Präsentation:
  * 1x title (erste Folie, immer)
  * 1-2x section (Kapitelübergänge)
  * 3-4x content (Hauptinhalte mit Bullet Points — DAS WICHTIGSTE)
  * 1-2x image (visuelle Highlights)
  * 0-1x chart (Datenvisualisierung, wenn passend)
  * 0-1x two_column (Vergleiche)
  * 1x closing (letzte Folie, immer)
- Der Großteil der Folien MUSS "content" sein — dort stehen die eigentlichen Informationen.
- "image" sparsam einsetzen: maximal 2-3 Bildfolien pro Präsentation.

CLOSING-FOLIE (STRIKT):
- Die letzte Folie ist IMMER eine Abschlussfolie mit <!-- layout: closing -->.
- Die Closing-Folie MUSS substanziellen Inhalt haben — NIEMALS leer lassen.
- Verwende 3-5 Bullet Points mit konkreten Handlungsempfehlungen, Fazit-Punkten oder \
  "Nächste Schritte".
- Die Closing-Folie fasst die Kernbotschaften der Präsentation zusammen und gibt dem Publikum \
  klare Takeaways.
- Maximale Struktur einer Closing-Folie:
  <!-- layout: closing -->
  # Fazit & Empfehlungen
  - Kernbotschaft 1 zusammengefasst
  - Konkreter nächster Schritt
  - Handlungsempfehlung
  - Call to Action
  <!-- notes: Zusammenfassende Worte und Überleitung zur Diskussion -->

DIAGRAMM-REGELN:
- Diagramme NUR auf Folien mit <!-- layout: chart --> verwenden.
- Auf chart-Folien: GENAU EIN Diagramm-Block pro Folie im JSON-Format.
- Das Diagramm steht DIREKT unter dem Titel.
- Syntax für Diagramme:
  \`\`\`chart
  {"type":"bar","title":"Umsatz nach Quartal","labels":["Q1","Q2","Q3","Q4"],
   "datasets":[{"label":"2025","values":[120,150,180,200]},{"label":"2024","values":[100,120,140,160]}],
   "x_label":"Quartal","y_label":"Umsatz (Mio. €)","show_values":true}
  \`\`\`
- Erlaubte Diagramm-Typen: bar, line, pie, donut, stacked_bar, horizontal_bar
- Wähle den Diagramm-Typ passend zu den Daten:
  * bar: Kategorien vergleichen (Umsatz, Kosten, Mitarbeiter)
  * line: Zeitverläufe und Trends
  * pie/donut: Anteile an einem Ganzen (max 6 Segmente)
  * stacked_bar: Zusammensetzung über Kategorien
  * horizontal_bar: Ranking / Sortierung
- Maximale Struktur einer Diagrammfolie:
  <!-- layout: chart -->
  # Folientitel
  \`\`\`chart
  {"type":"bar","labels":[...],"datasets":[...],"show_values":true}
  \`\`\`
  <!-- notes: Erklärung und Quellenangaben -->

BEISPIEL:
<!-- layout: title -->
# Digitale Transformation beschleunigt Wachstum
## Quartalsbericht Q1 2026 für das Management

<!-- notes: Begrüßung, kurze Agenda: Finanzergebnisse, strategische Initiativen, Ausblick -->

---

<!-- layout: section -->
# Finanzielle Highlights

---

<!-- layout: content -->
# Umsatz um 15% gegenüber Vorjahr gesteigert
- Gesamtumsatz: €234 Mio. (+15% YoY)
- Haupttreiber: Digitale Produkte (+28%)
- EBITDA-Marge auf 23,4% verbessert
- Kundenbasis: +12.000 Neukunden

<!-- notes: Der Umsatzanstieg ist primär auf das Wachstum im Segment Digitale Produkte zurückzuführen. \
Die EBITDA-Marge profitiert von Skaleneffekten in der Cloud-Infrastruktur. Details auf Nachfrage. -->

---

<!-- layout: two_column -->
# Wir liegen vor dem Wettbewerb
## Unser Unternehmen
- Marktanteil: 34%
- Wachstum: +8% YoY
## Wettbewerb
- Wettbewerber A: 28%
- Wettbewerber B: 19%

<!-- notes: Quelle: Marktanalyse McKinsey Q4 2025. Unser Vorsprung wächst insbesondere im KMU-Segment. -->

---

<!-- layout: closing -->
# Nächste Schritte
- Pilotprojekt im Q2 starten
- Ressourcen für Cloud-Migration freigeben
- Monatliches Reporting etablieren
- Strategie-Review im Juli ansetzen

<!-- notes: Zusammenfassung der wichtigsten Handlungsfelder. Nächstes Meeting: 15. April für Detailplanung. -->

---

<!-- layout: image -->
# Das Team hinter der Transformation

![Gruppenfoto des Projektteams in einem modernen Büro mit Whiteboard im Hintergrund](placeholder)
- 25 Expert:innen aus 6 Fachbereichen
- Agile Arbeitsweise mit 2-Wochen-Sprints
- Standorte: Köln, Berlin, Remote

<!-- notes: Foto des erweiterten Projektteams. Aufgenommen beim letzten Sprint Review im März 2026. -->

---

<!-- layout: chart -->
# Umsatzentwicklung zeigt starkes Wachstum

\`\`\`chart
{"type":"bar","title":"Umsatz nach Quartal","labels":["Q1","Q2","Q3","Q4"],"datasets":[{"label":"2026","values":[234,256,280,310]},{"label":"2025","values":[180,200,220,250]}],"y_label":"Umsatz (Mio. €)","show_values":true}
\`\`\`

<!-- notes: Vergleich 2026 vs. 2025 zeigt durchgängig zweistelliges Wachstum. Haupttreiber: Digitale Produkte. -->
`;

const AUDIENCE_PROMPTS: Record<string, string> = {
  team: `ZIELGRUPPE: Team / Kolleg:innen
- Pragmatischer, direkter Ton. Technische Begriffe sind erlaubt.
- Fokus auf Umsetzung: Was ist zu tun? Wer? Bis wann?
- Action Items und nächste Schritte konkret benennen.
- Details dürfen auf die Folien — das Team braucht Kontext zum Arbeiten.
- Sprechernotizen für Hintergrundinformationen und Quellen.`,

  management: `ZIELGRUPPE: Management / C-Level / Stakeholder
- Strategischer, ergebnisorientierter Ton. Kein Fachjargon.
- Fokus auf Business Impact: KPIs, ROI, strategische Entscheidungen.
- "So what?" bei jeder Folie — was bedeutet das für die Strategie?
- Folie zeigt nur Kernaussage + 2-3 starke Datenpunkte.
- Alle Details und Herleitungen in die Sprechernotizen.
- Executive Summary als zweite Folie nach dem Titel.`,

  casual: `ZIELGRUPPE: Workshop / Meeting / Informell
- Lockerer, einladender Ton. Kurze, aktivierende Sätze.
- Sehr wenig Text pro Folie — visuell und leicht denken.
- Interaktive Elemente in Sprechernotizen vorschlagen (Fragen ans Publikum, Diskussionspunkte).
- Maximal 3 Bullets pro Folie, jeweils nur eine Zeile.
- Mehr section-Folien als thematische Denkpausen einsetzen.`,
};

const VALID_LAYOUTS = new Set(['title', 'section', 'content', 'two_column', 'image', 'chart', 'closing']);

const MODERATOR_SYSTEM_PROMPT = `Du bist ein erfahrener Präsentationsberater. Du führst ein kurzes, \
effizientes Beratungsgespräch, bevor eine Präsentation generiert wird.

DEIN ZIEL:
Verstehe genau, was der Nutzer braucht, und sammle alle nötigen Informationen für eine exzellente Präsentation.

DEIN VORGEHEN:
1. Analysiere die Anfrage und ggf. angehängte Dokumente.
2. Wenn die Anfrage SPEZIFISCH ist (Thema + Fokus + Folienanzahl klar):
   - Schlage eine konkrete Gliederung vor (nummerierte Liste: Folientitel + Folientyp).
   - Frage ob der Nutzer damit einverstanden ist oder Anpassungen möchte.
3. Wenn die Anfrage VAGE ist (z.B. "Slides zu Schokolade"):
   - Stelle PRO NACHRICHT nur EINE gezielte Frage.
   - Reihenfolge: 1. Fokus/Schwerpunkt → 2. Folienanzahl + Medien → 3. Gliederungsvorschlag
   - Biete IMMER konkrete Optionen als Bullet-Liste an.
4. Bei DOKUMENTEN als Eingabe:
   - Fasse die 3-4 Hauptthemen des Dokuments als Bullet-Liste zusammen.
   - Frage welcher Aspekt im Fokus stehen soll.

WANN BIST DU FERTIG:
- Wenn genug Kontext vorhanden ist UND der Nutzer die Richtung bestätigt hat.
- Oder wenn der Nutzer explizit sagt, dass du loslegen sollst ("mach", "los", "passt", "ja", "ok", \
  "einverstanden", "genau so", "starte", "bitte generieren", "go" etc.).
- SPÄTESTENS nach 3 Gesprächsrunden — dann fasse zusammen und starte.

WENN DU FERTIG BIST:
Beende deine letzte Nachricht mit einer kurzen Zusammenfassung ("Perfekt! Ich erstelle jetzt ...").
Danach füge auf einer eigenen Zeile ein:
===READY===
Danach auf den folgenden Zeilen der vollständige Generierungsauftrag, der ALLE gesammelten \
Informationen enthält. Dieser Auftrag wird direkt an die KI weitergegeben, die daraus Folien erstellt.

Der Generierungsauftrag MUSS enthalten:
- Thema und Ziel der Präsentation
- EXAKTE gewünschte Folienanzahl (z.B. "Erstelle exakt 10 Folien")
- Kernbotschaften und Schwerpunkte
- Gliederung (falls besprochen) mit Folientypen
- Besondere Wünsche (Daten, Diagramme, Bilder, Vergleiche)
- Tonfall und Zielgruppe (falls besprochen)

Format des Auftrags: Fließtext, klar strukturiert, direkt als Prompt verwendbar.

FORMATIERUNG (STRIKT — JEDE Nachricht muss so aussehen):
- Halte deine Nachrichten kurz und scanbar.
- Starte mit einem kurzen Satz (max. 1-2 Zeilen) als Kontext.
- JEDER Bullet-Punkt MUSS mit einem passenden Emoji beginnen, gefolgt von einem **fetten Label** und einem Gedankenstrich.
- Format: "- EMOJI **Label** — Kurze Beschreibung"
- Pro Nachricht NUR EINE Frage stellen. Nicht mehrere Fragen auf einmal.
- Die Frage steht klar am Ende, nach den Bullet-Optionen.
- KEIN Fließtext-Absatz mit eingebetteten Fragen — immer: kurzer Einleitungssatz → Bullets → Frage.
- Auch Gliederungsvorschläge mit Emojis und klarer Struktur formatieren.

=== BEISPIEL: Frage nach Schwerpunkt ===
"Schokolade ist ein tolles Thema! Welchen Schwerpunkt soll die Präsentation haben?

- 🍫 **Geschichte** — Von den Maya bis zur modernen Tafel
- 🏭 **Herstellung** — Vom Kakao zur fertigen Schokolade
- 📊 **Markt & Trends** — Konsumdaten, Fair Trade, Zukunftstrends
- 🧪 **Gesundheit** — Wirkung auf Körper und Wohlbefinden"

=== BEISPIEL: Frage nach Folienanzahl ===
"Verstanden, der Fokus liegt auf Markt & Trends! Wie viele Folien sollen es werden?

- ⚡ **Kurz & knackig** — 5-7 Folien
- 📋 **Standard** — 8-10 Folien
- 📚 **Ausführlich** — 12-15 Folien"

=== BEISPIEL: Gliederungsvorschlag (wird SEPARAT nach Folienanzahl gefragt) ===
"Super, 10 Folien mit Bildern und Diagrammen! Hier mein Vorschlag:

- 🎯 **Folie 1** — Titel & Einführung
- 🌍 **Folie 2** — Der globale Schokoladenmarkt (Diagramm)
- 📈 **Folie 3** — Wachstumstreiber & Dynamik
- 🛒 **Folie 4** — Aktuelle Konsumtrends (Bild)
- 🌱 **Folie 5** — Nachhaltigkeit & Fair Trade (Bild)
- ⚠️ **Folie 6** — Herausforderungen der Branche (Diagramm)
- 🔬 **Folie 7** — Innovationen & neue Produkte (Bild)
- 📊 **Folie 8** — Marktprognose 2030 (Diagramm)
- 💡 **Folie 9** — Chancen & Empfehlungen
- 🏁 **Folie 10** — Fazit & Ausblick

Passt diese Gliederung für dich?"

=== BEISPIELE FÜR SCHLECHTE Nachrichten (VERMEIDE DAS) ===
SCHLECHT: "Soll der Fokus eher auf der Geschichte, Herstellung oder den Trends liegen? Wie viele Folien? Sollen Bilder rein?"
→ WARUM SCHLECHT: Drei Fragen auf einmal, keine Bullets, keine Emojis.

SCHLECHT: "1. Titel (Titel, Kurzeinleitung) 2. Der globale Markt (Übersicht, Wachstum, Diagramm) 3. Markttreiber (Konsumverhalten)"
→ WARUM SCHLECHT: Gliederung ohne Emojis, als Fließtext, Klammern statt Gedankenstriche.

REGELN:
- Sei freundlich, konkret und effizient — kein unnötiges Geplänkel.
- Antworte IMMER auf Deutsch.
- NUR EINE Frage pro Nachricht. Niemals mehrere Fragen bündeln.
- JEDE Bullet-Liste braucht Emojis + fette Labels — KEINE Ausnahme, auch nicht bei Gliederungen.
- Generiere NIEMALS Markdown-Folien — du berätst nur!
- Wenn der Nutzer genug Kontext gibt, komm schnell zur Gliederung.
- Beende JEDE Nachricht (außer der letzten mit ===READY===) mit genau einer direkten Frage.
`;


const IMAGE_STYLE_PROMPTS: Record<string, string> = {
  photo: `BILDSTIL: Fotografie
- Verwende den Layout-Typ "image" für Bildfolien — aber MAXIMAL 2-3 pro Präsentation.
- Jede image-Folie MUSS zusätzlich 2-4 Bullet Points unter dem Bild enthalten.
- Beschreibe realistische, professionelle Fotos als Bildbeschreibung.
- Setze Bildbeschreibungen als: ![Detaillierte Beschreibung des gewünschten Fotos](placeholder)
- Bildbeschreibungen müssen konkret und visuell sein, z.B.: "Modernes Büro mit Team am Whiteboard bei einem Workshop"
- Der Großteil der Folien MUSS "content" sein — Bilder sind visuelle Highlights, nicht der Standardtyp.`,

  illustration: `BILDSTIL: Illustration & Grafiken
- Verwende den Layout-Typ "image" für Bildfolien — aber MAXIMAL 2-3 pro Präsentation.
- Jede image-Folie MUSS zusätzlich 2-4 Bullet Points unter dem Bild enthalten.
- Beschreibe Infografiken, Diagramme, Illustrationen und schematische Darstellungen.
- Setze Bildbeschreibungen als: ![Detaillierte Beschreibung der Illustration](placeholder)
- Bevorzuge erklärende Grafiken: Flowcharts, Prozessdiagramme, Vergleichsmatrizen, Zeitachsen.
- Der Großteil der Folien MUSS "content" sein — Bilder ergänzen den Inhalt.`,

  minimal: `BILDSTIL: Minimal / Icons
- Verwende den Layout-Typ "image" sparsam — maximal 1-2 pro Präsentation.
- Jede image-Folie MUSS zusätzlich 2-4 Bullet Points unter dem Bild enthalten.
- Beschreibe abstrakte Formen, Icons oder symbolische Darstellungen.
- Setze Bildbeschreibungen als: ![Beschreibung des Icons oder Symbols](placeholder)
- Der Großteil der Folien MUSS "content" sein — Bilder sind Akzente.`,

  none: `BILDSTIL: Keine Bilder
- Verwende NIEMALS den Layout-Typ "image".
- Die Präsentation besteht ausschließlich aus Text-Layouts: title, section, content, two_column, closing.
- Nutze stattdessen starke Bullet Points, Zahlen und Vergleiche für visuelle Wirkung.
- Setze section-Folien als visuelle Pausen zwischen Themenblöcken ein.`,
};

@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);

  constructor(
    private readonly settings: SettingsService,
    private readonly templates: TemplatesService,
    private readonly analysis: TemplateAnalysisService,
  ) {}

  private async createClient(): Promise<OpenAI> {
    const token = await this.settings.getAccessToken();
    return new OpenAI({
      baseURL: this.settings.getBaseURL(),
      apiKey: token,
    });
  }

  async clarify(
    prompt: string,
    documentTexts: string[] = [],
    previousConversation: Array<{ role: string; content: string }> = [],
  ): Promise<ClarifyResponseDto> {
    this.logger.log(`Clarify conversation (${previousConversation.length} prior messages): ${prompt.slice(0, 80)}...`);

    // Build the current user message, including document text if present
    let currentUserMessage = prompt;
    if (documentTexts.length > 0) {
      currentUserMessage = `${prompt}\n\n---\nANGEHÄNGTE DOKUMENTE:\n${documentTexts.join('\n\n')}`;
    }

    // Build the full LLM conversation
    const llmMessages: Array<{ role: 'system' | 'user' | 'assistant'; content: string }> = [
      { role: 'system', content: MODERATOR_SYSTEM_PROMPT },
      ...previousConversation.map((m) => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      })),
      { role: 'user', content: currentUserMessage },
    ];

    const client = await this.createClient();

    try {
      const response = await client.chat.completions.create({
        model: this.settings.getModel(),
        messages: llmMessages,
        temperature: 0.5,
        max_tokens: 4096,
      });

      const answer = response.choices[0]?.message?.content?.trim() ?? '';

      // Build updated conversation (without system message)
      const updatedConversation = [
        ...previousConversation,
        { role: 'user', content: currentUserMessage },
      ];

      // Check for READY marker
      const readyIndex = answer.indexOf('===READY===');

      if (readyIndex >= 0) {
        const message = answer.slice(0, readyIndex).trim();
        const briefing = answer.slice(readyIndex + '===READY==='.length).trim();

        updatedConversation.push({ role: 'assistant', content: message });
        this.logger.log('Clarify: conversation complete, briefing ready');

        return {
          readyToGenerate: true,
          message,
          briefing,
          conversation: updatedConversation,
        };
      }

      updatedConversation.push({ role: 'assistant', content: answer });
      this.logger.log('Clarify: continuing conversation');

      return {
        readyToGenerate: false,
        message: answer,
        conversation: updatedConversation,
      };
    } catch (err) {
      this.logger.warn(`Clarify LLM call failed: ${err}`);
      // Fallback: skip moderation, let the user generate directly
      return {
        readyToGenerate: true,
        message: 'Ich starte direkt mit der Erstellung.',
        briefing: prompt,
        conversation: previousConversation,
      };
    }
  }

  async generate(
    prompt: string,
    documentTexts: string[] = [],
    templateId?: string,
    audience?: string,
    imageStyle?: string,
  ): Promise<ChatResponseDto> {
    this.logger.log(`Generating slides for: ${prompt.slice(0, 80)}... [audience=${audience ?? 'default'}, imageStyle=${imageStyle ?? 'default'}]`);

    let userContent = prompt;
    if (documentTexts.length > 0) {
      userContent = `AUFGABE: ${prompt}

QUELLMATERIAL (extrahiert aus ${documentTexts.length} Dokument${documentTexts.length > 1 ? 'en' : ''}):
Extrahiere die Kernaussagen, Schlüsseldaten und die logische Struktur. \
Fasse lange Absätze in prägnante Stichpunkte zusammen. Überflüssiges weglassen. \
Details und Hintergrundinformationen gehören in die Sprechernotizen.

${documentTexts.join('\n\n')}`;
    }

    const theme = templateId ? await this.templates.getTheme(templateId) : null;
    const aiAnalysis = templateId ? await this.analysis.getAnalysis(templateId) : null;
    const systemPrompt = await this.buildSystemPrompt(templateId, audience, imageStyle);

    const client = await this.createClient();
    const model = this.settings.getModel();

    let response: OpenAI.Chat.Completions.ChatCompletion;
    try {
      response = await client.chat.completions.create({
        model,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userContent },
        ],
        temperature: 0.5,
        max_tokens: 16384,
      });
    } catch (err: unknown) {
      const status = (err as { status?: number }).status;
      if (status === 404) {
        throw new Error(
          `Modell "${model}" ist in der aktuellen Region nicht verfügbar. ` +
          `Bitte wechsle in den Einstellungen zu einem anderen Modell (z.B. gemini-2.5-flash) oder einer anderen Region.`,
        );
      }
      throw err;
    }

    let markdown = response.choices[0]?.message?.content?.trim() ?? '';
    let slides = this.parseMarkdown(markdown);

    // Post-generation step 1: fix structural issues (images on wrong slides, etc.)
    const structuralResult = await this.validateStructure(client, markdown, slides);
    markdown = structuralResult.markdown;
    slides = structuralResult.slides;

    // Post-generation step 2: validate readability and auto-fix overflow
    const constraintMap = this.buildConstraintMapFromAll(theme, aiAnalysis);
    if (constraintMap.size > 0) {
      const validated = await this.validateAndFix(client, markdown, slides, constraintMap);
      markdown = validated.markdown;
      slides = validated.slides;
    }

    this.logger.log(`Generated ${slides.length} slides`);
    this.settings.incrementPresentationCount();
    return { markdown, slides };
  }

  /**
   * Check for structural issues: images on wrong slides, misplaced markdown syntax, etc.
   * Auto-fix via Gemini if problems found.
   */
  private async validateStructure(
    client: OpenAI,
    markdown: string,
    slides: SlideDto[],
  ): Promise<{ markdown: string; slides: SlideDto[] }> {
    const issues: string[] = [];

    for (let i = 0; i < slides.length; i++) {
      const slide = slides[i];
      const slideNum = i + 1;

      // Check: image markdown on non-image slides
      const rawSlides = markdown.split(/^\s*---\s*$/m).filter((s) => s.trim());
      const rawSlide = rawSlides[i] ?? '';
      const hasImageMd = /!\[[^\]]*\]\([^)]*\)/.test(rawSlide);

      if (hasImageMd && slide.layout !== 'image') {
        issues.push(
          `Folie ${slideNum} (${slide.layout}): Enthält Bild-Markdown ![...](placeholder), ist aber KEIN image-Layout. ` +
          `Bild-Syntax darf NUR auf <!-- layout: image --> Folien stehen.`,
        );
      }

      // Check: image slide without image markdown
      if (slide.layout === 'image' && !hasImageMd) {
        issues.push(
          `Folie ${slideNum} (image): Ist als Bild-Layout markiert, enthält aber kein ![Beschreibung](placeholder).`,
        );
      }

      // Check: image slide missing bullets (should have 2-4 for context)
      if (slide.layout === 'image' && slide.bullets.length === 0) {
        issues.push(
          `Folie ${slideNum} (image): Bild-Folie hat KEINE Bullet Points. ` +
          `Image-Folien MÜSSEN 2-4 Bullet Points mit Kernaussagen enthalten.`,
        );
      }
    }

    if (issues.length === 0) {
      this.logger.log('Structural check passed — no issues detected');
      return { markdown, slides };
    }

    this.logger.warn(`Structural issues found: ${issues.length}, requesting Gemini fix`);

    const fixPrompt = `Du bist "Clarity Engine" — ein Experte für Präsentationsdesign. \
Die folgende Markdown-Präsentation hat STRUKTURELLE PROBLEME, die behoben werden müssen.

GEFUNDENE PROBLEME:
${issues.map((i) => `- ${i}`).join('\n')}

KORREKTUR-REGELN:
1. Bild-Markdown (![Beschreibung](placeholder)) darf NUR auf Folien mit <!-- layout: image --> stehen.
2. Wenn ein Bild auf einer falschen Folie steht: Erstelle eine NEUE image-Folie direkt danach \
   und verschiebe das Bild dorthin. Oder entferne das Bild und verlagere die Beschreibung in die Sprechernotizen.
3. image-Folien MÜSSEN enthalten: layout-Kommentar, # Titel, ![Beschreibung](placeholder), \
   2-4 Bullet Points mit Kernaussagen zum Bild, Sprechernotizen.
4. Behalte alle anderen Folien UNVERÄNDERT.
5. Behalte alle <!-- layout: TYPE --> und <!-- notes: --> Kommentare bei.
6. Antworte NUR mit dem vollständigen korrigierten Markdown.`;

    try {
      const response = await client.chat.completions.create({
        model: this.settings.getModel(),
        messages: [
          { role: 'system', content: fixPrompt },
          { role: 'user', content: markdown },
        ],
        temperature: 0.2,
        max_tokens: 8192,
      });

      const fixedMarkdown = response.choices[0]?.message?.content?.trim() ?? '';
      if (!fixedMarkdown) return { markdown, slides };

      const fixedSlides = this.parseMarkdown(fixedMarkdown);
      if (fixedSlides.length > 0) {
        this.logger.log(`Structural fix applied: ${slides.length} → ${fixedSlides.length} slides`);
        return { markdown: fixedMarkdown, slides: fixedSlides };
      }
    } catch (err) {
      this.logger.warn(`Structural fix LLM call failed: ${err}`);
    }

    return { markdown, slides };
  }

  private async buildSystemPrompt(templateId?: string, audience?: string, imageStyle?: string): Promise<string> {
    const audienceBlock = audience && AUDIENCE_PROMPTS[audience]
      ? `\n${AUDIENCE_PROMPTS[audience]}\n`
      : '';

    const imageBlock = imageStyle && IMAGE_STYLE_PROMPTS[imageStyle]
      ? `\n${IMAGE_STYLE_PROMPTS[imageStyle]}\n`
      : '';

    if (!templateId || templateId === 'default') {
      return `${BASE_SYSTEM_PROMPT}${audienceBlock}${imageBlock}`;
    }

    // Try rich profile first (from deep learning)
    const profile = this.analysis.getProfile(templateId);
    const aiAnalysis = await this.analysis.getAnalysis(templateId);
    const theme = await this.templates.getTheme(templateId);

    if (!theme && !aiAnalysis && !profile) {
      return `${BASE_SYSTEM_PROMPT}${audienceBlock}${imageBlock}`;
    }

    // Build template design info — profile is richest, then analysis, then theme
    let templateBlock = '';

    if (profile) {
      templateBlock = this.buildProfilePromptBlock(profile);
    } else if (aiAnalysis) {
      templateBlock = this.buildAnalysisPromptBlock(aiAnalysis, theme);
    } else if (theme) {
      templateBlock = this.buildThemeFallbackBlock(theme);
    }

    return `${BASE_SYSTEM_PROMPT}${audienceBlock}${imageBlock}\n${templateBlock}`;
  }

  private buildProfilePromptBlock(profile: TemplateProfile): string {
    // Group layouts by type for cleaner presentation
    const byType = new Map<string, Array<typeof profile.layout_catalog[0]>>();
    for (const m of profile.layout_catalog) {
      if (m.mapped_type === 'unused') continue;
      if (!byType.has(m.mapped_type)) byType.set(m.mapped_type, []);
      byType.get(m.mapped_type)!.push(m);
    }

    const layoutLines: string[] = [];
    for (const [type, layouts] of byType) {
      for (const m of layouts) {
        const constraintStr = this.formatConstraints(m);
        let line = `- ${type} ("${m.layout_name}"): ${m.description}${constraintStr}`;
        if (m.spatial_description) {
          line += `\n  Aufbau: ${m.spatial_description}`;
        }
        if (m.generation_rules) {
          line += `\n  REGELN: ${m.generation_rules}`;
        } else {
          line += `\n  → ${m.recommended_usage}`;
        }
        layoutLines.push(line);
      }
    }

    const colorInfo = profile.color_dna;
    const typo = profile.typography_dna;
    const chartGuide = profile.chart_guidelines;

    let chartBlock = '';
    if (chartGuide.color_sequence.length > 0) {
      chartBlock = `
DIAGRAMM-STIL (passend zum Corporate Design):
- Farbreihenfolge für Datenreihen: ${chartGuide.color_sequence.join(', ')}
- Schriftart: ${chartGuide.font_family}
- Stil: Modern, flach, ohne 3D-Effekte — passend zum Template-Design
- Nutze die chart-Folien aktiv für datengetriebene Aussagen!`;
    }

    return `
TEMPLATE-PROFIL "${profile.template_name || profile.template_id}" (Deep Learning):
${profile.description}

DESIGN-PERSÖNLICHKEIT:
${profile.design_personality || 'Professionelles Corporate Design'}

VERFÜGBARE LAYOUT-TYPEN: ${profile.supported_layout_types.join(', ')}

LAYOUT-KATALOG MIT EINSCHRÄNKUNGEN:
${layoutLines.join('\n')}

VISUELLE DNA:
- Schrift Überschriften: ${typo.heading_font}
- Schrift Text: ${typo.body_font}
- Primärfarbe: ${colorInfo.primary}
- Akzentfarben: ${colorInfo.accent1}, ${colorInfo.accent2}, ${colorInfo.accent3}
- Hintergrund: ${colorInfo.background}
- Folienformat: ${profile.slide_width_cm} × ${profile.slide_height_cm} cm
${chartBlock}

DESIGN-RICHTLINIEN:
${profile.guidelines}

DESIGN-QUALITÄTSREGELN (aus Template-Analyse — STRIKT EINHALTEN):
${profile.design_rules?.title_rules ? `- TITEL: ${profile.design_rules.title_rules}` : '- TITEL: Max. 50 Zeichen, einzeilig, als Aussage formuliert.'}
${profile.design_rules?.bullet_rules ? `- BULLETS: ${profile.design_rules.bullet_rules}` : '- BULLETS: 3-5 Stichpunkte pro Folie, max. 80 Zeichen pro Punkt. Aufzählungszeichen verwenden.'}
${profile.design_rules?.image_rules ? `- BILDER: ${profile.design_rules.image_rules}` : '- BILDER: Nur in PICTURE-Platzhaltern. Kein Text-Overlap.'}
${profile.design_rules?.typography_rules ? `- TYPOGRAFIE: ${profile.design_rules.typography_rules}` : ''}
${profile.design_rules?.spacing_rules ? `- LEERRAUM: ${profile.design_rules.spacing_rules}` : '- LEERRAUM: Keine Überlappungen. Ränder einhalten.'}
${profile.design_rules?.color_rules ? `- FARBEN: ${profile.design_rules.color_rules}` : '- FARBEN: Hoher Kontrast für Lesbarkeit.'}

REGELN FÜR TEXTLÄNGE:
- Überschreite NIEMALS die angegebenen maximalen Bullet-Anzahlen und Zeichenlimits.
- Wenn du mehr Inhalte hast als auf eine Folie passen, teile sie auf mehrere Folien auf.
  Verwende dafür den gleichen Layout-Typ und nummeriere: "Thema (1/2)", "Thema (2/2)".
- Bei two_column: Beide Spalten haben jeweils das gleiche Limit.
- Bei image: Der Textbereich ist deutlich kleiner — kürze radikal.
- Titel sollten einzeilig und unter dem Zeichenlimit bleiben.

STRATEGISCHE FOLIENGESTALTUNG:
- Folientitel als prägnante Aussagen formulieren: "Umsatz um 15% gesteigert" statt "Umsatz".
- Eine Kernaussage pro Folie — lieber eine Folie mehr als eine überladene.
- Alle Details, Hintergrundinformationen und Quellenangaben in Sprechernotizen (<!-- notes: -->).
- Nutze two_column für Gegenüberstellungen (Ist/Soll, Vor/Nach, Wir/Wettbewerb).
- Nutze section-Folien als Kapitelüberschriften für den narrativen roten Faden.
- Nutze chart-Folien für datengetriebene Aussagen mit konkreten Zahlen.
- Passe den Tonfall dem Corporate Design an: ${profile.design_personality ? profile.design_personality.split('.')[0] : 'professionell und modern'}.
`;
  }

  private formatConstraints(m: { max_bullets: number; max_chars_per_bullet: number; title_max_chars: number }): string {
    const constraints: string[] = [];
    if (m.max_bullets > 0) constraints.push(`max ${m.max_bullets} Bullets`);
    if (m.max_chars_per_bullet > 0) constraints.push(`max ${m.max_chars_per_bullet} Zeichen/Zeile`);
    if (m.title_max_chars > 0) constraints.push(`Titel max ${m.title_max_chars} Zeichen`);
    return constraints.length > 0 ? ` | Limits: ${constraints.join(', ')}` : '';
  }

  private buildAnalysisPromptBlock(
    analysis: TemplateAnalysis,
    theme: TemplateTheme | null,
  ): string {
    const mappings = analysis.layout_mappings
      .filter((m) => m.mapped_type !== 'unused')
      .map((m) => {
        const constraints = [];
        if (m.max_bullets > 0) constraints.push(`max ${m.max_bullets} Bullets`);
        if (m.max_chars_per_bullet > 0) constraints.push(`max ${m.max_chars_per_bullet} Zeichen/Zeile`);
        if (m.title_max_chars > 0) constraints.push(`Titel max ${m.title_max_chars} Zeichen`);
        const constraintStr = constraints.length > 0 ? ` | Limits: ${constraints.join(', ')}` : '';
        return `- ${m.mapped_type} ("${m.layout_name}"): ${m.description}${constraintStr}\n  → ${m.recommended_usage}`;
      })
      .join('\n');

    const themeInfo = theme
      ? `\nDas Design verwendet:
- Schriftart Überschriften: ${theme.heading_font}
- Schriftart Text: ${theme.body_font}
- Primärfarbe: ${theme.accent_color}
- Hintergrund: ${theme.bg_color}
- Folienformat: ${theme.slide_width_cm} × ${theme.slide_height_cm} cm`
      : '';

    return `
TEMPLATE-ANALYSE (KI-generiert):
${analysis.description}

VERFÜGBARE LAYOUTS MIT EINSCHRÄNKUNGEN:
${mappings}
${themeInfo}

DESIGN-RICHTLINIEN:
${analysis.guidelines}

REGELN FÜR TEXTLÄNGE:
- Überschreite NIEMALS die angegebenen maximalen Bullet-Anzahlen und Zeichenlimits.
- Wenn du mehr Inhalte hast als auf eine Folie passen, teile sie auf mehrere Folien auf.
  Verwende dafür den gleichen Layout-Typ und nummeriere: "Thema (1/2)", "Thema (2/2)".
- Bei two_column: Beide Spalten haben jeweils das gleiche Limit.
- Bei image: Der Textbereich ist deutlich kleiner — kürze radikal.
- Titel sollten einzeilig und unter dem Zeichenlimit bleiben.

STRATEGISCHE FOLIENGESTALTUNG:
- Folientitel als prägnante Aussagen formulieren: "Umsatz um 15% gesteigert" statt "Umsatz".
- Eine Kernaussage pro Folie — lieber eine Folie mehr als eine überladene.
- Alle Details, Hintergrundinformationen und Quellenangaben in Sprechernotizen (<!-- notes: -->).
- Nutze two_column für Gegenüberstellungen (Ist/Soll, Vor/Nach, Wir/Wettbewerb).
- Nutze section-Folien als Kapitelüberschriften für den narrativen roten Faden.
- Passe den Tonfall dem Corporate Design des Folienmasters an.
`;
  }

  private buildThemeFallbackBlock(theme: TemplateTheme): string {
    const layoutInfo = theme.layouts
      .map((name, i) => `  ${i}: "${name}"`)
      .join('\n');

    const constraintsBlock = this.buildConstraintsBlock(theme.layout_constraints);

    return `
FOLIENMASTER-INFORMATIONEN:
Der gewählte Folienmaster "${theme.template_name || theme.template_id}" hat folgende Layouts:
${layoutInfo}

Das Design verwendet:
- Schriftart Überschriften: ${theme.heading_font}
- Schriftart Text: ${theme.body_font}
- Primärfarbe: ${theme.accent_color}
- Hintergrund: ${theme.bg_color}
- Folienformat: ${theme.slide_width_cm} × ${theme.slide_height_cm} cm

DESIGN-EINSCHRÄNKUNGEN (WICHTIG — unbedingt einhalten!):
${constraintsBlock}

REGELN FÜR TEXTLÄNGE:
- Überschreite NIEMALS die angegebene maximale Bullet-Anzahl pro Folie.
- Halte Bullet Points kürzer als die angegebene max. Zeichenzahl pro Zeile.
- Wenn du mehr Inhalte hast als auf eine Folie passen, teile sie auf mehrere Folien auf.
  Verwende dafür den gleichen Layout-Typ und nummeriere: "Thema (1/2)", "Thema (2/2)".
- Bei two_column: Beide Spalten haben jeweils das gleiche Limit.
- Bei image: Der Textbereich ist deutlich kleiner — kürze radikal.
- Titel sollten einzeilig und unter dem Zeichenlimit bleiben.

STRATEGISCHE FOLIENGESTALTUNG:
- Folientitel als prägnante Aussagen formulieren: "Umsatz um 15% gesteigert" statt "Umsatz".
- Eine Kernaussage pro Folie — lieber eine Folie mehr als eine überladene.
- Alle Details, Hintergrundinformationen und Quellenangaben in Sprechernotizen (<!-- notes: -->).
- Nutze two_column für Gegenüberstellungen (Ist/Soll, Vor/Nach, Wir/Wettbewerb).
- Nutze section-Folien als Kapitelüberschriften für den narrativen roten Faden.
- Passe den Tonfall dem Corporate Design des Folienmasters an.
`;
  }

  private buildConstraintsBlock(constraints: LayoutConstraint[]): string {
    // Pick the primary (highest-scoring / first) constraint per layout type
    const primaryByType = new Map<string, LayoutConstraint>();
    for (const c of constraints) {
      if (!primaryByType.has(c.layout_type)) {
        primaryByType.set(c.layout_type, c);
      }
    }

    const lines: string[] = [];
    for (const [type, c] of primaryByType) {
      if (type === 'title' || type === 'section') {
        lines.push(`- ${type}: Titel max ${c.title_max_chars || 50} Zeichen`);
      } else if (type === 'content') {
        lines.push(
          `- ${type}: max ${c.max_bullets} Bullet Points, max ${c.max_chars_per_bullet} Zeichen/Zeile, Titel max ${c.title_max_chars} Zeichen`,
        );
      } else if (type === 'two_column') {
        lines.push(
          `- ${type}: max ${c.max_bullets} Bullets pro Spalte, max ${c.max_chars_per_bullet} Zeichen/Zeile, Titel max ${c.title_max_chars} Zeichen`,
        );
      } else if (type === 'image') {
        lines.push(
          `- ${type}: max ${c.max_bullets} Bullet Points, max ${c.max_chars_per_bullet} Zeichen/Zeile (Textbereich neben Bild ist klein!)`,
        );
      } else if (type === 'closing') {
        lines.push(`- ${type}: max ${c.max_bullets} Zeilen, max ${c.max_chars_per_bullet} Zeichen/Zeile`);
      }
    }
    return lines.join('\n');
  }

  // ── Readability validation & auto-split ────────────────────────────────

  /** Build a unified constraint map from AI analysis (preferred) or theme extraction (fallback). */
  private buildConstraintMapFromAll(
    theme: TemplateTheme | null,
    aiAnalysis: TemplateAnalysis | null,
  ): Map<string, LayoutConstraint> {
    const map = new Map<string, LayoutConstraint>();

    // Prefer AI analysis
    if (aiAnalysis?.layout_mappings?.length) {
      for (const m of aiAnalysis.layout_mappings) {
        if (m.mapped_type === 'unused' || map.has(m.mapped_type)) continue;
        map.set(m.mapped_type, {
          layout_name: m.layout_name,
          layout_type: m.mapped_type,
          placeholders: [],
          max_bullets: m.max_bullets,
          max_chars_per_bullet: m.max_chars_per_bullet,
          title_max_chars: m.title_max_chars,
        });
      }
    }

    // Fill gaps from theme constraints
    if (theme?.layout_constraints?.length) {
      for (const c of theme.layout_constraints) {
        if (!map.has(c.layout_type)) {
          map.set(c.layout_type, c);
        }
      }
    }

    return map;
  }

  private async validateAndFix(
    client: OpenAI,
    markdown: string,
    slides: SlideDto[],
    constraintMap: Map<string, LayoutConstraint>,
  ): Promise<{ markdown: string; slides: SlideDto[] }> {
    const issues = this.detectOverflow(slides, constraintMap);

    if (issues.length === 0) {
      this.logger.log('Readability check passed — no overflow detected');
      return { markdown, slides };
    }

    this.logger.warn(`Readability issues found on ${issues.length} slide(s), requesting Gemini fix`);

    const fixPrompt = this.buildFixPrompt(markdown, issues, constraintMap);

    try {
      const response = await client.chat.completions.create({
        model: this.settings.getModel(),
        messages: [
          { role: 'system', content: fixPrompt },
          { role: 'user', content: markdown },
        ],
        temperature: 0.3,
        max_tokens: 4096,
      });

      const fixedMarkdown = response.choices[0]?.message?.content?.trim() ?? '';
      if (!fixedMarkdown) {
        return { markdown, slides };
      }

      const fixedSlides = this.parseMarkdown(fixedMarkdown);
      // Only accept the fix if it actually produced slides
      if (fixedSlides.length > 0) {
        this.logger.log(
          `Readability fix applied: ${slides.length} → ${fixedSlides.length} slides`,
        );
        return { markdown: fixedMarkdown, slides: fixedSlides };
      }
    } catch (err) {
      this.logger.warn(`Readability fix LLM call failed: ${err}`);
    }

    return { markdown, slides };
  }

  private detectOverflow(
    slides: SlideDto[],
    constraintMap: Map<string, LayoutConstraint>,
  ): Array<{ slideIndex: number; slide: SlideDto; reason: string }> {
    const issues: Array<{ slideIndex: number; slide: SlideDto; reason: string }> = [];

    for (let i = 0; i < slides.length; i++) {
      const slide = slides[i];
      const constraint = constraintMap.get(slide.layout);
      if (!constraint) continue;

      const reasons: string[] = [];

      // Check bullet count overflow
      if (constraint.max_bullets > 0 && slide.bullets.length > constraint.max_bullets) {
        reasons.push(
          `${slide.bullets.length} Bullets (max ${constraint.max_bullets})`,
        );
      }

      // Check bullet text length
      if (constraint.max_chars_per_bullet > 0) {
        for (const bullet of slide.bullets) {
          if (bullet.length > constraint.max_chars_per_bullet) {
            reasons.push(
              `Bullet "${bullet.slice(0, 30)}..." hat ${bullet.length} Zeichen (max ${constraint.max_chars_per_bullet})`,
            );
            break; // one example is enough
          }
        }
      }

      // Check title length
      if (constraint.title_max_chars > 0 && slide.title.length > constraint.title_max_chars) {
        reasons.push(
          `Titel "${slide.title.slice(0, 30)}..." hat ${slide.title.length} Zeichen (max ${constraint.title_max_chars})`,
        );
      }

      if (reasons.length > 0) {
        issues.push({ slideIndex: i + 1, slide, reason: reasons.join('; ') });
      }
    }

    return issues;
  }

  private buildFixPrompt(
    _markdown: string,
    issues: Array<{ slideIndex: number; slide: SlideDto; reason: string }>,
    constraintMap: Map<string, LayoutConstraint>,
  ): string {
    const issueList = issues
      .map((i) => `- Folie ${i.slideIndex} (${i.slide.layout}): ${i.reason}`)
      .join('\n');

    const constraintList = [...constraintMap.entries()]
      .map(([type, c]) => {
        if (type === 'content') {
          return `- ${type}: max ${c.max_bullets} Bullets, max ${c.max_chars_per_bullet} Zeichen/Zeile`;
        }
        if (type === 'two_column') {
          return `- ${type}: max ${c.max_bullets} Bullets/Spalte, max ${c.max_chars_per_bullet} Zeichen/Zeile`;
        }
        if (type === 'image') {
          return `- ${type}: max ${c.max_bullets} Bullets, max ${c.max_chars_per_bullet} Zeichen/Zeile`;
        }
        return `- ${type}: max ${c.title_max_chars} Zeichen Titel`;
      })
      .join('\n');

    return `Du bist "Clarity Engine" — ein Experte für Präsentationsdesign. Die folgende Markdown-Präsentation \
hat Lesbarkeitsprobleme, weil Texte die Platzhalter-Grenzen des Folienmasters überschreiten.

PROBLEME:
${issueList}

DESIGN-LIMITS:
${constraintList}

REGELN:
1. Gib die GESAMTE korrigierte Präsentation im gleichen Markdown-Format zurück.
2. Kürze zu lange Bullet Points auf die Kernaussage. Details in <!-- notes: --> verschieben.
3. Teile übervolle Folien in mehrere Folien auf: gleicher Layout-Typ, Titel mit "(1/2)", "(2/2)".
4. Folientitel als prägnante Aussagen formulieren, nicht als Schlagworte.
5. Behalte alle <!-- layout: TYPE --> und <!-- notes: --> Kommentare bei.
6. Ändere NICHT Folien, die keine Probleme haben.
7. Antworte NUR mit dem korrigierten Markdown.`;
  }

  parseMarkdown(markdown: string): SlideDto[] {
    const rawSlides = markdown
      .split(/^\s*---\s*$/m)
      .filter((s) => s.trim());

    const slides = rawSlides.map((raw) => this.parseSlide(raw.trim())).filter(Boolean) as SlideDto[];

    for (const slide of slides) {
      if (slide.layout === 'image' && slide.bullets.length === 0) {
        this.logger.warn(
          `Image slide "${slide.title}" has no bullet points — violates "Klarheit vor Dekoration"`,
        );
      }
    }

    return slides;
  }

  private parseSlide(raw: string): SlideDto | null {
    if (!raw) return null;

    const layoutMatch = raw.match(/<!--\s*layout:\s*(\w+)\s*-->/);
    let layout = layoutMatch?.[1] ?? 'content';
    if (!VALID_LAYOUTS.has(layout)) layout = 'content';

    const notesMatch = raw.match(/<!--\s*notes:\s*([\s\S]*?)\s*-->/);
    const notes = notesMatch?.[1]?.trim() ?? '';

    const clean = raw
      .replace(/<!--\s*layout:\s*\w+\s*-->/g, '')
      .replace(/<!--\s*notes:[\s\S]*?-->/g, '')
      .trim();

    const h1 = clean.match(/^#\s+(.+)$/m);
    const h2 = clean.match(/^##\s+(.+)$/m);
    const bullets = [...clean.matchAll(/^[-*]\s+(.+)$/gm)].map((m) => m[1]);

    let leftColumn = '';
    let rightColumn = '';
    if (layout === 'two_column') {
      [leftColumn, rightColumn] = this.parseTwoColumns(clean);
    }

    // Extract image description from ![desc](url)
    const imgMatch = clean.match(/!\[([^\]]+)\]\([^)]*\)/);
    const imageDescription = imgMatch?.[1]?.trim() ?? '';

    return {
      layout,
      title: h1?.[1]?.trim() ?? '',
      subtitle: h2?.[1]?.trim() ?? '',
      body: '',
      bullets,
      notes,
      imageDescription,
      leftColumn,
      rightColumn,
    };
  }

  private parseTwoColumns(text: string): [string, string] {
    // Find all ## headings and their positions
    const headingPattern = /^##\s+.+$/gm;
    const headings: Array<{ index: number; length: number }> = [];
    let match: RegExpExecArray | null;
    while ((match = headingPattern.exec(text)) !== null) {
      headings.push({ index: match.index, length: match[0].length });
    }

    // Need exactly 2 ## headings for left/right columns
    if (headings.length < 2) return ['', ''];

    const extractBullets = (t: string): string =>
      [...t.matchAll(/^[-*]\s+(.+)$/gm)]
        .map((m) => `- ${m[1]}`)
        .join('\n');

    const leftContent = text.slice(
      headings[0].index + headings[0].length,
      headings[1].index,
    );
    const rightContent = text.slice(headings[1].index + headings[1].length);

    return [extractBullets(leftContent), extractBullets(rightContent)];
  }
}
