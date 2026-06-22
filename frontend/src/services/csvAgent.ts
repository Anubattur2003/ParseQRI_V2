import apiClient from './api';

export interface CsvQueryRequest {
  query: string;
  table_name?: string;
  visualization?: boolean;
  database_id?: number | null;
}

export interface CsvQueryResponse {
  answer: string;
  sql_query?: string;
  data: any[];
  chart_type: 'bar' | 'line' | 'pie';
  visualization_data?: any;
  table_name?: string;
}

export interface CsvTable {
  name: string;
  full_name: string;
  source: string;
  column_count?: number;
}

export interface ColumnSchema {
  name: string;
  type: string;
  nullable: boolean;
}

export interface TableSchema {
  table_name: string;
  columns: ColumnSchema[];
}

export const csvAgentService = {
  /**
   * Process a natural language query against CSV data
   */
  processQuery: async (
    query: string, 
    tableName?: string, 
    visualization: boolean = false,
    databaseId?: number | null
  ): Promise<CsvQueryResponse> => {
    try {
      const response = await apiClient.post<CsvQueryResponse>('/csv/query', {
        query,
        table_name: tableName,
        visualization,
        database_id: databaseId
      });
      return response.data;
    } catch (error: any) {
      console.error('Error processing CSV query:', error);
      throw error;
    }
  },

  /**
   * Execute raw SQL query
   */
  executeSql: async (sqlQuery: string): Promise<CsvQueryResponse> => {
    try {
      const response = await apiClient.post<CsvQueryResponse>('/csv/execute_sql', {
        sql_query: sqlQuery
      });
      return response.data;
    } catch (error: any) {
      console.error('Error executing SQL:', error);
      throw error;
    }
  },

  /**
   * Upload a CSV file
   */
  uploadCsv: async (file: File, dbId?: number): Promise<{ success: boolean; table_name: string; message: string }> => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (dbId) {
        formData.append('db_id', dbId.toString());
      }

      const response = await apiClient.post('/csv/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return response.data;
    } catch (error: any) {
      console.error('Error uploading CSV:', error);
      throw error;
    }
  },

  /**
   * List available tables
   */
  listTables: async (): Promise<CsvTable[]> => {
    try {
      const response = await apiClient.get('/csv/tables');
      return response.data.tables;
    } catch (error: any) {
      console.error('Error listing CSV tables:', error);
      // Return empty list instead of throwing to avoid breaking UI on load
      return [];
    }
  },

  /**
   * Get schema for a specific table
   */
  getTableSchema: async (tableName: string): Promise<TableSchema> => {
    try {
      const response = await apiClient.get(`/csv/schema/${tableName}`);
      return response.data;
    } catch (error: any) {
      console.error(`Error getting schema for ${tableName}:`, error);
      throw error;
    }
  }
};

export default csvAgentService;
