/**
 * Property-based tests for documentation and user guidance features.
 *
 * Task 19.1 – Property tests for documentation features.
 *
 * **Validates: Requirements 20.1, 20.2, 20.5**
 *
 * Property 66: Help Text and Tooltips – Validates: Requirements 20.1
 * Property 67: Feature Onboarding – Validates: Requirements 20.2
 * Property 68: Multilingual Documentation – Validates: Requirements 20.5
 */

import { describe, it, expect } from 'vitest';
import { translations, t, tLocale, setLocale, getLocale } from './i18n';
import type { Locale, TranslationKey } from './i18n';

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** All translation keys defined in the Italian catalogue (source of truth). */
const ALL_KEYS = Object.keys(translations.it) as TranslationKey[];

/** All supported locales. */
const LOCALES: Locale[] = ['it', 'en'];

/** Tooltip-specific keys. */
const TOOLTIP_KEYS = ALL_KEYS.filter((k) => k.startsWith('tooltip.'));

/** Tour-specific keys. */
const TOUR_KEYS = ALL_KEYS.filter((k) => k.startsWith('tour.'));

/** Help-page-specific keys. */
const HELP_KEYS = ALL_KEYS.filter((k) => k.startsWith('help.'));

// ─── Property 66: Help Text and Tooltips ─────────────────────────────────────
// Validates: Requirement 20.1 – in-application help text and tooltips for complex features.

describe('Property 66: Help Text and Tooltips (Requirement 20.1)', () => {
  it('should define tooltip keys for all complex features', () => {
    const expectedTooltipFeatures = [
      'tooltip.deviceRecognition',
      'tooltip.qrScanner',
      'tooltip.folderFilter',
      'tooltip.semanticSearch',
      'tooltip.confidenceScore',
      'tooltip.uploadFolder',
      'tooltip.saveContent',
      'tooltip.exportContent',
      'tooltip.bulkDelete',
      'tooltip.hybridSearch',
      'tooltip.mockService',
    ] as TranslationKey[];

    for (const key of expectedTooltipFeatures) {
      expect(ALL_KEYS, `Missing tooltip key: ${key}`).toContain(key);
    }
  });

  it('should have non-empty tooltip text for every tooltip key in Italian', () => {
    for (const key of TOOLTIP_KEYS) {
      const text = tLocale('it', key);
      expect(text, `Empty tooltip for key "${key}" in Italian`).toBeTruthy();
      expect(text.length, `Tooltip "${key}" too short`).toBeGreaterThan(10);
    }
  });

  it('should have non-empty tooltip text for every tooltip key in English', () => {
    for (const key of TOOLTIP_KEYS) {
      const text = tLocale('en', key);
      expect(text, `Empty tooltip for key "${key}" in English`).toBeTruthy();
      expect(text.length, `Tooltip "${key}" too short`).toBeGreaterThan(10);
    }
  });

  it('should return the key itself when a key is missing (graceful fallback)', () => {
    // Cast to bypass type safety to simulate a missing key
    const missingKey = 'tooltip.nonExistentFeature' as TranslationKey;
    const result = tLocale('it', missingKey);
    // Should return the key string, not throw
    expect(result).toBe(missingKey);
  });

  it('should have tooltip text that is different from the key (not just echoing the key)', () => {
    for (const key of TOOLTIP_KEYS) {
      const text = tLocale('it', key);
      expect(text, `Tooltip "${key}" appears to just echo the key`).not.toBe(key);
    }
  });

  it('should cover all major feature areas with tooltips', () => {
    const featureAreas = ['deviceRecognition', 'qrScanner', 'folderFilter', 'semanticSearch', 'uploadFolder'];
    for (const area of featureAreas) {
      const key = `tooltip.${area}` as TranslationKey;
      expect(TOOLTIP_KEYS, `No tooltip for feature area: ${area}`).toContain(key);
    }
  });
});

// ─── Property 67: Feature Onboarding ─────────────────────────────────────────
// Validates: Requirement 20.2 – guided tours or onboarding flows when users access new features.

