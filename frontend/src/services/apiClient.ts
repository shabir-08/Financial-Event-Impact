import { request } from './http';

/**
 * Small backend utilities used outside the event and simulator pages.
 * The former demo-fallback getters were removed: live pages use services/eventsApi.ts and
 * services/blackSwanApi.ts (which throw on failure), demo pages read demo constants directly.
 */
class ApiClient {
  private backendAvailable: boolean | null = null;

  async checkHealth(): Promise<boolean> {
    try {
      await request('/api/health', undefined, 3000);
      this.backendAvailable = true;
    } catch {
      this.backendAvailable = false;
    }
    return this.backendAvailable;
  }

  get isBackendConnected(): boolean {
    return this.backendAvailable === true;
  }

  /** The backend has no account service; nothing can be verified or reset. */
  async resetUserCredentials(_currentPassword: string): Promise<{ success: boolean; message: string }> {
    return { success: false, message: 'Account service not available (demo login). Nothing was verified or reset.' };
  }
}

export const apiClient = new ApiClient();
