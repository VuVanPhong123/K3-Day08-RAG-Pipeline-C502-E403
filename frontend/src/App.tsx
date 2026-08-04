import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

type Role = "user" | "assistant";

type Source = {
  content: string;
  score: number;
  source: string;
  metadata: {
    title?: string;
    institution?: string;
    admission_year?: string | number;
    document_type?: string;
    url?: string;
    backend?: string;
    retrieval_mode?: string;
  };
};

type Message = {
  id: string;
  role: Role;
  content: string;
  sources?: Source[];
  provider?: string;
  model?: string;
};

type Health = {
  status: string;
  index_ready: boolean;
  chunk_count: number;
  generator: { provider: string; model: string };
  pageindex_backend: string;
  embedding_backend: string;
  embedding_backend_configured?: string;
  embedding_backend_actual?: string;
};

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const STORAGE_KEY = "admission-rag-chat";

function isValidUrl(value?: string) {
  if (!value) return false;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

function inlineMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[[^\]]+\])/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("[") && part.endsWith("]")) {
      return (
        <span className="citation" key={index}>
          {part}
        </span>
      );
    }
    return part;
  });
}

function MarkdownLite({ text }: { text: string }) {
  const lines = text.split(/\n+/).filter(Boolean);
  return (
    <div className="markdown">
      {lines.map((line, index) => {
        if (line.startsWith("- ")) {
          return <p key={index}>• {inlineMarkdown(line.slice(2))}</p>;
        }
        return <p key={index}>{inlineMarkdown(line)}</p>;
      })}
    </div>
  );
}

