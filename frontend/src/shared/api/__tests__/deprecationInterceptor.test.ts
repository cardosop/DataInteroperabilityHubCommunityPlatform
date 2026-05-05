/**
 * Phase 250.3.B.6 TDD pin for the RFC-8594 deprecation-header
 * response interceptor. Verifies the wire contract used by the
 * Asset visibility deprecation rollout (D250.4):
 *
 * * Non-deprecated responses produce no toast (zero-cost path).
 * * ``Deprecation: true`` responses produce one toast per
 *   (path-prefix, sunset-date) pair — subsequent hits are de-duped.
 * * Toast severity escalates as the sunset date approaches.
 * * Non-admin sessions see no toast (the deprecation surface is
 *   operator-targeted).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  configureDeprecationInterceptor,
  inspectResponse,
  resetDeprecationInterceptor,
} from '../deprecationInterceptor';

function makeToast() {
  return {
    info: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  };
}

describe('deprecationInterceptor', () => {
  let toast: ReturnType<typeof makeToast>;

  beforeEach(() => {
    toast = makeToast();
    configureDeprecationInterceptor({
      toast,
      isAdminSession: () => true,
    });
  });

  afterEach(() => {
    resetDeprecationInterceptor();
  });

  it('does nothing when no Deprecation header is present', () => {
    inspectResponse('/api/v1/assets/', {});
    expect(toast.info).not.toHaveBeenCalled();
    expect(toast.warning).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('does nothing when Deprecation header is "false"', () => {
    inspectResponse('/api/v1/assets/', { Deprecation: 'false' });
    expect(toast.warning).not.toHaveBeenCalled();
  });

  it('does nothing for non-admin sessions even when deprecated', () => {
    configureDeprecationInterceptor({
      toast,
      isAdminSession: () => false,
    });
    inspectResponse('/api/v1/assets/', {
      Deprecation: 'true',
      Sunset: 'Wed, 21 Oct 2026 07:28:00 GMT',
    });
    expect(toast.warning).not.toHaveBeenCalled();
    expect(toast.info).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('emits an info toast when sunset is more than 30 days out', () => {
    const sunset = new Date(Date.now() + 60 * 24 * 60 * 60 * 1000);
    inspectResponse('/api/v1/assets/', {
      Deprecation: 'true',
      Sunset: sunset.toUTCString(),
    });
    expect(toast.info).toHaveBeenCalledTimes(1);
    expect(toast.info.mock.calls[0][0]).toContain('/api/v1/assets');
  });

  it('emits a warning toast when sunset is between 7 and 30 days out', () => {
    const sunset = new Date(Date.now() + 14 * 24 * 60 * 60 * 1000);
    inspectResponse('/api/v1/assets/', {
      Deprecation: 'true',
      Sunset: sunset.toUTCString(),
    });
    expect(toast.warning).toHaveBeenCalledTimes(1);
  });

  it('emits an error toast when sunset is less than 7 days out', () => {
    const sunset = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000);
    inspectResponse('/api/v1/assets/', {
      Deprecation: 'true',
      Sunset: sunset.toUTCString(),
    });
    expect(toast.error).toHaveBeenCalledTimes(1);
  });

  it('de-dupes the same (path-prefix, sunset) pair', () => {
    const sunset = new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toUTCString();
    inspectResponse('/api/v1/assets/', {
      Deprecation: 'true',
      Sunset: sunset,
    });
    inspectResponse(
      '/api/v1/assets/123e4567-e89b-12d3-a456-426614174000/',
      {
        Deprecation: 'true',
        Sunset: sunset,
      },
    );
    inspectResponse('/api/v1/assets/?status=PUBLIC', {
      Deprecation: 'true',
      Sunset: sunset,
    });
    // All three URLs normalise to the same prefix.
    expect(toast.warning).toHaveBeenCalledTimes(1);
  });

  it('re-fires when the sunset date changes (operator extended window)', () => {
    const first = new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toUTCString();
    const second = new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toUTCString();
    inspectResponse('/api/v1/assets/', {
      Deprecation: 'true',
      Sunset: first,
    });
    inspectResponse('/api/v1/assets/', {
      Deprecation: 'true',
      Sunset: second,
    });
    expect(toast.warning).toHaveBeenCalledTimes(1);
    expect(toast.info).toHaveBeenCalledTimes(1);
  });

  it('parses and displays the deprecation Link doc URL', () => {
    inspectResponse('/api/v1/assets/', {
      Deprecation: 'true',
      Sunset: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toUTCString(),
      Link: '</docs/api/migrations/visibility-deprecation.md>; rel="deprecation"; type="text/markdown"',
    });
    expect(toast.warning).toHaveBeenCalledTimes(1);
    expect(toast.warning.mock.calls[0][0]).toContain(
      '/docs/api/migrations/visibility-deprecation.md',
    );
  });
});
