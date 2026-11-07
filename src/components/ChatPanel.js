"use client";

import { useState } from "react";
import { askQuestion } from "../lib/api";

export default function ChatPanel() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(event) {
    event.preventDefault();
    const submittedQuestion = question.trim();
    if (!submittedQuestion || pending) return;

    setPending(true);
    setError("");
    try {
      const response = await askQuestion(submittedQuestion);
      setMessages((current) => [...current, { question: submittedQuestion, response }]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The question could not be answered.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="card chat-panel" aria-labelledby="chat-heading">
      <h2 id="chat-heading">Ask about compliance rules</h2>
      <p className="hint">Ask a question about the vessel rules and get an answer with source clauses.</p>

      {messages.length > 0 && (
        <div className="chat-messages" aria-live="polite" aria-busy={pending}>
          {messages.map(({ question: asked, response }, index) => (
            <article className="chat-exchange" key={index}>
              <p className="chat-question">{asked}</p>
              <div className="chat-answer">
                <p>{response.answer}</p>
                {response.relevant && response.clauses.length > 0 && (
                  <div className="chat-sources">
                    <strong>Sources</strong>
                    <ul>
                      {response.clauses.map((clause) => (
                        <li key={clause.id}>
                          <a href={clause.source_url} target="_blank" rel="noreferrer">
                            {clause.title}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </article>
          ))}
          {pending && <p className="hint" role="status">Thinking...</p>}
        </div>
      )}

      <form className="chat-form" onSubmit={onSubmit}>
        <label htmlFor="chat-question">Your question</label>
        <textarea
          id="chat-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          maxLength={2000}
          placeholder="For example: What are the requirements for escape routes?"
          required
        />
        <div className="chat-form-footer">
          <span className="hint">Up to 2,000 characters</span>
          <button type="submit" className="primary" disabled={pending || !question.trim()}>
            {pending ? "Sending..." : "Ask"}
          </button>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
      </form>
    </section>
  );
}