function SourceList({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false);
  if (!sources.length) {
    return <p className="source-empty">Không có nguồn tham khảo đi kèm.</p>;
  }
  return (
    <div className="sources">
      <button className="source-toggle" type="button" onClick={() => setOpen((value) => !value)}>
        {open ? "Ẩn nguồn tham khảo" : `Xem nguồn tham khảo (${sources.length})`}
      </button>
      {open && (
        <div className="source-list">
          {sources.map((source, index) => {
            const meta = source.metadata || {};
            return (
              <article className="source-item" key={`${meta.title || "source"}-${index}`}>
                <div className="source-head">
                  <h3>{meta.title || "Nguồn tuyển sinh"}</h3>
                  <span>{Number(source.score || 0).toFixed(3)}</span>
                </div>
                <dl>
                  <div>
                    <dt>Trường</dt>
                    <dd>{meta.institution || "N/A"}</dd>
                  </div>
                  <div>
                    <dt>Năm</dt>
                    <dd>{meta.admission_year || "N/A"}</dd>
                  </div>
                  <div>
                    <dt>Loại</dt>
                    <dd>{meta.document_type || "N/A"}</dd>
                  </div>
                  <div>
                    <dt>Retrieval</dt>
                    <dd>{source.source || "N/A"}</dd>
                  </div>
                  <div>
                    <dt>Backend</dt>
                    <dd>{meta.backend || meta.retrieval_mode || "hybrid"}</dd>
                  </div>
                </dl>
                <p className="excerpt">{source.content || "Không có evidence excerpt."}</p>
                {isValidUrl(meta.url) && (
                  <a href={meta.url} target="_blank" rel="noreferrer">
                    Mở nguồn chính thức
                  </a>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

function App() {
  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    return saved ? (JSON.parse(saved) as Message[]) : [];
  });
  const [health, setHealth] = useState<Health | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const statusText = useMemo(() => {
    if (!health) return "Backend chưa chạy";
    if (!health.index_ready) return "Index chưa sẵn sàng";
    return `API sẵn sàng · ${health.chunk_count} chunks`;
  }, [health]);

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const loadStatus = async () => {
      try {
        const [healthResponse, suggestionResponse] = await Promise.all([
          fetch(`${API_URL}/api/health`),
          fetch(`${API_URL}/api/suggestions`)
        ]);
        if (!healthResponse.ok) throw new Error("health");
        setHealth(await healthResponse.json());
        if (suggestionResponse.ok) setSuggestions(await suggestionResponse.json());
        setError("");
      } catch {
        setHealth(null);
        setError("Backend chưa chạy hoặc chưa truy cập được. Hãy khởi động FastAPI ở cổng 8000.");
      }
    };
    loadStatus();
  }, []);

  async function sendMessage(value: string) {
    const message = value.trim();
    if (!message || loading) return;
    setError("");
    setInput("");
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content: message };
    setMessages((current) => [...current, userMessage]);
    setLoading(true);

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 78000);
    try {
      const history = messages
        .slice(-8)
        .map(({ role, content }) => ({ role, content }));
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history, top_k: topK }),
        signal: controller.signal
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Không thể xử lý câu hỏi lúc này.");
      }
      const data = await response.json();
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: data.answer,
        sources: data.sources || [],
        provider: data.provider,
        model: data.model
      };
      setMessages((current) => [...current, assistantMessage]);
    } catch (err) {
      const timeoutMessage = err instanceof DOMException && err.name === "AbortError";
      setError(timeoutMessage ? "Request timeout. Vui lòng thử lại với câu hỏi ngắn hơn." : String((err as Error).message));
    } finally {
      window.clearTimeout(timeout);
      setLoading(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    sendMessage(input);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage(input);
    }
  }

  function clearConversation() {
    setMessages([]);
    setInput("");
    setError("");
    sessionStorage.removeItem(STORAGE_KEY);
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">University Admission RAG Assistant</p>
          <h1>Trợ lý AI tra cứu tuyển sinh đại học</h1>
          <p>Tra cứu học phí, học bổng, chỉ tiêu, điểm chuẩn và phương thức xét tuyển từ nguồn chính thức.</p>
        </div>
        <div className="header-actions">
          <span className={health?.index_ready ? "status ok" : "status warn"}>{statusText}</span>
          <button type="button" onClick={clearConversation}>
            Xóa hội thoại
          </button>
        </div>
      </header>

      <section className="overview" aria-label="Pipeline overview">
        {["Hybrid Retrieval", "BM25 + Semantic Search", "RRF Reranking", "Citation & PageIndex Fallback"].map((item) => (
          <span key={item}>{item}</span>
        ))}
      </section>

      <section className="workspace">
        <aside className="side-panel">
          <label htmlFor="top-k">Số nguồn</label>
          <select id="top-k" value={topK} onChange={(event) => setTopK(Number(event.target.value))}>
            {[3, 4, 5, 6, 7, 8].map((value) => (
              <option value={value} key={value}>
                top_k = {value}
              </option>
            ))}
          </select>
          <div className="meta">
            <span>Generator</span>
            <strong>{health ? `${health.generator.provider} · ${health.generator.model}` : "N/A"}</strong>
          </div>
          <div className="meta">
            <span>PageIndex</span>
            <strong>{health?.pageindex_backend || "N/A"}</strong>
          </div>
          <div className="meta">
            <span>Embedding</span>
            <strong>{health?.embedding_backend || "N/A"}</strong>
          </div>
        </aside>

        <section className="chat-panel" aria-label="Chat">
          <div className="suggestions">
            {(suggestions.length ? suggestions : [
              "Điều kiện IELTS vào HUST năm 2026 là gì?",
              "HUST chấp nhận những chứng chỉ quốc tế nào?",
              "VinUni có học bổng nào?",
              "Chỉ tiêu HUST năm 2026?",
              "Học phí Computer Science tại RMIT năm 2026 là bao nhiêu?"
            ]).map((question) => (
              <button key={question} type="button" onClick={() => sendMessage(question)} disabled={loading}>
                {question}
              </button>
            ))}
          </div>

          <div className="messages">
            {messages.length === 0 && (
              <div className="empty-state">
                <h2>Sẵn sàng tra cứu</h2>
                <p>Chọn một câu hỏi gợi ý hoặc nhập câu hỏi tuyển sinh cụ thể để xem câu trả lời kèm nguồn.</p>
              </div>
            )}
            {messages.map((message) => (
              <article className={`message ${message.role}`} key={message.id}>
                <div className="bubble">
                  <MarkdownLite text={message.content} />
                  {message.role === "assistant" && (
                    <>
                      <p className="provider">
                        Provider: {message.provider || "unknown"} · Model: {message.model || "unknown"}
                      </p>
                      <SourceList sources={message.sources || []} />
                    </>
                  )}
                </div>
              </article>
            ))}
            {loading && (
              <article className="message assistant">
                <div className="bubble loading">Đang truy xuất tài liệu và tổng hợp câu trả lời...</div>
              </article>
            )}
            <div ref={bottomRef} />
          </div>

          {error && <div className="error">{error}</div>}

          <form className="composer" onSubmit={handleSubmit}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Nhập câu hỏi về IELTS, học phí, học bổng, chỉ tiêu hoặc điểm chuẩn..."
              disabled={loading}
              maxLength={2000}
            />
            <button type="submit" disabled={loading || !input.trim()}>
              Gửi
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}

export default App;
