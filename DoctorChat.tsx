import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Send, Menu, X } from "lucide-react";
import { useLocation } from "wouter";

interface Message {
  id: string;
  sender: "student" | "doctor";
  senderName: string;
  text: string;
  timestamp: Date;
}

export default function DoctorChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      sender: "doctor",
      senderName: "Dr. Osama",
      text: "Hello! How can I help you with your studies?",
      timestamp: new Date(Date.now() - 3600000),
    },
    {
      id: "2",
      sender: "student",
      senderName: "You",
      text: "Hi Dr. Osama, I have a question about the Data Structures lecture",
      timestamp: new Date(Date.now() - 1800000),
    },
    {
      id: "3",
      sender: "doctor",
      senderName: "Dr. Osama",
      text: "Sure! Go ahead and ask your question.",
      timestamp: new Date(Date.now() - 900000),
    },
  ]);
  const [input, setInput] = useState("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [, navigate] = useLocation();

  const handleSendMessage = () => {
    if (input.trim()) {
      const userMessage: Message = {
        id: Date.now().toString(),
        sender: "student",
        senderName: "You",
        text: input,
        timestamp: new Date(),
      };

      setMessages([...messages, userMessage]);
      setInput("");

      // Simulate doctor response
      setTimeout(() => {
        const doctorMessage: Message = {
          id: (Date.now() + 1).toString(),
          sender: "doctor",
          senderName: "Dr. Osama",
          text: "That's a good question. Let me explain that for you...",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, doctorMessage]);
      }, 1000);
    }
  };

  const sidebarItems = [
    { icon: "📊", label: "Overview", href: "/student/dashboard" },
    { icon: "📋", label: "Attendance", href: "#" },
    { icon: "✏️", label: "Exams", href: "#" },
    { icon: "🤖", label: "AI Advice", href: "#" },
    { icon: "💬", label: "AI Chat", href: "/ai-chat" },
    { icon: "📚", label: "Study Plan", href: "#" },
    { icon: "⚠️", label: "Weak Points", href: "#" },
    { icon: "📖", label: "Resources", href: "#" },
    { icon: "👨‍⚕️", label: "Doctor Chat", href: "/doctor-chat", active: true },
    { icon: "🔔", label: "Notifications", href: "#" },
    { icon: "📈", label: "Score Analysis", href: "#" },
    { icon: "📅", label: "Calendar", href: "#" },
    { icon: "👤", label: "Profile", href: "#" },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Navigation Bar */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-slate-900/80 backdrop-blur-md border-b border-slate-700/50">
        <div className="px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🧠</span>
            <span className="text-xl font-bold text-white">Mentor Mind</span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate("/student/dashboard")}
              className="hidden md:block px-4 py-2 rounded-lg text-slate-300 hover:bg-slate-700/50 transition"
            >
              Dashboard
            </button>
            <button className="px-4 py-2 rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 transition font-semibold">
              Logout
            </button>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 hover:bg-slate-700/50 rounded-lg transition"
            >
              {mobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>
        </div>
      </nav>

      <div className="flex pt-16">
        {/* Sidebar */}
        <aside className="w-72 bg-slate-800/50 backdrop-blur-sm border-r border-slate-700/50 overflow-hidden hidden md:block">
          <div className="p-6 space-y-6">
            <div className="flex items-center gap-3 pb-6 border-b border-slate-700/50">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-400 to-emerald-400 flex items-center justify-center font-bold text-slate-900">
                M
              </div>
              <span className="font-bold text-white">Student</span>
            </div>

            <div className="space-y-3">
              {sidebarItems.map((item) => (
                <button
                  key={item.label}
                  onClick={() => item.href !== "#" && navigate(item.href)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition ${
                    item.active
                      ? "bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 font-semibold"
                      : "text-slate-300 hover:bg-slate-700/50"
                  }`}
                >
                  <span className="text-lg">{item.icon}</span>
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="bg-slate-800/30 backdrop-blur-sm border-b border-slate-700/50 px-8 py-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-bold">
                DO
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">Dr. Osama</h1>
                <p className="text-slate-400 text-sm">Online</p>
              </div>
            </div>
          </div>

          {/* Chat Area */}
          <div className="flex-1 overflow-y-auto p-8 space-y-4">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.sender === "student" ? "justify-end" : "justify-start"}`}
              >
                <div className={`flex gap-3 max-w-md ${msg.sender === "student" ? "flex-row-reverse" : ""}`}>
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm flex-shrink-0 ${
                      msg.sender === "student"
                        ? "bg-emerald-500/20 text-emerald-300"
                        : "bg-blue-500/20 text-blue-300"
                    }`}
                  >
                    {msg.sender === "student" ? "S" : "D"}
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 mb-1">{msg.senderName}</p>
                    <div
                      className={`px-4 py-3 rounded-lg ${
                        msg.sender === "student"
                          ? "bg-cyan-500/20 border border-cyan-500/30 text-white"
                          : "bg-slate-700/50 border border-slate-600/50 text-slate-100"
                      }`}
                    >
                      <p>{msg.text}</p>
                    </div>
                    <p className="text-xs mt-1 opacity-60">
                      {msg.timestamp.toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Input Area */}
          <div className="bg-slate-800/30 backdrop-blur-sm border-t border-slate-700/50 p-6">
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleSendMessage()}
                placeholder="Type your message here..."
                className="flex-1 bg-slate-700/50 border border-slate-600/50 rounded-lg px-4 py-3 text-white placeholder-slate-400 focus:outline-none focus:border-cyan-500/50"
              />
              <Button
                onClick={handleSendMessage}
                className="bg-cyan-500 hover:bg-cyan-600 text-slate-900 font-semibold px-6 rounded-lg flex items-center gap-2"
              >
                <Send size={18} />
              </Button>
            </div>
          </div>
        </main>
      </div>

      {/* Mobile Sidebar */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 bg-black/50 z-40 md:hidden" onClick={() => setMobileMenuOpen(false)}>
          <div className="w-64 bg-slate-800 h-full overflow-y-auto p-6 space-y-4">
            {sidebarItems.map((item) => (
              <button
                key={item.label}
                onClick={() => {
                  item.href !== "#" && navigate(item.href);
                  setMobileMenuOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition ${
                  item.active
                    ? "bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 font-semibold"
                    : "text-slate-300 hover:bg-slate-700/50"
                }`}
              >
                <span className="text-lg">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}