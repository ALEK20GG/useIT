/**
 * Bilingual (Italian/English) help text and UI strings.
 *
 * Implements Requirement 20.5: Documentation available in both Italian and English.
 *
 * Usage:
 *   import { t, setLocale, locale } from '$lib/i18n';
 *   // In Svelte: {t('tooltip.deviceRecognition')}
 */

export type Locale = 'it' | 'en';

// ─── Translation catalogue ────────────────────────────────────────────────────

const translations = {
  it: {
    // ── Navigation ──────────────────────────────────────────────────────────
    'nav.home': 'Home',
    'nav.scan': 'Scansiona',
    'nav.search': 'Cerca',
    'nav.pdf': 'PDF',
    'nav.files': 'File',
    'nav.folders': 'Cartelle',
    'nav.user': 'Area Personale',
    'nav.help': 'Guida',

    // ── Tooltips ─────────────────────────────────────────────────────────────
    'tooltip.deviceRecognition':
      'Scatta o carica una foto del dispositivo per identificarlo automaticamente tramite intelligenza artificiale.',
    'tooltip.qrScanner':
      'Scansiona il codice QR stampato sul dispositivo per accedere direttamente alla sua documentazione.',
    'tooltip.folderFilter':
      'Filtra i risultati di ricerca per cartella. Seleziona "Dispositivi" per cercare solo nella documentazione tecnica.',
    'tooltip.semanticSearch':
      'La ricerca semantica comprende il significato della tua domanda, non solo le parole esatte. Prova a descrivere il problema con parole tue.',
    'tooltip.confidenceScore':
      'Indica quanto il sistema è sicuro del riconoscimento. Verde = alta confidenza (>80%), Giallo = media (50-80%), Rosso = bassa (<50%).',
    'tooltip.uploadFolder':
      'Scegli in quale cartella indicizzare il documento. I file nella cartella "Dispositivi" saranno cercabili insieme alla documentazione tecnica.',
    'tooltip.saveContent':
      "Salva questo risultato nella tua Area Personale per ritrovarlo facilmente in seguito.",
    'tooltip.exportContent':
      'Esporta i contenuti salvati in formato PDF o JSON per usarli offline.',
    'tooltip.bulkDelete':
      'Seleziona più file tenendo premuto Ctrl (o Cmd su Mac) e poi clicca Elimina.',
    'tooltip.hybridSearch':
      'La ricerca ibrida combina la ricerca semantica con quella per parole chiave per risultati più precisi.',
    'tooltip.mockService':
      'Il servizio AI è in modalità simulazione. I risultati sono generati automaticamente a scopo dimostrativo.',

    // ── Onboarding tour ───────────────────────────────────────────────────────
    'tour.welcome.title': 'Benvenuto in UseIt!',
    'tour.welcome.body':
      'UseIt è la tua piattaforma intelligente per la documentazione dei dispositivi. Fai un breve tour per scoprire le funzionalità principali.',
    'tour.scan.title': 'Riconosci i dispositivi',
    'tour.scan.body':
      'Vai su "Scansiona" per fotografare un dispositivo o scansionare il suo QR code. Il sistema lo identificherà automaticamente e troverà la documentazione.',
    'tour.search.title': 'Cerca nella documentazione',
    'tour.search.body':
      'Usa la ricerca semantica per trovare informazioni. Puoi filtrare per cartella (Dispositivi, Appunti, Scuola) o cercare in tutto il sistema.',
    'tour.folders.title': 'Organizza i contenuti',
    'tour.folders.body':
      'Le cartelle ti permettono di organizzare la documentazione per categoria. Crea nuove cartelle per i tuoi progetti.',
    'tour.user.title': 'Area Personale',
    'tour.user.body':
      'Salva i risultati di ricerca più utili nella tua Area Personale. Puoi organizzarli in cartelle private ed esportarli.',
    'tour.done': 'Inizia a usare UseIt',
    'tour.next': 'Avanti',
    'tour.prev': 'Indietro',
    'tour.skip': 'Salta il tour',
    'tour.step': 'Passo {current} di {total}',

    // ── Help page ─────────────────────────────────────────────────────────────
    'help.title': 'Guida e Documentazione',
    'help.subtitle': 'Tutto quello che ti serve per usare UseIt al meglio.',
    'help.section.deviceRecognition': 'Riconoscimento dispositivi',
    'help.section.search': 'Ricerca semantica',
    'help.section.contentManagement': 'Gestione contenuti',
    'help.section.userArea': 'Area Personale',
    'help.section.api': 'API per sviluppatori',
    'help.deviceRecognition.intro':
      'UseIt può identificare automaticamente i dispositivi elettronici tramite foto o codice QR.',
    'help.deviceRecognition.step1': 'Vai alla pagina "Scansiona" dal menu principale.',
    'help.deviceRecognition.step2':
      'Scegli la modalità: "Foto dispositivo" per caricare/scattare una foto, oppure "Scansiona QR" per il codice QR.',
    'help.deviceRecognition.step3':
      'Carica l\'immagine o avvia la fotocamera e premi "Riconosci dispositivo".',
    'help.deviceRecognition.step4':
      'Il sistema mostrerà il dispositivo identificato con il livello di confidenza.',
    'help.deviceRecognition.fallback':
      'Se il riconoscimento automatico non funziona, usa la selezione manuale per inserire il nome del dispositivo.',
    'help.search.intro':
      'La ricerca semantica comprende il significato delle tue domande, non solo le parole esatte.',
    'help.search.step1': 'Vai alla pagina "Cerca" dal menu principale.',
    'help.search.step2': 'Digita la tua domanda in linguaggio naturale.',
    'help.search.step3':
      'Opzionalmente, seleziona una cartella per limitare la ricerca a una categoria specifica.',
    'help.search.step4': 'I risultati sono ordinati per rilevanza semantica.',
    'help.search.tip':
      'Suggerimento: descrivi il problema con parole tue invece di usare termini tecnici esatti.',
    'help.contentManagement.intro':
      'Puoi caricare documenti PDF, DOC, DOCX e TXT per renderli ricercabili.',
    'help.contentManagement.step1': 'Vai alla pagina "File" dal menu principale.',
    'help.contentManagement.step2': 'Clicca "Carica file" e seleziona il documento.',
    'help.contentManagement.step3': 'Scegli la cartella di destinazione.',
    'help.contentManagement.step4':
      'Il sistema estrarrà automaticamente il testo e lo indicizzerà.',
    'help.contentManagement.formats': 'Formati supportati: PDF, DOC, DOCX, TXT (max 10 MB).',
    'help.userArea.intro':
      "L'Area Personale ti permette di salvare e organizzare i risultati di ricerca più utili.",
    'help.userArea.step1': 'Clicca l\'icona "Salva" su qualsiasi risultato di ricerca.',
    'help.userArea.step2': 'Vai alla pagina "Area Personale" per vedere i contenuti salvati.',
    'help.userArea.step3': 'Organizza i contenuti in cartelle personali.',
    'help.userArea.step4': 'Esporta i contenuti in PDF o JSON.',

    // ── Common UI ─────────────────────────────────────────────────────────────
    'common.loading': 'Caricamento in corso…',
    'common.error': 'Si è verificato un errore.',
    'common.retry': 'Riprova',
    'common.close': 'Chiudi',
    'common.save': 'Salva',
    'common.cancel': 'Annulla',
    'common.delete': 'Elimina',
    'common.confirm': 'Conferma',
    'common.search': 'Cerca',
    'common.upload': 'Carica',
    'common.download': 'Scarica',
    'common.export': 'Esporta',
    'common.back': 'Indietro',
    'common.next': 'Avanti',
    'common.done': 'Fatto',
    'common.yes': 'Sì',
    'common.no': 'No',
    'common.or': 'oppure',
    'common.and': 'e',
    'common.learnMore': 'Scopri di più',
    'common.showHelp': 'Mostra guida',
    'common.hideHelp': 'Nascondi guida',
  },

  en: {
    // ── Navigation ──────────────────────────────────────────────────────────
    'nav.home': 'Home',
    'nav.scan': 'Scan',
    'nav.search': 'Search',
    'nav.pdf': 'PDF',
    'nav.files': 'Files',
    'nav.folders': 'Folders',
    'nav.user': 'My Area',
    'nav.help': 'Help',

    // ── Tooltips ─────────────────────────────────────────────────────────────
    'tooltip.deviceRecognition':
      'Take or upload a photo of the device to automatically identify it using AI.',
    'tooltip.qrScanner':
      'Scan the QR code printed on the device to directly access its documentation.',
    'tooltip.folderFilter':
      'Filter search results by folder. Select "Devices" to search only in technical documentation.',
    'tooltip.semanticSearch':
      "Semantic search understands the meaning of your question, not just exact words. Try describing the problem in your own words.",
    'tooltip.confidenceScore':
      'Indicates how confident the system is about the recognition. Green = high confidence (>80%), Yellow = medium (50-80%), Red = low (<50%).',
    'tooltip.uploadFolder':
      'Choose which folder to index the document in. Files in the "Devices" folder will be searchable alongside technical documentation.',
    'tooltip.saveContent':
      'Save this result to your Personal Area to easily find it later.',
    'tooltip.exportContent':
      'Export saved content in PDF or JSON format for offline use.',
    'tooltip.bulkDelete':
      'Select multiple files by holding Ctrl (or Cmd on Mac) then click Delete.',
    'tooltip.hybridSearch':
      'Hybrid search combines semantic search with keyword search for more precise results.',
    'tooltip.mockService':
      'The AI service is in simulation mode. Results are automatically generated for demonstration purposes.',

    // ── Onboarding tour ───────────────────────────────────────────────────────
    'tour.welcome.title': 'Welcome to UseIt!',
    'tour.welcome.body':
      'UseIt is your intelligent device documentation platform. Take a quick tour to discover the main features.',
    'tour.scan.title': 'Recognize devices',
    'tour.scan.body':
      'Go to "Scan" to photograph a device or scan its QR code. The system will automatically identify it and find the documentation.',
    'tour.search.title': 'Search documentation',
    'tour.search.body':
      'Use semantic search to find information. You can filter by folder (Devices, Notes, School) or search across the entire system.',
    'tour.folders.title': 'Organize content',
    'tour.folders.body':
      'Folders let you organize documentation by category. Create new folders for your projects.',
    'tour.user.title': 'Personal Area',
    'tour.user.body':
      'Save the most useful search results to your Personal Area. You can organize them in private folders and export them.',
    'tour.done': 'Start using UseIt',
    'tour.next': 'Next',
    'tour.prev': 'Back',
    'tour.skip': 'Skip tour',
    'tour.step': 'Step {current} of {total}',

    // ── Help page ─────────────────────────────────────────────────────────────
    'help.title': 'Help & Documentation',
    'help.subtitle': 'Everything you need to get the most out of UseIt.',
    'help.section.deviceRecognition': 'Device recognition',
    'help.section.search': 'Semantic search',
    'help.section.contentManagement': 'Content management',
    'help.section.userArea': 'Personal Area',
    'help.section.api': 'API for developers',
    'help.deviceRecognition.intro':
      'UseIt can automatically identify electronic devices via photo or QR code.',
    'help.deviceRecognition.step1': 'Go to the "Scan" page from the main menu.',
    'help.deviceRecognition.step2':
      'Choose the mode: "Device photo" to upload/take a photo, or "Scan QR" for the QR code.',
    'help.deviceRecognition.step3':
      'Upload the image or start the camera and press "Recognize device".',
    'help.deviceRecognition.step4':
      'The system will show the identified device with the confidence level.',
    'help.deviceRecognition.fallback':
      'If automatic recognition does not work, use manual selection to enter the device name.',
    'help.search.intro':
      'Semantic search understands the meaning of your questions, not just exact words.',
    'help.search.step1': 'Go to the "Search" page from the main menu.',
    'help.search.step2': 'Type your question in natural language.',
    'help.search.step3':
      'Optionally, select a folder to limit the search to a specific category.',
    'help.search.step4': 'Results are sorted by semantic relevance.',
    'help.search.tip':
      'Tip: describe the problem in your own words instead of using exact technical terms.',
    'help.contentManagement.intro':
      'You can upload PDF, DOC, DOCX and TXT documents to make them searchable.',
    'help.contentManagement.step1': 'Go to the "Files" page from the main menu.',
    'help.contentManagement.step2': 'Click "Upload file" and select the document.',
    'help.contentManagement.step3': 'Choose the destination folder.',
    'help.contentManagement.step4':
      'The system will automatically extract the text and index it.',
    'help.contentManagement.formats': 'Supported formats: PDF, DOC, DOCX, TXT (max 10 MB).',
    'help.userArea.intro':
      'The Personal Area lets you save and organize the most useful search results.',
    'help.userArea.step1': 'Click the "Save" icon on any search result.',
    'help.userArea.step2': 'Go to the "Personal Area" page to see saved content.',
    'help.userArea.step3': 'Organize content in personal folders.',
    'help.userArea.step4': 'Export content in PDF or JSON.',

    // ── Common UI ─────────────────────────────────────────────────────────────
    'common.loading': 'Loading…',
    'common.error': 'An error occurred.',
    'common.retry': 'Retry',
    'common.close': 'Close',
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.delete': 'Delete',
    'common.confirm': 'Confirm',
    'common.search': 'Search',
    'common.upload': 'Upload',
    'common.download': 'Download',
    'common.export': 'Export',
    'common.back': 'Back',
    'common.next': 'Next',
    'common.done': 'Done',
    'common.yes': 'Yes',
    'common.no': 'No',
    'common.or': 'or',
    'common.and': 'and',
    'common.learnMore': 'Learn more',
    'common.showHelp': 'Show help',
    'common.hideHelp': 'Hide help',
  },
} as const;

