import { DataHubClient } from './client';

export class BillingAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async getSubscription(): Promise<any> {
    return this.client.get('billing/subscription/current/');
  }

  async listInvoices(params?: any): Promise<any> {
    return this.client.get('billing/invoices/', { params });
  }

  async getInvoice(id: string): Promise<any> {
    return this.client.get(`billing/invoices/${id}/`);
  }

  async listPlans(params?: any): Promise<any> {
    return this.client.get('billing/plans/', { params });
  }

  async getPlan(id: string): Promise<any> {
    return this.client.get(`billing/plans/${id}/`);
  }

  async changePlan(planSlug: string): Promise<any> {
    return this.client.post('billing/subscription/current/change-plan/', { plan_slug: planSlug });
  }

  async getMlSubscription(): Promise<any> {
    return this.client.get('billing/subscription/ml/current/');
  }

  async changeMlPlan(planSlug: string): Promise<any> {
    return this.client.post('billing/subscription/ml/current/change-plan/', { plan_slug: planSlug });
  }

  async getPlanLimits(): Promise<any> {
    const data = await this.client.get('billing/subscription/current/');
    return data?.limits ?? {};
  }

  async getUsage(params?: any): Promise<any> {
    return this.client.get('billing/usage/', { params });
  }

  async processRefund(paymentIntentId: string, amountCents: number, reason: string): Promise<any> {
    return this.client.post('billing/refunds/', { payment_intent_id: paymentIntentId, amount_cents: amountCents, reason });
  }

  async triggerReconciliation(dryRun?: boolean): Promise<any> {
    return this.client.post('billing/admin/reconcile/', { dry_run: dryRun });
  }
}
