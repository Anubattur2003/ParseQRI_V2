import React, { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from '../components/Sidebar'
import Header from '../components/Header'
import { 
  RiTableLine, 
  RiDatabase2Line, 
  RiSearchLine, 
  RiAddLine, 
  RiSendPlaneFill, 
  RiMore2Fill,
  RiFileExcel2Line,
  RiArrowRightSLine,
  RiArrowDownSLine,
  RiCodeLine,
  RiPlayFill
} from 'react-icons/ri'
import { csvAgentService, CsvTable, TableSchema } from '../services/csvAgent'

const CsvDashboard = () => {
  // State
  const [tables, setTables] = useState<CsvTable[]>([])
  const [selectedTable, setSelectedTable] = useState<string | null>(null)
  const [tableSchema, setTableSchema] = useState<TableSchema | null>(null)
  const [tableData, setTableData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({})
  const [isUploading, setIsUploading] = useState(false)
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Enhanced Chat History State
  interface ChatMessage {
    role: 'user' | 'assistant'
    content: string
    data?: any[]
    schema?: TableSchema
    sql?: string
    timestamp: Date
  }
  
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory])

  // Load tables on mount
  useEffect(() => {
    fetchTables()
  }, [])

  const fetchTables = async () => {
    setIsInitialLoading(true)
    try {
      const data = await csvAgentService.listTables()
      setTables(data)
      
      // If tables exist and none selected, auto-select the first one
      if (data.length > 0 && !selectedTable) {
        handleTableSelect(data[0].name)
      }
    } catch (error) {
      console.error("Failed to fetch tables", error)
    } finally {
      setIsInitialLoading(false)
    }
  }

  const handleTableSelect = async (tableName: string) => {
    if (selectedTable === tableName) return
    setSelectedTable(tableName)
    setLoading(true)
    
    // Fetch schema
    try {
      const schema = await csvAgentService.getTableSchema(tableName)
      setTableSchema(schema)
      
      // Add a system welcome message for this table
      setChatHistory(prev => [
        ...prev, 
        { 
          role: 'assistant', 
          content: `I've loaded table **${tableName}**. What would you like to know about it?`,
          schema: schema,
          timestamp: new Date()
        }
      ])

    } catch (error) {
      console.error("Failed to load table details", error)
    } finally {
      setLoading(false)
    }
  }
  
  const toggleTableExpand = async (tableName: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setExpandedTables(prev => ({
      ...prev,
      [tableName]: !prev[tableName]
    }))
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return
    
    const file = e.target.files[0]
    setIsUploading(true)
    
    try {
      await csvAgentService.uploadCsv(file)
      await fetchTables()
      setChatHistory(prev => [
        ...prev, 
        { 
          role: 'assistant', 
          content: `✅ Successfully uploaded **${file.name}**. You can now select it from the sidebar.`,
          timestamp: new Date()
        }
      ])
    } catch (error) {
      console.error("Upload failed", error)
      setChatHistory(prev => [
        ...prev, 
        { 
          role: 'assistant', 
          content: `❌ Failed to upload ${file.name}. Please try again.`,
          timestamp: new Date()
        }
      ])
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleExecuteSql = async (sql: string) => {
    setLoading(true)
    // Add a system message indicating execution
    setChatHistory(prev => [
      ...prev, 
      { role: 'user', content: `Execute SQL: \n\`\`\`sql\n${sql}\n\`\`\``, timestamp: new Date() }
    ])

    try {
      const response = await csvAgentService.executeSql(sql)
      
      setChatHistory(prev => [
        ...prev, 
        { 
          role: 'assistant', 
          content: "Here are the results of your SQL query:", 
          data: response.data, 
          sql: response.sql_query, 
          timestamp: new Date() 
        }
      ])
    } catch (error: any) {
       console.error("SQL Execution failed", error)
       setChatHistory(prev => [
        ...prev, 
        { 
          role: 'assistant', 
          content: `❌ SQL Execution Failed: ${error.message || error}`,
          timestamp: new Date()
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  const updateMessageSql = (index: number, newSql: string) => {
      setChatHistory(prev => {
          const newHistory = [...prev]
          newHistory[index] = { ...newHistory[index], sql: newSql }
          return newHistory
      })
  }

  const handleQuerySubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    const userQuery = query
    setQuery('')
    
    // Add user message immediately
    setChatHistory(prev => [
      ...prev, 
      { role: 'user', content: userQuery, timestamp: new Date() }
    ])
    
    setLoading(true)

    try {
      const response = await csvAgentService.processQuery(
        userQuery, 
        selectedTable || undefined,
        false
      )

      // Add assistant response with data
      setChatHistory(prev => [
        ...prev, 
        { 
          role: 'assistant', 
          content: response.answer, 
          data: response.data,
          sql: response.sql_query, 
          timestamp: new Date() 
        }
      ])
      
    } catch (error) {
      console.error("Query failed", error)
      setChatHistory(prev => [
        ...prev, 
        { 
          role: 'assistant', 
          content: "Sorry, I encountered an error processing your query.",
          timestamp: new Date()
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  // Formatting helper for markdown-like bold text
  const formatText = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*)/g)
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i}>{part.slice(2, -2)}</strong>
      }
      return part
    })
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-dark-950 font-sans">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        
        <main className="flex-1 flex overflow-hidden">
          {/* Left Sidebar: Data Sources */}
          <div className="w-72 bg-white dark:bg-dark-900 border-r border-gray-200 dark:border-dark-800 flex flex-col shadow-sm z-10">
            <div className="p-5 border-b border-gray-200 dark:border-dark-800 flex justify-between items-center bg-gray-50/50 dark:bg-dark-800/50">
              <h2 className="font-bold text-gray-800 dark:text-gray-100 flex items-center gap-2">
                <RiDatabase2Line className="text-primary-500" />
                Data Sources
              </h2>
              <button 
                onClick={() => fileInputRef.current?.click()}
                className="p-2 rounded-full hover:bg-white dark:hover:bg-dark-700 hover:shadow-sm text-primary-600 dark:text-primary-400 transition-all"
                title="Upload CSV"
              >
                <RiAddLine size={20} />
              </button>
              <input 
                type="file" 
                ref={fileInputRef} 
                onChange={handleFileUpload} 
                accept=".csv" 
                className="hidden" 
              />
            </div>
            
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {isInitialLoading ? (
                <div className="flex flex-col items-center justify-center py-10 space-y-3">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Loading tables...</span>
                </div>
              ) : tables.length === 0 ? (
                <div className="flex flex-col items-center text-center py-12 text-gray-400 dark:text-gray-500">
                  <div className="bg-gray-100 dark:bg-dark-800 p-4 rounded-full mb-4">
                    <RiFileExcel2Line size={32} />
                  </div>
                  <span className="font-medium text-gray-600 dark:text-gray-300">No tables found</span>
                  <span className="text-xs mt-2 max-w-[150px] leading-relaxed">Upload a CSV file to start analyzing your data.</span>
                  <button 
                    onClick={() => fileInputRef.current?.click()}
                    className="mt-6 px-4 py-2 bg-primary-600 text-white text-xs font-bold rounded-lg hover:bg-primary-700 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200"
                  >
                    Upload CSV
                  </button>
                </div>
              ) : (
                tables.map(table => (
                  <div key={table.name} className="group">
                    <div 
                      className={`flex items-center px-4 py-3 rounded-xl cursor-pointer transition-all duration-200 border ${
                        selectedTable === table.name 
                          ? 'bg-primary-50 dark:bg-primary-900/20 border-primary-200 dark:border-primary-800/30 shadow-sm transform scale-[1.02]' 
                          : 'bg-white dark:bg-dark-800 border-transparent hover:border-gray-200 dark:hover:border-dark-700 hover:shadow-md'
                      }`}
                      onClick={() => handleTableSelect(table.name)}
                    >
                      <button 
                        className={`mr-3 p-1 rounded-md transition-colors ${
                            selectedTable === table.name ? 'text-primary-500' : 'text-gray-400 group-hover:bg-gray-100 dark:group-hover:bg-dark-700'
                        }`}
                        onClick={(e) => toggleTableExpand(table.name, e)}
                      >
                        {expandedTables[table.name] ? <RiArrowDownSLine size={16} /> : <RiArrowRightSLine size={16} />}
                      </button>
                      <div className={`p-2 rounded-lg mr-3 ${selectedTable === table.name ? 'bg-primary-100 dark:bg-primary-900/40 text-primary-600' : 'bg-gray-100 dark:bg-dark-700 text-gray-500'}`}>
                         <RiTableLine size={18} />
                      </div>
                      <span className={`truncate flex-1 text-sm font-semibold ${selectedTable === table.name ? 'text-primary-900 dark:text-primary-100' : 'text-gray-700 dark:text-gray-300'}`}>{table.name}</span>
                    </div>
                    
                    {/* Columns list */}
                    <AnimatePresence>
                        {expandedTables[table.name] && selectedTable === table.name && tableSchema && (
                        <motion.div 
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="ml-4 pl-4 border-l-2 border-gray-100 dark:border-dark-700 my-1 space-y-1 overflow-hidden"
                        >
                            {tableSchema.columns.map(col => (
                            <div key={col.name} className="flex items-center text-xs px-2 py-1.5 rounded-md hover:bg-gray-50 dark:hover:bg-dark-800/50 text-gray-500 dark:text-gray-400 transition-colors">
                                <span className={`w-1.5 h-1.5 rounded-full mr-2 ${col.name === 'id' ? 'bg-orange-400' : 'bg-gray-300 dark:bg-gray-600'}`}></span>
                                <span className="truncate font-medium">{col.name}</span>
                                <span className="ml-auto text-gray-400 text-[9px] uppercase tracking-wider bg-gray-100 dark:bg-dark-800 px-1.5 py-0.5 rounded">{col.type}</span>
                            </div>
                            ))}
                        </motion.div>
                        )}
                    </AnimatePresence>
                  </div>
                ))
              )}
            </div>
            
            <div className="p-4 bg-gray-50 dark:bg-dark-800 border-t border-gray-200 dark:border-dark-700 text-xs text-center text-gray-500">
                <p>Select a table to start analyzing</p>
            </div>
          </div>

          {/* Middle: Chat & Data Interface */}
          <div className="flex-1 flex flex-col min-w-0 bg-white/50 dark:bg-dark-950 relative">
             
             {/* Chat History Area */}
             <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-8 scroll-smooth">
                {chatHistory.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center max-w-lg mx-auto p-8 opacity-0 animate-[fadeIn_0.5s_ease-out_forwards]">
                        <div className="w-20 h-20 bg-gradient-to-br from-primary-100 to-indigo-100 dark:from-primary-900/30 dark:to-indigo-900/30 rounded-3xl flex items-center justify-center mb-6 shadow-xl shadow-primary-500/10">
                            <RiSearchLine size={36} className="text-primary-600 dark:text-primary-400" />
                        </div>
                        <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
                            {selectedTable ? `Ask about ${selectedTable}` : 'Welcome to CSV Analyst'}
                        </h1>
                        <p className="text-gray-500 dark:text-gray-400 mb-8 leading-relaxed">
                            {selectedTable 
                                ? "I'm ready to help you analyze this dataset. Ask me questions about trends, summaries, or specific data points." 
                                : "Select a table from the sidebar to verify data or upload a new CSV file to get started."}
                        </p>
                        
                        {!selectedTable && (
                             <div className="flex gap-3">
                                <button 
                                    onClick={() => fileInputRef.current?.click()}
                                    className="px-5 py-2.5 bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-700 hover:border-primary-500 dark:hover:border-primary-500 text-gray-700 dark:text-gray-200 rounded-xl shadow-sm hover:shadow-md transition-all flex items-center gap-2 font-medium"
                                >
                                    <RiAddLine /> Upload CSV
                                </button>
                             </div>
                        )}
                    </div>
                ) : (
                    <>
                        {chatHistory.map((msg, idx) => (
                            <div key={idx} className={`flex flex-col gap-3 ${msg.role === 'user' ? 'items-end' : 'items-start'} max-w-5xl mx-auto w-full animate-[fadeIn_0.3s_ease-out]`}>
                                {/* Header / Role Label */}
                                <div className={`flex items-center gap-2 text-xs font-medium text-gray-400 uppercase tracking-wider px-1`}>
                                    {msg.role === 'user' ? 'You' : 'Analyst'} • {msg.timestamp.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                </div>

                                {/* Message Bubble */}
                                <div className={`rounded-2xl px-6 py-4 shadow-sm border max-w-[90%] md:max-w-[80%] leading-relaxed ${
                                    msg.role === 'user' 
                                        ? 'bg-primary-600 text-white border-primary-500 rounded-tr-sm' 
                                        : 'bg-white dark:bg-dark-800 text-gray-800 dark:text-gray-100 border-gray-100 dark:border-dark-700 rounded-tl-sm'
                                }`}>
                                    {formatText(msg.content)}
                                </div>
                                
                                {/* Attached Data / Schema View */}
                                {msg.role === 'assistant' && (msg.data || msg.schema || msg.sql) && (
                                    <div className="w-full mt-2 pl-2 overflow-hidden">
                                        
                                        {/* SQL Query View / Executor */}
                                        {msg.sql && (
                                            <div className="bg-gray-900 rounded-xl overflow-hidden mb-4 shadow-md font-mono text-sm border border-gray-700 animate-[fadeIn_0.5s_ease-out]">
                                                <div className="bg-gray-800 px-4 py-2 flex items-center justify-between border-b border-gray-700">
                                                    <span className="text-gray-400 text-xs font-bold uppercase flex items-center gap-2">
                                                        <RiCodeLine className="text-blue-400" /> SQL Editor
                                                    </span>
                                                     <button 
                                                        onClick={() => handleExecuteSql(msg.sql!)} 
                                                        className="flex items-center gap-1 text-[10px] bg-green-600 hover:bg-green-700 text-white px-3 py-1.5 rounded transition-all uppercase font-bold tracking-wider hover:shadow-lg active:scale-95"
                                                    >
                                                        <RiPlayFill size={14} /> Run Query
                                                    </button>
                                                </div>
                                                <div className="p-0">
                                                    <textarea 
                                                        value={msg.sql}
                                                        onChange={(e) => updateMessageSql(idx, e.target.value)}
                                                        className="w-full h-auto min-h-[80px] bg-gray-900 text-green-400 p-4 outline-none border-none resize-y text-xs font-mono leading-relaxed focus:bg-gray-900/50 transition-colors"
                                                        spellCheck={false}
                                                    />
                                                </div>
                                            </div>
                                        )}

                                        {/* Schema View */}
                                        {msg.schema && (
                                            <div className="bg-white dark:bg-dark-900/50 rounded-xl border border-gray-200 dark:border-dark-700 overflow-hidden mb-4 shadow-sm">
                                                <div className="bg-gray-50 dark:bg-dark-800/50 px-4 py-2 border-b border-gray-200 dark:border-dark-700 flex items-center gap-2">
                                                    <RiTableLine className="text-gray-500" />
                                                    <span className="text-xs font-bold text-gray-500 uppercase">Table Schema</span>
                                                </div>
                                                <div className="overflow-x-auto">
                                                    <table className="min-w-full divide-y divide-gray-100 dark:divide-dark-800">
                                                        <thead className="bg-gray-50/50 dark:bg-dark-800/20">
                                                            <tr>
                                                                {['Column', 'Type', 'Nullable'].map(h => (
                                                                    <th key={h} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{h}</th>
                                                                ))}
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y divide-gray-100 dark:divide-dark-800/50">
                                                            {msg.schema.columns.map((col, i) => (
                                                                <tr key={i} className="hover:bg-gray-50 dark:hover:bg-dark-800/30">
                                                                    <td className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 font-medium">{col.name}</td>
                                                                    <td className="px-4 py-2 text-xs text-gray-500 font-mono">{col.type}</td>
                                                                    <td className="px-4 py-2 text-xs text-gray-500">{col.nullable ? 'Yes' : 'No'}</td>
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        )}

                                        {/* Data Table View */}
                                        {msg.data && msg.data.length > 0 && (
                                            <div className="bg-white dark:bg-dark-900 rounded-xl border border-gray-200 dark:border-dark-700 shadow-sm overflow-hidden animate-[fadeIn_0.5s_ease-out]">
                                                <div className="bg-gray-50 dark:bg-dark-800/50 px-4 py-2 border-b border-gray-200 dark:border-dark-700 flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <RiDatabase2Line className="text-primary-500" />
                                                        <span className="text-xs font-bold text-gray-700 dark:text-gray-300 uppercase">Result Data</span>
                                                    </div>
                                                    <span className="text-xs text-gray-400">{msg.data.length} rows</span>
                                                </div>
                                                <div className="overflow-x-auto max-h-[400px]">
                                                    <table className="min-w-full divide-y divide-gray-200 dark:divide-dark-700">
                                                        <thead className="bg-gray-50 dark:bg-dark-800 sticky top-0 z-10">
                                                            <tr>
                                                                {Object.keys(msg.data[0]).map(key => (
                                                                    <th key={key} className="px-4 py-3 text-left text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider whitespace-nowrap bg-gray-50 dark:bg-dark-800 shadow-sm">
                                                                        {key}
                                                                    </th>
                                                                ))}
                                                            </tr>
                                                        </thead>
                                                        <tbody className="bg-white dark:bg-dark-900 divide-y divide-gray-100 dark:divide-dark-700/50">
                                                            {msg.data.map((row, rI) => (
                                                                <tr key={rI} className="hover:bg-blue-50/50 dark:hover:bg-blue-900/10 transition-colors">
                                                                    {Object.values(row).map((val: any, cI) => (
                                                                        <td key={cI} className="px-4 py-3 whitespace-nowrap text-sm text-gray-700 dark:text-gray-300 border-r border-transparent last:border-0 hover:border-gray-100 dark:hover:border-dark-700">
                                                                            {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                                                                        </td>
                                                                    ))}
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                        
                        {/* Loading Indicator */}
                        {loading && (
                            <div className="flex flex-col gap-3 items-start max-w-5xl mx-auto w-full animate-[fadeIn_0.3s_ease-out]">
                                <div className="flex items-center gap-2 text-xs font-medium text-gray-400 uppercase tracking-wider px-1">
                                    Analyst • Thinking
                                </div>
                                <div className="bg-white dark:bg-dark-800 border border-gray-100 dark:border-dark-700 rounded-2xl rounded-tl-sm px-6 py-4 shadow-sm flex items-center gap-3">
                                    <div className="flex space-x-1">
                                        <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                                        <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                                        <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce"></div>
                                    </div>
                                    <span className="text-sm text-gray-500">Processing query...</span>
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </>
                )}
             </div>

             {/* Input Area (Bottom) */}
             <div className="p-4 bg-white dark:bg-dark-900 border-t border-gray-200 dark:border-dark-800 z-20">
               <div className="max-w-4xl mx-auto relative">
                 <form onSubmit={handleQuerySubmit} className="relative group">
                   <input
                     type="text"
                     value={query}
                     onChange={(e) => setQuery(e.target.value)}
                     placeholder={selectedTable ? `Ask a question about ${selectedTable}...` : "Select a table to start..."}
                     className="w-full pl-5 pr-14 py-4 bg-gray-50 dark:bg-dark-800 border border-gray-200 dark:border-dark-700 rounded-2xl focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 focus:bg-white dark:focus:bg-dark-900 outline-none transition-all shadow-sm text-gray-700 dark:text-gray-200 placeholder-gray-400"
                     disabled={!selectedTable || loading}
                   />
                   <button 
                     type="submit"
                     disabled={!query.trim() || loading || !selectedTable}
                     className="absolute right-2 top-1/2 transform -translate-y-1/2 p-2.5 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg active:scale-95"
                   >
                     <RiSendPlaneFill size={20} />
                   </button>
                 </form>
                 <div className="text-center mt-2">
                    <p className="text-[10px] text-gray-400 dark:text-gray-600">
                        Try asking: "Show me top 5 rows", "Count records by category", "Average price per item"
                    </p>
                 </div>
               </div>
             </div>
          </div>
        </main>
      </div>
    </div>
  )
}

export default CsvDashboard
