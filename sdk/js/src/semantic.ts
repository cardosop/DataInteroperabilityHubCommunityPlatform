import { DataHubClient } from './client';

export class SemanticAPI {
  private client: DataHubClient;

  constructor(client: DataHubClient) {
    this.client = client;
  }

  async sparqlQuery(query: string, accept?: string): Promise<any> {
    return this.client.post('semantic/sparql/', { query }, {
      headers: accept ? { Accept: accept } : undefined,
    });
  }

  async sparqlConstruct(query: string, accept?: string): Promise<any> {
    return this.client.post('semantic/sparql/', { query, type: 'construct' }, {
      headers: accept ? { Accept: accept } : undefined,
    });
  }

  async rdfIngest(data: any, contentType?: string): Promise<any> {
    return this.client.post('semantic/rdf/ingest/', data, {
      headers: contentType ? { 'Content-Type': contentType } : undefined,
    });
  }

  async getOntology(): Promise<any> {
    return this.client.get('semantic/ontology/');
  }

  async getVoid(): Promise<any> {
    return this.client.get('semantic/void/');
  }

  async shaclValidate(data: any, shapes?: any): Promise<any> {
    return this.client.post('semantic/shacl/validate/', { data, shapes });
  }

  async resolveResource(uri: string): Promise<any> {
    return this.client.get('semantic/id/', { params: { uri } });
  }
}