describe('Property 67: Feature Onboarding (Requirement 20.2)', () => {
  it('should define tour step keys for all major features', () => {
    const expectedTourSteps = [
      'tour.welcome.title',
      'tour.welcome.body',
      'tour.scan.title',
      'tour.scan.body',
      'tour.search.title',
      'tour.search.body',
      'tour.folders.title',
      'tour.folders.body',
      'tour.user.title',
      'tour.user.body',
    ] as TranslationKey[];

    for (const key of expectedTourSteps) {
      expect(ALL_KEYS, `Missing tour key: ${key}`).toContain(key);
    }
  });

  it('should have non-empty tour content for every tour key in Italian', () => {
    for (const key of TOUR_KEYS) {
      const text = tLocale('it', key);
      expect(text, `Empty tour text for key "${key}" in Italian`).toBeTruthy();
    }
  });

  it('should have non-empty tour content for every tour key in English', () => {
    for (const key of TOUR_KEYS) {
      const text = tLocale('en', key);
      expect(text, `Empty tour text for key "${key}" in English`).toBeTruthy();
    }
  });

  it('should define navigation labels for the tour (next, prev, skip, done)', () => {
    const navKeys = ['tour.next', 'tour.prev', 'tour.skip', 'tour.done'] as TranslationKey[];
    for (const key of navKeys) {
      expect(ALL_KEYS, `Missing tour navigation key: ${key}`).toContain(key);
      const itText = tLocale('it', key);
      const enText = tLocale('en', key);
      expect(itText).toBeTruthy();
      expect(enText).toBeTruthy();
    }
  });

  it('should support step counter interpolation in tour.step key', () => {
    const itResult = tLocale('it', 'tour.step', { current: 2, total: 5 });
    const enResult = tLocale('en', 'tour.step', { current: 2, total: 5 });

    // Should contain the interpolated numbers
    expect(itResult).toContain('2');
    expect(itResult).toContain('5');
    expect(enResult).toContain('2');
    expect(enResult).toContain('5');

    // Should not contain raw placeholders
    expect(itResult).not.toContain('{current}');
    expect(itResult).not.toContain('{total}');
    expect(enResult).not.toContain('{current}');
    expect(enResult).not.toContain('{total}');
  });

  it('should cover all main application sections in the tour', () => {
    const tourSections = ['welcome', 'scan', 'search', 'folders', 'user'];
    for (const section of tourSections) {
      const titleKey = `tour.${section}.title` as TranslationKey;
      const bodyKey = `tour.${section}.body` as TranslationKey;
      expect(TOUR_KEYS, `Missing tour title for section: ${section}`).toContain(titleKey);
      expect(TOUR_KEYS, `Missing tour body for section: ${section}`).toContain(bodyKey);
    }
  });

  it('should have tour body text that is descriptive (more than 20 chars)', () => {
    const bodyKeys = TOUR_KEYS.filter((k) => k.endsWith('.body'));
    for (const key of bodyKeys) {
      const text = tLocale('it', key);
      expect(text.length, `Tour body "${key}" is too short to be descriptive`).toBeGreaterThan(20);
    }
  });
});

// ─── Property 68: Multilingual Documentation ─────────────────────────────────
// Validates: Requirement 20.5 – documentation available in both Italian and English.

