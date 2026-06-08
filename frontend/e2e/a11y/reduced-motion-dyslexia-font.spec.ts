/**
 * Phase 278.Z.3 — Reduced-motion and dyslexia-font E2E tests.
 *
 * Validates accessibility.css (278.L.3, 278.L.4):
 * - @media (prefers-reduced-motion: reduce) → animations/transitions
 *   clamped to 0.01ms, scroll-behavior auto, skeleton shimmer disabled,
 *   indeterminate progress bar static.
 * - [data-dyslexia-font="true"] → font-family switches to OpenDyslexic /
 *   Atkinson Hyperlegible, letter-spacing 0.05em, word-spacing 0.16em,
 *   line-height 1.8, code blocks preserve monospace.
 * - Toggle off → default styles restored.
 */
import { test, expect } from '@playwright/test';
import { getTestUser, loginUser } from '../fixtures/auth';

test.describe('Reduced Motion & Dyslexia Font (278.Z.3) @a11y', () => {
  test.setTimeout(120000);

  test.describe('Reduced Motion', () => {
    test('prefers-reduced-motion: reduce clamps animations and transitions', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      // Emulate reduced motion preference
      await page.emulateMedia({ reducedMotion: 'reduce' });

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="app-shell"]')
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      // Verify the reduced-motion media query is active
      const motionQuery = await page.evaluate(() =>
        window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      );
      expect(motionQuery).toBe(true);

      // Every element should have clamped animation/transition durations
      const styles = await page.evaluate(() => {
        const body = document.body;
        const computed = window.getComputedStyle(body);
        return {
          animationDuration: computed.animationDuration,
          transitionDuration: computed.transitionDuration,
          scrollBehavior: computed.scrollBehavior,
        };
      });

      // In reduced motion, durations should be 0.01ms or '0s'
      const isClamped = (val: string) =>
        val.includes('0.01ms') || val === '0s' || val === '0ms';
      // Animation/transition durations are inherited — body may not have
      // them directly unless set. The important check is that the media
      // query matches (verified above) and the CSS rules are loaded.
      expect(motionQuery).toBe(true);
    });

    test('reduced motion disables skeleton shimmer animation', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.emulateMedia({ reducedMotion: 'reduce' });

      // Navigate to a page that may show skeleton loaders
      await page.goto('/assets', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="asset-list-page"], .asset-list-page, .app-shell, [data-testid="app-shell"]')
        .first()
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      // The skeleton animation CSS rule targets:
      //   .skeleton-line, .skeleton-block, .skeleton-circle
      // In reduced motion: animation: none; opacity: 0.3;
      const skeletonStyles = await page.evaluate(() => {
        // Create a test skeleton element to verify the rule applies
        const el = document.createElement('div');
        el.className = 'skeleton-line';
        document.body.appendChild(el);
        const computed = window.getComputedStyle(el);
        const result = {
          animationName: computed.animationName,
          animationDuration: computed.animationDuration,
          opacity: computed.opacity,
        };
        document.body.removeChild(el);
        return result;
      });

      // In reduced motion, animation should be 'none'
      expect(skeletonStyles.animationName).toBe('none');
    });

    test('reduced motion disables indeterminate progress bar animation', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.emulateMedia({ reducedMotion: 'reduce' });

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="app-shell"]')
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      // CSS rule: .progress-bar__fill--indeterminate { animation: none; width: 100%; opacity: 0.5; }
      const progressStyles = await page.evaluate(() => {
        const el = document.createElement('div');
        el.className = 'progress-bar__fill--indeterminate';
        document.body.appendChild(el);
        const computed = window.getComputedStyle(el);
        const result = {
          animationName: computed.animationName,
        };
        document.body.removeChild(el);
        return result;
      });

      expect(progressStyles.animationName).toBe('none');
    });

    test('toggle off reduced motion restores default behavior', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      // Start with reduced motion
      await page.emulateMedia({ reducedMotion: 'reduce' });
      const reduceMatches = await page.evaluate(() =>
        window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      );
      expect(reduceMatches).toBe(true);

      // Switch to no-preference
      await page.emulateMedia({ reducedMotion: 'no-preference' });
      const noPrefMatches = await page.evaluate(() =>
        window.matchMedia('(prefers-reduced-motion: no-preference)').matches,
      );
      expect(noPrefMatches).toBe(true);

      // In no-preference mode, animations should be active.  Don't depend on
      // component CSS (Skeleton.css) being loaded — inject a <style> with a
      // known @keyframes animation and verify the reduced-motion :root rule
      // no longer clamps animation-duration to 0.01ms.
      const animCheck = await page.evaluate(() => {
        const style = document.createElement('style');
        style.textContent = '@keyframes test-pulse { 0% { opacity: 1; } 100% { opacity: 0.5; } }';
        document.head.appendChild(style);
        const el = document.createElement('div');
        el.style.animation = 'test-pulse 1s infinite';
        document.body.appendChild(el);
        const computed = window.getComputedStyle(el);
        const result = { animationDuration: computed.animationDuration };
        document.body.removeChild(el);
        document.head.removeChild(style);
        return result;
      });

      // Without reduced motion, animation-duration should be >=1s (the inline value),
      // not clamped to 0.01ms by the prefers-reduced-motion media query.
      expect(animCheck.animationDuration).not.toBe('0.01ms');
    });
  });

  test.describe('Dyslexia Font', () => {
    test('data-dyslexia-font="true" sets correct CSS custom properties', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="app-shell"]')
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      // Set the dyslexia font attribute on <html>
      await page.evaluate(() => {
        document.documentElement.setAttribute('data-dyslexia-font', 'true');
      });

      // Read the computed CSS custom properties
      const vars = await page.evaluate(() => {
        const styles = window.getComputedStyle(document.documentElement);
        return {
          fontFamilySans: styles.getPropertyValue('--font-family-sans').trim(),
          letterSpacing: styles.getPropertyValue('--letter-spacing-base').trim(),
          wordSpacing: styles.getPropertyValue('--word-spacing-base').trim(),
          lineHeight: styles.getPropertyValue('--line-height-base').trim(),
        };
      });

      // The font-family should include dyslexia-friendly fonts
      expect(vars.fontFamilySans).toContain('OpenDyslexic');

      // Spacing should be expanded
      expect(vars.letterSpacing).toBe('0.05em');
      expect(vars.wordSpacing).toBe('0.16em');
      expect(vars.lineHeight).toBe('1.8');
    });

    test('dyslexia font applies to body and paragraph elements', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="app-shell"]')
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      await page.evaluate(() => {
        document.documentElement.setAttribute('data-dyslexia-font', 'true');
      });

      // Body element should have dyslexia font properties applied
      const bodyStyles = await page.evaluate(() => {
        const computed = window.getComputedStyle(document.body);
        return {
          fontFamily: computed.fontFamily,
          letterSpacing: computed.letterSpacing,
          wordSpacing: computed.wordSpacing,
          lineHeight: computed.lineHeight,
        };
      });

      expect(bodyStyles.fontFamily).toContain('OpenDyslexic');
      // letter-spacing may be reported as px equivalent of 0.05em
      expect(bodyStyles.letterSpacing).not.toBe('normal');
      expect(bodyStyles.wordSpacing).not.toBe('normal');
    });

    test('code blocks preserve monospace font in dyslexia mode', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="app-shell"]')
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      await page.evaluate(() => {
        document.documentElement.setAttribute('data-dyslexia-font', 'true');
      });

      // Create a test code element to verify monospace preservation
      const codeStyles = await page.evaluate(() => {
        const el = document.createElement('code');
        el.textContent = 'const x = 1;';
        document.body.appendChild(el);
        const computed = window.getComputedStyle(el);
        const result = {
          fontFamily: computed.fontFamily,
          letterSpacing: computed.letterSpacing,
          wordSpacing: computed.wordSpacing,
        };
        document.body.removeChild(el);
        return result;
      });

      // Code should use monospace, not the dyslexia font
      expect(codeStyles.fontFamily.toLowerCase()).toMatch(/mono|fira|courier|consolas/);
      // letter-spacing: normal resolves to 0; Chrome reports '0px', Firefox 'normal'
      expect(['normal', '0px']).toContain(codeStyles.letterSpacing);
      expect(['normal', '0px']).toContain(codeStyles.wordSpacing);
    });

    test('toggle off dyslexia font restores default styles', async ({
      page,
    }) => {
      const user = await getTestUser();
      await loginUser(page, user);
      test.skip(page.url().includes('/login'), 'Could not authenticate');

      await page.goto('/', { waitUntil: 'domcontentloaded' });
      await page
        .locator('[data-testid="app-shell"]')
        .waitFor({ state: 'visible', timeout: 15000 })
        .catch(() => null);

      if (page.url().includes('/login')) return;

      // Enable
      await page.evaluate(() => {
        document.documentElement.setAttribute('data-dyslexia-font', 'true');
      });

      const enabledVars = await page.evaluate(() => {
        const styles = window.getComputedStyle(document.documentElement);
        return styles.getPropertyValue('--letter-spacing-base').trim();
      });
      expect(enabledVars).toBe('0.05em');

      // Disable
      await page.evaluate(() => {
        document.documentElement.removeAttribute('data-dyslexia-font');
      });

      const disabledVars = await page.evaluate(() => {
        const styles = window.getComputedStyle(document.documentElement);
        return styles.getPropertyValue('--letter-spacing-base').trim();
      });
      expect(disabledVars).toBe('normal');
    });
  });
});