type TranslationKey = keyof (typeof translations)['it'];

// ─── Locale state ─────────────────────────────────────────────────────────────

/** Detect browser/system locale, defaulting to Italian. */
function detectLocale(): Locale {
  if (typeof navigator === 'undefined') return 'it';
  const lang = navigator.language?.toLowerCase() ?? '';
  if (lang.startsWith('en')) return 'en';
  return 'it';
}

let _locale: Locale = detectLocale();

/** Get the current locale. */
export function getLocale(): Locale {
  return _locale;
}

/** Set the active locale. */
export function setLocale(locale: Locale): void {
  _locale = locale;
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('useit-locale', locale);
  }
}

/** Load persisted locale from localStorage (call once on app init). */
export function loadPersistedLocale(): void {
  if (typeof localStorage === 'undefined') return;
  const saved = localStorage.getItem('useit-locale') as Locale | null;
  if (saved === 'it' || saved === 'en') {
    _locale = saved;
  }
}

// ─── Translation function ─────────────────────────────────────────────────────

/**
 * Translate a key to the current locale.
 *
 * Supports simple interpolation: t('tour.step', { current: 2, total: 5 })
 * → "Passo 2 di 5"
 */
export function t(key: TranslationKey, vars?: Record<string, string | number>): string {
  const catalogue = translations[_locale] as Record<string, string>;
  let text = catalogue[key] ?? (translations['it'] as Record<string, string>)[key] ?? key;

  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      text = text.replace(`{${k}}`, String(v));
    }
  }

  return text;
}

/** Convenience: translate with explicit locale override. */
export function tLocale(
  locale: Locale,
  key: TranslationKey,
  vars?: Record<string, string | number>,
): string {
  const catalogue = translations[locale] as Record<string, string>;
  let text = catalogue[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      text = text.replace(`{${k}}`, String(v));
    }
  }
  return text;
}

export { translations };
export type { TranslationKey };
