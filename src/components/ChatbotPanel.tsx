'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useChat, Message } from 'ai/react';
import { Bot, Send, X, ChevronsRight, ChevronsLeft, Loader2, RotateCcw, Square } from 'lucide-react';

// Define initial messages outside the hook call to reference them later
const initialChatMessages: Message[] = [
  {
    id: 'system-init',
    role: 'system',
    content: 'You are a helpful assistant knowledgeable about biodiversity, taxonomy, and conservation, integrated into the biocosmos platform.'
  }
];

export default function ChatbotPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const { messages, setMessages, input, handleInputChange, handleSubmit, isLoading, error, stop } = useChat({
    api: '/api/chat', // Path to our backend route
    initialMessages: initialChatMessages, // Use the defined constant
    // Optional: Add error handler if needed
    // onError: (err) => { console.error("Chat Error:", err); }
  });
  const scrollRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom whenever messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Toggle panel visibility
  const togglePanel = () => setIsOpen(!isOpen);

  // Function to handle clearing the chat using setMessages
  const handleClearChat = () => {
      if (!isLoading && initialChatMessages.length > 0) {
          // Reset to only the first initial message (system prompt)
          setMessages([initialChatMessages[0]]); 
      }
  };

  return (
    <>
      {/* Button to open/close the panel - positioned fixed on the right */}
      <button
        onClick={togglePanel}
        className={`fixed top-1/2 transform -translate-y-1/2 z-20 p-2 bg-green-600 dark:bg-green-700 text-white rounded-l-md shadow-lg hover:bg-green-700 dark:hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500 transition-all duration-300 ease-in-out ${isOpen ? 'right-[350px] md:right-[400px]' : 'right-0'}`}
        aria-label={isOpen ? 'Close Chat Panel' : 'Open Chat Panel'}
      >
        {isOpen ? <ChevronsRight size={20} /> : <ChevronsLeft size={20} />}
      </button>

      {/* The Chat Panel - slides in from the right */}
      <div
        className={`fixed top-0 right-0 h-full w-[350px] md:w-[400px] bg-white dark:bg-gray-800 shadow-xl z-30 flex flex-col transition-transform duration-300 ease-in-out transform ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
      >
        {/* Panel Header with Clear Button*/}
        <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100 flex items-center gap-2">
            <Bot size={20} />
            <span>AI Assistant</span>
          </h2>
          <div className="flex items-center gap-2"> {/* Group buttons */}
            {/* Clear Chat Button */}
            <button
              onClick={handleClearChat}
              disabled={isLoading}
              className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Clear Chat History"
              title="Clear Chat History"
            >
              <RotateCcw size={18} />
            </button>
            {/* Close Panel Button */}
            <button
              onClick={togglePanel}
              className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400"
              aria-label="Close Chat Panel"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Message Area - Scrollable */}
        <div ref={scrollRef} className="flex-grow p-4 overflow-y-auto space-y-4">
          {messages.length > 1 ? (
            messages.map(m => (
              m.role !== 'system' && (
                <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[80%] px-3 py-2 rounded-lg whitespace-pre-wrap ${m.role === 'user' 
                      ? 'bg-green-600 text-white' 
                      : 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100'}`}
                  >
                    {m.content}
                  </div>
                </div>
              )
            ))
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center">Start the conversation below.</p>
          )}
          {isLoading && (
             <div className="flex justify-start">
                <div className="px-3 py-2 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 flex items-center">
                  <Loader2 className="h-4 w-4 animate-spin mr-2"/> Thinking...
                </div>
            </div>
          )}
        </div>

        {/* Error Display Area */}
        {error && (
          <div className="px-4 pb-2 text-red-500 text-sm border-t border-gray-200 dark:border-gray-700 pt-2">
            <p>Error: {error.message}</p>
          </div>
        )}

        {/* Input Area with Stop Button Logic */}
        <form onSubmit={handleSubmit} className="p-3 border-t border-gray-200 dark:border-gray-700 flex-shrink-0 flex items-center gap-2">
          <input
            className="flex-grow px-3 py-2 rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 focus:outline-none focus:ring-1 focus:ring-green-500 text-sm"
            value={input}
            placeholder="Ask about species, ecosystems..."
            onChange={handleInputChange}
            disabled={isLoading}
          />
          {isLoading ? (
            <button 
              type="button"
              onClick={stop}
              className="p-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500"
              aria-label="Stop generating response"
              title="Stop generating response"
            >
               <Square size={20} />
            </button>
          ) : (
            <button 
              type="submit" 
              disabled={!input.trim()}
              className="p-2 bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Send message"
            >
               <Send size={20} />
            </button>
          )}
        </form>
      </div>
    </>
  );
} 