describe('Property 68: Multilingual Documentation (Requirement 20.5)', () => {
  it('should have the same set of keys in Italian and English catalogues', () => {
    const itKeys = new Set(Object.keys(translations.it));
    const enKeys = new Set(Object.keys(translations.en));

    // Every Italian key must exist in English
    for (const key of itKeys) {
      expect(enKeys, `Key "${key}" exists in Italian but not in English`).toContain(key);
    }

    // Every English key must exist in Italian
    for (const key of enKeys) {
      expect(itKeys, `Key "${key}" exists in English but not in Italian`).toContain(key);
    }
  });

  it('should return different text for Italian and English for most keys', () => {
    // At least 50% of keys should have different translations (some may be identical, e.g. proper nouns)
    let differentCount = 0;
    for (const key of ALL_KEYS) {
      const itText = tLocale('it', key);
      const enText = tLocale('en', key);
      if (itText !== enText) differentCount++;
    }
    const ratio = differentCount / ALL_KEYS.length;
    expect(ratio, `Only ${Math.round(ratio * 100)}% of keys differ between IT and EN`).toBeGreaterThan(0.5);
  });

  it('should switch locale and return correct translations via t()', () => {
    setLocale('it');
    expect(getLocale()).toBe('it');
    const itTitle = t('help.title');
    expect(itTitle).toBeTruthy();

    setLocale('en');
    expect(getLocale()).toBe('en');
    const enTitle = t('help.title');
    expect(enTitle).toBeTruthy();

    // Titles should differ between locales
    expect(itTitle).not.toBe(enTitle);
  });

  it('should have Italian as the default fallback locale', () => {
    // tLocale with 'it' should always return a non-key value for defined keys
    for (const key of ALL_KEYS.slice(0, 20)) {
      const text = tLocale('it', key);
      expect(text, `Italian fallback missing for key "${key}"`).toBeTruthy();
      expect(text).not.toBe('');
    }
  });

  it('should have help section keys for all documented features', () => {
    const expectedHelpSections = [
      'help.section.deviceRecognition',
      'help.section.search',
      'help.section.contentManagement',
      'help.section.userArea',
      'help.section.api',
    ] as TranslationKey[];

    for (const key of expectedHelpSections) {
      expect(ALL_KEYS, `Missing help section key: ${key}`).toContain(key);
      const itText = tLocale('it', key);
      const enText = tLocale('en', key);
      expect(itText).toBeTruthy();
      expect(enText).toBeTruthy();
    }
  });

  it('should have user manual content for device recognition, search, and content management', () => {
    // Requirement 20.3: user manuals for device recognition, search, and content management
    const manualKeys: TranslationKey[] = [
      'help.deviceRecognition.intro',
      'help.deviceRecognition.step1',
      'help.search.intro',
      'help.search.step1',
      'help.contentManagement.intro',
      'help.contentManagement.step1',
    ];

    for (const key of manualKeys) {
      expect(ALL_KEYS, `Missing user manual key: ${key}`).toContain(key);
      const itText = tLocale('it', key);
      const enText = tLocale('en', key);
      expect(itText.length, `Manual content "${key}" too short in Italian`).toBeGreaterThan(15);
      expect(enText.length, `Manual content "${key}" too short in English`).toBeGreaterThan(15);
    }
  });

  it('should support variable interpolation consistently across both locales', () => {
    const vars = { current: 3, total: 7 };
    const itResult = tLocale('it', 'tour.step', vars);
    const enResult = tLocale('en', 'tour.step', vars);

    // Both should interpolate the same values
    expect(itResult).toContain('3');
    expect(itResult).toContain('7');
    expect(enResult).toContain('3');
    expect(enResult).toContain('7');
  });

  it('should have common UI strings in both locales', () => {
    const commonKeys: TranslationKey[] = [
      'common.loading',
      'common.error',
      'common.retry',
      'common.close',
      'common.save',
      'common.cancel',
      'common.delete',
    ];

    for (const key of commonKeys) {
      expect(ALL_KEYS, `Missing common UI key: ${key}`).toContain(key);
      const itText = tLocale('it', key);
      const enText = tLocale('en', key);
      expect(itText).toBeTruthy();
      expect(enText).toBeTruthy();
    }
  });

  it('should have navigation labels in both locales', () => {
    const navKeys: TranslationKey[] = [
      'nav.home',
      'nav.scan',
      'nav.search',
      'nav.files',
      'nav.folders',
      'nav.user',
      'nav.help',
    ];

    for (const key of navKeys) {
      expect(ALL_KEYS, `Missing nav key: ${key}`).toContain(key);
      const itText = tLocale('it', key);
      const enText = tLocale('en', key);
      expect(itText).toBeTruthy();
      expect(enText).toBeTruthy();
    }
  });
});
