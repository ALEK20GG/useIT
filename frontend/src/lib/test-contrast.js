/**
 * Simple contrast ratio checker for WCAG AA compliance
 * This is a basic implementation for testing purposes
 */

// Convert hex to RGB
function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16)
    } : null;
}

// Calculate relative luminance
function getLuminance(r, g, b) {
    const [rs, gs, bs] = [r, g, b].map(c => {
        c = c / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

// Calculate contrast ratio
function getContrastRatio(color1, color2) {
    const rgb1 = hexToRgb(color1);
    const rgb2 = hexToRgb(color2);
    
    if (!rgb1 || !rgb2) return null;
    
    const lum1 = getLuminance(rgb1.r, rgb1.g, rgb1.b);
    const lum2 = getLuminance(rgb2.r, rgb2.g, rgb2.b);
    
    const brightest = Math.max(lum1, lum2);
    const darkest = Math.min(lum1, lum2);
    
    return (brightest + 0.05) / (darkest + 0.05);
}

// Test color combinations
const lightModeColors = {
    bg: '#ffffff',
    text: '#0f172a',
    textMuted: '#475569',
    primary: '#2563eb',
    secondary: '#64748b',
    success: '#047857',
    warning: '#b45309',
    error: '#dc2626'
};

const darkModeColors = {
    bg: '#0f172a',
    text: '#f8fafc',
    textMuted: '#cbd5e1',
    primary: '#3b82f6',
    secondary: '#94a3b8',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444'
};

function testColorSystem() {
    console.log('=== WCAG AA Contrast Testing ===\n');
    
    // Test light mode
    console.log('Light Mode:');
    console.log(`Text on Background: ${getContrastRatio(lightModeColors.text, lightModeColors.bg).toFixed(2)}:1 ${getContrastRatio(lightModeColors.text, lightModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Muted Text on Background: ${getContrastRatio(lightModeColors.textMuted, lightModeColors.bg).toFixed(2)}:1 ${getContrastRatio(lightModeColors.textMuted, lightModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Primary on Background: ${getContrastRatio(lightModeColors.primary, lightModeColors.bg).toFixed(2)}:1 ${getContrastRatio(lightModeColors.primary, lightModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`White on Primary: ${getContrastRatio('#ffffff', lightModeColors.primary).toFixed(2)}:1 ${getContrastRatio('#ffffff', lightModeColors.primary) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Success on Background: ${getContrastRatio(lightModeColors.success, lightModeColors.bg).toFixed(2)}:1 ${getContrastRatio(lightModeColors.success, lightModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Warning on Background: ${getContrastRatio(lightModeColors.warning, lightModeColors.bg).toFixed(2)}:1 ${getContrastRatio(lightModeColors.warning, lightModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Error on Background: ${getContrastRatio(lightModeColors.error, lightModeColors.bg).toFixed(2)}:1 ${getContrastRatio(lightModeColors.error, lightModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    
    console.log('\nDark Mode:');
    console.log(`Text on Background: ${getContrastRatio(darkModeColors.text, darkModeColors.bg).toFixed(2)}:1 ${getContrastRatio(darkModeColors.text, darkModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Muted Text on Background: ${getContrastRatio(darkModeColors.textMuted, darkModeColors.bg).toFixed(2)}:1 ${getContrastRatio(darkModeColors.textMuted, darkModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Primary on Background: ${getContrastRatio(darkModeColors.primary, darkModeColors.bg).toFixed(2)}:1 ${getContrastRatio(darkModeColors.primary, darkModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Black on Primary: ${getContrastRatio('#000000', darkModeColors.primary).toFixed(2)}:1 ${getContrastRatio('#000000', darkModeColors.primary) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Success on Background: ${getContrastRatio(darkModeColors.success, darkModeColors.bg).toFixed(2)}:1 ${getContrastRatio(darkModeColors.success, darkModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Warning on Background: ${getContrastRatio(darkModeColors.warning, darkModeColors.bg).toFixed(2)}:1 ${getContrastRatio(darkModeColors.warning, darkModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Error on Background: ${getContrastRatio(darkModeColors.error, darkModeColors.bg).toFixed(2)}:1 ${getContrastRatio(darkModeColors.error, darkModeColors.bg) >= 4.5 ? '✅ PASS' : '❌ FAIL'}`);
    
    console.log('\n=== Test Complete ===');
}

// Run tests if in Node.js environment
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { testColorSystem, getContrastRatio };
    testColorSystem();
}

// Run tests if in browser environment
if (typeof window !== 'undefined') {
    window.testColorSystem = testColorSystem;
    window.getContrastRatio = getContrastRatio;
}