"use client";

import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Bot, User, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getActiveRunId, getSessionUser, sendChatMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Chatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([
    {
      role: "assistant",
      content: "Hi! I'm NEXUS AI 👋\n\nI can help you understand your placement profile, assessment results, skill gaps, roadmap, and anything else about NEXUS.\n\nWhat would you like to know?"
    }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const suggestedQuestions = [
    "How does my readiness score work?",
    "What should I improve first?",
    "Explain my skill gaps",
    "Which companies match me?",
    "How does the assessment work?"
  ];

  const scrollToBottom = () => {
    if (messages.length > 1) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, isOpen]);

  const handleSend = async (text: string) => {
    if (!text.trim()) return;

    const newMessages = [...messages, { role: "user", content: text }];
    setMessages(newMessages);
    setInput("");

    // The assistant answers from the student's own plan, so it needs a student sign-in
    const user = getSessionUser();
    if (!user || user.role !== "student") {
      setMessages([...newMessages, { role: "assistant", content: user
        ? "The career assistant is for students. Use your console for Placement Cell work."
        : "Please sign in as a student to chat — I answer from your own readiness plan." }]);
      return;
    }
    setIsLoading(true);

    try {
      const runId = getActiveRunId();
      const { response } = await sendChatMessage(text, messages, runId);
      
      setMessages([...newMessages, { role: "assistant", content: response }]);
    } catch (error) {
      console.warn("Chat error:", error);
      setMessages([
        ...newMessages,
        { role: "assistant", content: "Sorry, I'm having trouble connecting right now. Please try again later." }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  };

  return (
    <>
      {/* Floating Button */}
      <button
        onClick={() => setIsOpen(true)}
        className={cn(
          "fixed bottom-6 right-6 p-4 rounded-full shadow-xl transition-all duration-300 z-50",
          "bg-orange text-white hover:bg-orange/90 hover:scale-105 active:scale-95",
          isOpen && "opacity-0 pointer-events-none scale-90"
        )}
      >
        <MessageCircle className="w-6 h-6" />
      </button>

      {/* Chat Panel */}
      <div
        className={cn(
          "fixed bottom-6 right-6 w-[360px] sm:w-[450px] h-[640px] max-h-[85vh] flex flex-col z-50",
          "bg-ivory rounded-[20px] shadow-2xl border border-border-subtle transition-all duration-300 transform origin-bottom-right",
          isOpen ? "scale-100 opacity-100" : "scale-90 opacity-0 pointer-events-none"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 bg-white border-b border-border-subtle rounded-t-[20px]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-orange/10 flex items-center justify-center">
              <Bot className="w-5 h-5 text-orange" />
            </div>
            <div>
              <h3 className="font-semibold text-charcoal leading-none mb-1">NEXUS AI</h3>
              <p className="text-xs text-bronze-dark/60">Your placement assistant</p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-surface-muted transition-colors text-bronze-dark/60"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={cn(
                "flex gap-3 max-w-[92%]",
                msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
              )}
            >
              <div className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                msg.role === "user" ? "bg-charcoal text-white" : "bg-orange text-white"
              )}>
                {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              {msg.role === "user" ? (
                <div className="px-4 py-2.5 rounded-[16px] text-sm bg-charcoal text-white rounded-tr-sm whitespace-pre-wrap">
                  {msg.content}
                </div>
              ) : (
                <div className="px-4 py-3 rounded-[16px] text-sm bg-white border border-border-subtle text-charcoal rounded-tl-sm shadow-xs overflow-hidden leading-relaxed">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      h1: ({ children }) => (
                        <h1 className="text-sm font-bold text-charcoal mt-2 mb-1.5 flex items-center gap-1.5">{children}</h1>
                      ),
                      h2: ({ children }) => (
                        <h2 className="text-xs font-bold text-charcoal uppercase tracking-wider mt-3 mb-1.5 text-orange border-b border-border-subtle/50 pb-1">{children}</h2>
                      ),
                      h3: ({ children }) => (
                        <h3 className="text-xs font-semibold text-charcoal mt-2 mb-1">{children}</h3>
                      ),
                      p: ({ children }) => (
                        <p className="mb-2 leading-relaxed text-charcoal/90 last:mb-0 text-xs sm:text-sm">{children}</p>
                      ),
                      ul: ({ children }) => (
                        <ul className="list-disc list-outside pl-4 mb-2 space-y-1 text-xs sm:text-sm">{children}</ul>
                      ),
                      ol: ({ children }) => (
                        <ol className="list-decimal list-outside pl-4 mb-2 space-y-1 text-xs sm:text-sm">{children}</ol>
                      ),
                      li: ({ children }) => (
                        <li className="leading-relaxed">{children}</li>
                      ),
                      strong: ({ children }) => (
                        <strong className="font-semibold text-charcoal">{children}</strong>
                      ),
                      hr: () => (
                        <hr className="my-2.5 border-border-subtle/60" />
                      ),
                      code: ({ children }) => (
                        <code className="bg-surface-warm px-1.5 py-0.5 rounded text-xs font-mono text-orange border border-border-subtle/40">
                          {children}
                        </code>
                      ),
                      table: ({ children }) => (
                        <div className="overflow-x-auto my-2 rounded-lg border border-border-subtle shadow-2xs">
                          <table className="w-full text-xs text-left border-collapse">{children}</table>
                        </div>
                      ),
                      th: ({ children }) => (
                        <th className="bg-surface-warm font-semibold px-2 py-1.5 border-b border-border-subtle text-charcoal whitespace-nowrap">
                          {children}
                        </th>
                      ),
                      td: ({ children }) => (
                        <td className="px-2 py-1.5 border-b border-border-subtle/40 text-bronze-dark/90 align-top">
                          {children}
                        </td>
                      ),
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          ))}
          
          {isLoading && (
            <div className="flex gap-3 max-w-[85%] mr-auto">
              <div className="w-8 h-8 rounded-full bg-orange text-white flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <div className="px-4 py-3 rounded-[16px] bg-white border border-border-subtle rounded-tl-sm shadow-xs flex items-center gap-1">
                <div className="w-1.5 h-1.5 bg-orange/60 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                <div className="w-1.5 h-1.5 bg-orange/60 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                <div className="w-1.5 h-1.5 bg-orange/60 rounded-full animate-bounce"></div>
              </div>
            </div>
          )}

          {/* Suggested Questions (only show if few messages) */}
          {messages.length === 1 && (
            <div className="flex flex-col gap-2 mt-4 ml-11">
              <p className="text-xs text-bronze-dark/50 mb-1 font-medium">Suggested questions:</p>
              {suggestedQuestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(q)}
                  className="text-left px-3 py-2 text-xs text-orange bg-orange/5 hover:bg-orange/10 border border-orange/20 rounded-[12px] transition-colors w-fit"
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 bg-white border-t border-border-subtle rounded-b-[20px]">
          <div className="relative flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything..."
              className="w-full bg-surface-warm border border-border-subtle rounded-[16px] px-4 py-3 pr-12 text-sm focus:outline-none focus:border-orange focus:ring-1 focus:ring-orange/30 resize-none max-h-32"
              rows={1}
              style={{ minHeight: "44px" }}
            />
            <button
              onClick={() => handleSend(input)}
              disabled={!input.trim() || isLoading}
              className="absolute right-2 bottom-2 w-8 h-8 rounded-full bg-orange text-white flex items-center justify-center disabled:opacity-50 disabled:bg-bronze-dark transition-colors"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
          <div className="flex justify-between items-center mt-2">
            <p className="text-[10px] text-bronze-dark/40 px-2">Shift+Enter for new line</p>
            {messages.length > 1 && (
              <button 
                onClick={() => setMessages([messages[0]])}
                className="text-[10px] text-bronze-dark/60 hover:text-danger px-2 transition-colors"
              >
                Clear chat
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
