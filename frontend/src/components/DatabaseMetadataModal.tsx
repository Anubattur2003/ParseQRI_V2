import React, { useState, useEffect } from 'react'
import { X, Database, Table, Columns, Eye, Info } from 'lucide-react'

interface Column {
  column_name: string
  data_type: string
  is_nullable: string
  column_default: string | null
}

interface Table {
  table_name: string
  column_count: number
  columns: Column[]
  foreign_keys?: any[]
}

interface DatabaseMetadataModalProps {
  isOpen: boolean
  onClose: () => void
  database: {
    id: number
    name: string
    type: string
    server_name?: string
    database_name?: string
  }
}

const DatabaseMetadataModal: React.FC<DatabaseMetadataModalProps> = ({ isOpen, onClose, database }) => {
  const [tables, setTables] = useState<Table[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedTable, setSelectedTable] = useState<Table | null>(null)

  useEffect(() => {
    if (isOpen && database) {
      loadDatabaseMetadata()
    }
  }, [isOpen, database])

  const loadDatabaseMetadata = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const token = localStorage.getItem('token')
      
      // Load database metadata using the database agent
      const response = await fetch(`/db/metadata/${database.id}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      
      if (response.ok) {
        const metadata = await response.json()
        console.log('Loaded database metadata:', metadata)
        
        if (metadata.status === 'success' && metadata.tables) {
          // Transform the metadata to table format
          const tableData: Table[] = metadata.tables.map((table: any) => ({
            table_name: table.table_name,
            column_count: table.column_count || table.columns?.length || 0,
            columns: table.columns || [],
            foreign_keys: table.foreign_keys || []
          }))
          
          setTables(tableData)
        } else {
          setError(metadata.message || 'Failed to load database metadata')
        }
      } else {
        // Mock data for demonstration
        const mockTables: Table[] = [
          {
            table_name: 'Equipment',
            column_count: 8,
            columns: [
              { column_name: 'EquipmentID', data_type: 'int', is_nullable: 'NO', column_default: null },
              { column_name: 'SerialNumber', data_type: 'varchar', is_nullable: 'NO', column_default: null },
              { column_name: 'EquipmentName', data_type: 'varchar', is_nullable: 'YES', column_default: null },
              { column_name: 'ModelNumber', data_type: 'varchar', is_nullable: 'YES', column_default: null },
              { column_name: 'ManufacturerID', data_type: 'int', is_nullable: 'YES', column_default: null },
              { column_name: 'InstallationDate', data_type: 'date', is_nullable: 'YES', column_default: null },
              { column_name: 'Status', data_type: 'varchar', is_nullable: 'YES', column_default: "'Active'" },
              { column_name: 'LastMaintenanceDate', data_type: 'date', is_nullable: 'YES', column_default: null }
            ]
          },
          {
            table_name: 'Defects',
            column_count: 6,
            columns: [
              { column_name: 'DefectID', data_type: 'int', is_nullable: 'NO', column_default: null },
              { column_name: 'EquipmentID', data_type: 'int', is_nullable: 'NO', column_default: null },
              { column_name: 'DefectDescription', data_type: 'text', is_nullable: 'YES', column_default: null },
              { column_name: 'Severity', data_type: 'varchar', is_nullable: 'YES', column_default: null },
              { column_name: 'DateReported', data_type: 'datetime', is_nullable: 'YES', column_default: null },
              { column_name: 'Status', data_type: 'varchar', is_nullable: 'YES', column_default: "'Open'" }
            ]
          },
          {
            table_name: 'Maintenance',
            column_count: 7,
            columns: [
              { column_name: 'MaintenanceID', data_type: 'int', is_nullable: 'NO', column_default: null },
              { column_name: 'EquipmentID', data_type: 'int', is_nullable: 'NO', column_default: null },
              { column_name: 'MaintenanceType', data_type: 'varchar', is_nullable: 'YES', column_default: null },
              { column_name: 'ScheduledDate', data_type: 'date', is_nullable: 'YES', column_default: null },
              { column_name: 'CompletedDate', data_type: 'date', is_nullable: 'YES', column_default: null },
              { column_name: 'TechnicianID', data_type: 'int', is_nullable: 'YES', column_default: null },
              { column_name: 'Notes', data_type: 'text', is_nullable: 'YES', column_default: null }
            ]
          }
        ]
        
        setTables(mockTables)
      }
    } catch (err: any) {
      console.error('Error loading database metadata:', err)
      setError('Failed to load database metadata')
    } finally {
      setLoading(false)
    }
  }

  const getDataTypeColor = (dataType: string) => {
    if (dataType.includes('int') || dataType.includes('bigint')) return 'text-blue-600 bg-blue-50'
    if (dataType.includes('varchar') || dataType.includes('text')) return 'text-green-600 bg-green-50'
    if (dataType.includes('date') || dataType.includes('time')) return 'text-purple-600 bg-purple-50'
    if (dataType.includes('decimal') || dataType.includes('float')) return 'text-orange-600 bg-orange-50'
    return 'text-gray-600 bg-gray-50'
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <Database className="w-6 h-6 text-blue-600" />
            <div>
              <h2 className="text-2xl font-bold text-gray-900">{database.name}</h2>
              <p className="text-sm text-gray-500">
                {database.server_name ? `${database.server_name} - ${database.database_name}` : database.type}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex h-[calc(90vh-120px)]">
          {/* Tables List */}
          <div className="w-1/3 border-r border-gray-200 overflow-y-auto">
            <div className="p-4 border-b border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center">
                <Table className="w-5 h-5 mr-2" />
                Tables ({tables.length})
              </h3>
            </div>
            
            {loading ? (
              <div className="p-4 text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                <p className="text-sm text-gray-500 mt-2">Loading tables...</p>
              </div>
            ) : error ? (
              <div className="p-4 text-center text-red-600">
                <Info className="w-8 h-8 mx-auto mb-2" />
                <p className="text-sm">{error}</p>
              </div>
            ) : (
              <div className="p-2">
                {tables.map((table, index) => (
                  <div
                    key={index}
                    className={`p-3 rounded-lg cursor-pointer transition-colors mb-2 ${
                      selectedTable === table 
                        ? 'bg-blue-50 border-2 border-blue-200' 
                        : 'hover:bg-gray-50 border-2 border-transparent'
                    }`}
                    onClick={() => setSelectedTable(table)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center">
                        <Table className="w-4 h-4 text-gray-500 mr-2" />
                        <span className="font-medium text-gray-900">{table.table_name}</span>
                      </div>
                      <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                        {table.column_count} cols
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Table Details */}
          <div className="w-2/3 overflow-y-auto">
            {selectedTable ? (
              <div className="p-6">
                <div className="mb-6">
                  <h3 className="text-xl font-bold text-gray-900 flex items-center">
                    <Columns className="w-5 h-5 mr-2" />
                    {selectedTable.table_name} Columns
                  </h3>
                  <p className="text-sm text-gray-500 mt-1">
                    {selectedTable.column_count} columns in this table
                  </p>
                </div>

                {/* Columns Table */}
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Column Name
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Data Type
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Nullable
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Default
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {selectedTable.columns.map((column, index) => (
                        <tr key={index} className="hover:bg-gray-50">
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="font-medium text-gray-900">{column.column_name}</span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getDataTypeColor(column.data_type)}`}>
                              {column.data_type}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                              column.is_nullable === 'YES' 
                                ? 'text-yellow-600 bg-yellow-50' 
                                : 'text-red-600 bg-red-50'
                            }`}>
                              {column.is_nullable === 'YES' ? 'Nullable' : 'Not Null'}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                            {column.column_default || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Foreign Keys */}
                {selectedTable.foreign_keys && selectedTable.foreign_keys.length > 0 && (
                  <div className="mt-8">
                    <h4 className="text-lg font-semibold text-gray-900 mb-4">Foreign Key Relationships</h4>
                    <div className="space-y-2">
                      {selectedTable.foreign_keys.map((fk: any, index: number) => (
                        <div key={index} className="bg-blue-50 p-3 rounded-lg">
                          <span className="text-sm text-blue-800">
                            {fk.column} → {fk.referenced_table}.{fk.referenced_column}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                <div className="text-center">
                  <Eye className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                  <p className="text-lg">Select a table to view its columns</p>
                  <p className="text-sm">Click on any table from the list to see detailed column information</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default DatabaseMetadataModal
